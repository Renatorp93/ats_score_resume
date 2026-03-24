from __future__ import annotations

import re
from dataclasses import dataclass

from ats_score_resume.document_parser import ExtractedDocument
from ats_score_resume.text_utils import (
    ACTION_VERBS,
    REQUIRED_MARKERS,
    clamp_score,
    detect_seniority,
    extract_degree_terms,
    extract_significant_terms,
    extract_skill_phrases,
    normalize_for_matching,
    overlap_ratio,
    split_nonempty_lines,
    tokenize,
)

SECTION_ALIASES = {
    "summary": (
        "summary",
        "professional summary",
        "profile",
        "objective",
        "resumo",
        "resumo profissional",
        "perfil",
        "objetivo",
    ),
    "experience": (
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "career history",
        "experiencia",
        "experiencia profissional",
        "historico profissional",
    ),
    "education": (
        "education",
        "academic background",
        "formacao",
        "formacao academica",
        "educacao",
    ),
    "skills": (
        "skills",
        "technical skills",
        "core competencies",
        "competencies",
        "habilidades",
        "competencias",
        "conhecimentos",
    ),
    "certifications": ("certifications", "licenses", "certificacoes", "cursos"),
}

DATE_PATTERN = re.compile(
    r"\b(?:"
    r"\d{4}"
    r"|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|"
    r"january|february|march|april|june|july|august|september|october|november|december|"
    r"jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)"
    r")[ /-]*\d{0,4}\b",
    re.IGNORECASE,
)
EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
PHONE_PATTERN = re.compile(r"(\+\d{1,3}\s?)?(?:\(?\d{2,3}\)?[\s-]?)?\d{4,5}[\s-]?\d{4}\b")
LOCATION_PATTERN = re.compile(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+)*,? [A-Z]{2}\b")
LINKEDIN_PATTERN = re.compile(r"linkedin\.com|github\.com|portfolio", re.IGNORECASE)
UPPERCASE_ACRONYM_PATTERN = re.compile(r"\b[A-Z]{2,6}\b")


@dataclass(slots=True)
class MetricResult:
    key: str
    label: str
    score: int
    max_score: int
    details: str


@dataclass(slots=True)
class Suggestion:
    priority: str
    title: str
    details: str


@dataclass(slots=True)
class ResumeAnalysis:
    score: int
    metrics: list[MetricResult]
    detected_sections: list[str]
    missing_sections: list[str]
    format_risks: list[str]
    contact_hits: list[str]
    quantified_achievement_count: int
    action_bullet_count: int
    keyword_terms: list[str]


@dataclass(slots=True)
class JobMatchAnalysis:
    score: int
    metrics: list[MetricResult]
    job_title: str | None
    matched_keywords: list[str]
    missing_keywords: list[str]
    missing_required_terms: list[str]
    source: str


@dataclass(slots=True)
class AnalysisResult:
    resume: ResumeAnalysis
    overall_score: int
    suggestions: list[Suggestion]
    job_match: JobMatchAnalysis | None = None


def analyze_document(document: ExtractedDocument, job_text: str | None = None, job_source: str = "") -> AnalysisResult:
    resume = analyze_resume(document)
    job_match = analyze_job_match(document.cleaned_text, job_text, job_source) if job_text else None
    overall_score = resume.score if job_match is None else round((resume.score * 0.45) + (job_match.score * 0.55))
    suggestions = build_suggestions(document, resume, job_match)
    return AnalysisResult(
        resume=resume,
        job_match=job_match,
        overall_score=overall_score,
        suggestions=suggestions,
    )


def analyze_resume(document: ExtractedDocument) -> ResumeAnalysis:
    text = document.cleaned_text
    raw_lines = split_nonempty_lines(document.raw_text)
    normalized_text = normalize_for_matching(text)
    lines_for_matching = [normalize_for_matching(line) for line in raw_lines]

    detected_sections = detect_sections(lines_for_matching)
    missing_sections = [section for section in ("summary", "experience", "education", "skills") if section not in detected_sections]
    format_risks = detect_format_risks(document, raw_lines)
    contact_hits = detect_contact_fields(text)
    keyword_terms = extract_significant_terms(text, limit=18)

    parsing_metric = score_parsing_and_format(document, text, detected_sections, format_risks)
    completeness_metric = score_completeness(contact_hits, detected_sections)
    content_metric, quantified_count, action_count = score_content_quality(text, normalized_text, raw_lines)

    total = parsing_metric.score + completeness_metric.score + content_metric.score
    return ResumeAnalysis(
        score=total,
        metrics=[parsing_metric, completeness_metric, content_metric],
        detected_sections=detected_sections,
        missing_sections=missing_sections,
        format_risks=format_risks,
        contact_hits=contact_hits,
        quantified_achievement_count=quantified_count,
        action_bullet_count=action_count,
        keyword_terms=keyword_terms,
    )


def analyze_job_match(resume_text: str, job_text: str | None, source: str) -> JobMatchAnalysis | None:
    if not job_text:
        return None

    job_terms = extract_significant_terms(job_text, limit=20)
    resume_terms = extract_significant_terms(resume_text, limit=50)
    resume_term_set = set(resume_terms)

    matched_keywords = [term for term in job_terms if term in resume_term_set]
    missing_keywords = [term for term in job_terms if term not in resume_term_set]
    keyword_score = clamp_score(overlap_ratio(job_terms, resume_terms) * 35, 35)

    required_terms = extract_required_terms(job_text)
    required_overlap = [term for term in required_terms if term in resume_term_set]
    missing_required_terms = [term for term in required_terms if term not in resume_term_set]
    required_score = clamp_score(overlap_ratio(required_terms, resume_terms) * 25, 25) if required_terms else 13

    job_title = extract_job_title(job_text)
    title_score = score_title_alignment(job_title, resume_text, job_text)
    experience_education_score = score_evidence_alignment(job_text, resume_text)
    terminology_score = score_terminology_fidelity(job_text, resume_text)

    metrics = [
        MetricResult(
            key="keyword_coverage",
            label="Cobertura de keywords",
            score=keyword_score,
            max_score=35,
            details=f"{len(matched_keywords)} de {len(job_terms) or 0} termos principais aparecem no curriculo.",
        ),
        MetricResult(
            key="required_terms",
            label="Cobertura de requisitos obrigatorios",
            score=required_score,
            max_score=25,
            details=f"{len(required_overlap)} de {len(required_terms) or 0} requisitos explicitos aparecem no curriculo.",
        ),
        MetricResult(
            key="title_alignment",
            label="Alinhamento de titulo e senioridade",
            score=title_score,
            max_score=15,
            details=f"Titulo da vaga identificado como: {job_title or 'nao identificado'}.",
        ),
        MetricResult(
            key="evidence_alignment",
            label="Evidencias de experiencia e educacao",
            score=experience_education_score,
            max_score=15,
            details="Verifica se termos de experiencia e formacao da vaga aparecem no curriculo.",
        ),
        MetricResult(
            key="terminology_fidelity",
            label="Fidelidade terminologica",
            score=terminology_score,
            max_score=10,
            details="Premia siglas e frases tecnicas que batem exatamente com a vaga.",
        ),
    ]

    return JobMatchAnalysis(
        score=sum(metric.score for metric in metrics),
        metrics=metrics,
        job_title=job_title,
        matched_keywords=matched_keywords[:12],
        missing_keywords=missing_keywords[:12],
        missing_required_terms=missing_required_terms[:10],
        source=source,
    )


def build_suggestions(
    document: ExtractedDocument,
    resume: ResumeAnalysis,
    job_match: JobMatchAnalysis | None,
) -> list[Suggestion]:
    suggestions: list[Suggestion] = []

    if document.extension == ".pdf":
        suggestions.append(
            Suggestion(
                priority="alta",
                title="Considere manter uma versao DOCX do curriculo",
                details="PDF pode funcionar bem, mas DOCX costuma ser a opcao mais previsivel para parsing ATS quando a vaga nao exige PDF.",
            )
        )

    if "skills" in resume.missing_sections:
        suggestions.append(
            Suggestion(
                priority="alta",
                title="Crie uma secao de skills dedicada",
                details="Liste hard skills, ferramentas, linguagens, metodologias e certificacoes em uma secao clara para facilitar o match por keywords.",
            )
        )

    if "summary" in resume.missing_sections:
        suggestions.append(
            Suggestion(
                priority="media",
                title="Adicione um resumo profissional curto",
                details="Um resumo de 2 a 4 linhas ajuda a concentrar keywords e a alinhar rapidamente o perfil com a vaga.",
            )
        )

    if resume.quantified_achievement_count < 2:
        suggestions.append(
            Suggestion(
                priority="alta",
                title="Inclua resultados mensuraveis nas experiencias",
                details="Troque descricoes genericas por bullets com numeros, percentuais, prazos, volumes ou economias geradas.",
            )
        )

    if resume.action_bullet_count < 3:
        suggestions.append(
            Suggestion(
                priority="media",
                title="Reescreva experiencias com verbos de acao",
                details="Comece bullets com verbos como implementou, liderou, desenvolveu, improved ou managed para deixar o impacto mais claro.",
            )
        )

    if resume.format_risks:
        suggestions.append(
            Suggestion(
                priority="media",
                title="Simplifique a formatacao para reduzir risco de parsing",
                details="Evite excesso de pipes, tabs, icones e layouts que parecam tabelas ou colunas.",
            )
        )

    if job_match and job_match.missing_required_terms:
        suggestions.append(
            Suggestion(
                priority="alta",
                title="Cubra os requisitos obrigatorios da vaga com a mesma terminologia",
                details=f"Considere incorporar evidencias para: {', '.join(job_match.missing_required_terms[:5])}.",
            )
        )

    if job_match and job_match.missing_keywords:
        suggestions.append(
            Suggestion(
                priority="alta",
                title="Aumente a cobertura de keywords da vaga",
                details=f"Os principais termos ainda ausentes sao: {', '.join(job_match.missing_keywords[:6])}.",
            )
        )

    return suggestions[:7]


def detect_sections(lines: list[str]) -> list[str]:
    detected: list[str] = []
    for section, aliases in SECTION_ALIASES.items():
        if any(matches_heading(line, aliases) for line in lines):
            detected.append(section)
    return detected


def matches_heading(line: str, aliases: tuple[str, ...]) -> bool:
    trimmed = line.strip(":- ").lower()
    return any(trimmed == alias or trimmed.startswith(f"{alias}:") for alias in aliases)


def detect_format_risks(document: ExtractedDocument, lines: list[str]) -> list[str]:
    risks: list[str] = []
    raw_text = document.raw_text
    pipe_lines = sum(1 for line in lines if "|" in line)
    tab_lines = sum(1 for line in raw_text.splitlines() if "\t" in line)
    icon_hits = len(re.findall(r"[•●▪◆■♦★☎✉📧📱🔗]", raw_text))

    if pipe_lines >= 2:
        risks.append("ha sinais de colunas ou tabelas representadas por pipes")
    if tab_lines >= 2:
        risks.append("ha muitos tabs, o que pode indicar layout dificil para parsing")
    if icon_hits >= 3:
        risks.append("ha varios icones ou glifos decorativos")
    if len(document.cleaned_text) < 500:
        risks.append("o texto extraido ficou curto para um curriculo completo")

    return risks


def detect_contact_fields(text: str) -> list[str]:
    hits: list[str] = []
    if EMAIL_PATTERN.search(text):
        hits.append("email")
    if PHONE_PATTERN.search(text):
        hits.append("telefone")
    if LOCATION_PATTERN.search(text) or re.search(r"\b(?:sao paulo|rio de janeiro|belo horizonte|curitiba|remote|remoto)\b", text, re.IGNORECASE):
        hits.append("localizacao")
    if LINKEDIN_PATTERN.search(text):
        hits.append("perfil profissional")
    return hits


def score_parsing_and_format(
    document: ExtractedDocument,
    text: str,
    detected_sections: list[str],
    format_risks: list[str],
) -> MetricResult:
    extension_points = {".docx": 8, ".txt": 7, ".md": 7, ".pdf": 6}.get(document.extension, 0)
    char_count = len(text)

    if char_count >= 2200:
        text_points = 8
    elif char_count >= 1200:
        text_points = 6
    elif char_count >= 700:
        text_points = 4
    else:
        text_points = 1

    risk_points = max(0, 8 - (len(format_risks) * 2))
    heading_points = clamp_score((len(detected_sections) / 4) * 6, 6)
    score = extension_points + text_points + risk_points + heading_points
    details = (
        f"Formato {document.extension}, texto extraido com {char_count} caracteres, "
        f"{len(detected_sections)} secoes principais detectadas e {len(format_risks)} alertas de formatacao."
    )
    return MetricResult(
        key="parsing_format",
        label="Compatibilidade de parsing e formato",
        score=score,
        max_score=30,
        details=details,
    )


def score_completeness(contact_hits: list[str], detected_sections: list[str]) -> MetricResult:
    contact_score = min(
        10,
        (4 if "email" in contact_hits else 0)
        + (3 if "telefone" in contact_hits else 0)
        + (2 if "localizacao" in contact_hits else 0)
        + (1 if "perfil profissional" in contact_hits else 0),
    )
    summary_score = 5 if "summary" in detected_sections else 0
    experience_score = 7 if "experience" in detected_sections else 0
    education_score = 4 if "education" in detected_sections else 0
    skills_score = 4 if "skills" in detected_sections else 0
    score = contact_score + summary_score + experience_score + education_score + skills_score
    details = (
        f"Contato detectado: {', '.join(contact_hits) or 'insuficiente'}. "
        f"Secoes detectadas: {', '.join(detected_sections) or 'nenhuma secao padrao detectada'}."
    )
    return MetricResult(
        key="completeness",
        label="Completude estrutural",
        score=score,
        max_score=30,
        details=details,
    )


def score_content_quality(text: str, normalized_text: str, lines: list[str]) -> tuple[MetricResult, int, int]:
    date_hits = len(DATE_PATTERN.findall(text))
    quantified_lines = [
        line
        for line in lines
        if re.search(r"\d", line) and re.search(r"[%$]|r\$|usd|eur|anos|years|clientes|users|usuarios|projetos|projects", line, re.IGNORECASE)
    ]
    action_lines = [line for line in lines if line_starts_with_action_verb(line)]
    skill_terms = extract_skill_phrases(text)
    stuffing_penalty = repetition_penalty(normalized_text)

    date_score = 8 if date_hits >= 4 else 5 if date_hits >= 2 else 2 if date_hits >= 1 else 0
    quantified_score = 10 if len(quantified_lines) >= 3 else 6 if len(quantified_lines) >= 1 else 0
    action_score = 8 if len(action_lines) >= 4 else 5 if len(action_lines) >= 2 else 2 if len(action_lines) >= 1 else 0
    skill_score = 8 if len(skill_terms) >= 8 else 5 if len(skill_terms) >= 4 else 2 if len(skill_terms) >= 2 else 0
    stuffing_score = 6 if stuffing_penalty == 0 else 3 if stuffing_penalty == 1 else 0

    score = date_score + quantified_score + action_score + skill_score + stuffing_score
    details = (
        f"{date_hits} referencias de data, {len(quantified_lines)} bullets com numeros, "
        f"{len(action_lines)} bullets com verbos de acao e {len(skill_terms)} hard skills detectadas."
    )
    return (
        MetricResult(
            key="content_quality",
            label="Qualidade de conteudo",
            score=score,
            max_score=40,
            details=details,
        ),
        len(quantified_lines),
        len(action_lines),
    )


def line_starts_with_action_verb(line: str) -> bool:
    normalized_line = normalize_for_matching(line).lstrip("-* ")
    return any(normalized_line.startswith(f"{verb} ") for verb in ACTION_VERBS)


def repetition_penalty(text: str) -> int:
    tokens = [token for token in tokenize(text) if len(token) >= 3]
    if len(tokens) < 30:
        return 0

    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1

    max_ratio = max(counts.values()) / len(tokens)
    if max_ratio > 0.12:
        return 2
    if max_ratio > 0.08:
        return 1
    return 0


def extract_required_terms(job_text: str) -> list[str]:
    lines = split_nonempty_lines(job_text)
    candidate_lines = [line for line in lines if any(marker in normalize_for_matching(line) for marker in REQUIRED_MARKERS)]
    terms = extract_significant_terms("\n".join(candidate_lines), limit=12)
    if terms:
        return terms
    return extract_significant_terms(job_text, limit=8)


def extract_job_title(job_text: str) -> str | None:
    for line in split_nonempty_lines(job_text)[:12]:
        normalized_line = normalize_for_matching(line)
        if 2 <= len(line.split()) <= 8 and not any(marker in normalized_line for marker in REQUIRED_MARKERS):
            return line.strip()
    return None


def score_title_alignment(job_title: str | None, resume_text: str, job_text: str) -> int:
    if not job_title:
        return 7

    title_tokens = [token for token in tokenize(job_title) if len(token) >= 3]
    resume_tokens = set(tokenize(resume_text))
    title_ratio = overlap_ratio(title_tokens, list(resume_tokens))
    title_points = clamp_score(title_ratio * 10, 10)

    job_seniority = detect_seniority(job_text) or detect_seniority(job_title)
    resume_seniority = detect_seniority(resume_text)
    seniority_points = 5 if job_seniority and job_seniority == resume_seniority else 3 if not job_seniority else 0
    return title_points + seniority_points


def score_evidence_alignment(job_text: str, resume_text: str) -> int:
    job_degrees = extract_degree_terms(job_text)
    resume_degrees = extract_degree_terms(resume_text)
    degree_ratio = overlap_ratio(job_degrees, resume_degrees) if job_degrees else 1.0

    job_skills = extract_skill_phrases(job_text)[:10]
    resume_skills = extract_skill_phrases(resume_text)
    skill_ratio = overlap_ratio(job_skills, resume_skills) if job_skills else 0.6
    return clamp_score(((degree_ratio * 0.4) + (skill_ratio * 0.6)) * 15, 15)


def score_terminology_fidelity(job_text: str, resume_text: str) -> int:
    acronyms = {match.group(0) for match in UPPERCASE_ACRONYM_PATTERN.finditer(job_text)}
    if acronyms:
        acronym_hits = sum(1 for acronym in acronyms if acronym in resume_text)
        acronym_ratio = acronym_hits / len(acronyms)
    else:
        acronym_ratio = 0.6

    multiword_phrases = [phrase for phrase in extract_skill_phrases(job_text) if " " in phrase]
    if multiword_phrases:
        normalized_resume = normalize_for_matching(resume_text)
        phrase_hits = sum(1 for phrase in multiword_phrases if phrase in normalized_resume)
        phrase_ratio = phrase_hits / len(multiword_phrases)
    else:
        phrase_ratio = 0.6

    return clamp_score(((acronym_ratio + phrase_ratio) / 2) * 10, 10)
