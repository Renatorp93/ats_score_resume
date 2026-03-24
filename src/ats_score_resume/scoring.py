from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

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
        "technical competencies",
        "technical competence",
        "core skills",
        "hard skills",
        "key skills",
        "core competencies",
        "competencies",
        "habilidades",
        "competencias",
        "competencias tecnicas",
        "habilidades tecnicas",
        "ferramentas",
        "ferramentas e tecnologias",
        "tecnologias",
        "stack tecnica",
        "conhecimentos",
    ),
    "certifications": ("certifications", "licenses", "certificacoes", "cursos"),
}

CANONICAL_SKILL_HEADINGS = {"skills", "technical skills"}
SECTION_DISPLAY_NAMES = {
    "summary": "Resumo profissional",
    "experience": "Experiência profissional",
    "education": "Educação",
    "skills": "Skills",
    "certifications": "Certificações",
}
NOISE_JOB_TITLE_LINES = {
    "skip to main content",
    "start of main content",
    "main content",
    "clear text",
    "job description",
    "apply now",
    "sign in",
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
    section_headings: dict[str, str]
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
    section_headings = detect_section_headings(raw_lines)
    detected_sections = list(section_headings.keys())
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
        section_headings=section_headings,
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
            label="Palavras-chave da vaga",
            score=keyword_score,
            max_score=35,
            details=f"{len(matched_keywords)} de {len(job_terms) or 0} termos principais aparecem no currículo.",
        ),
        MetricResult(
            key="required_terms",
            label="Requisitos obrigatórios",
            score=required_score,
            max_score=25,
            details=f"{len(required_overlap)} de {len(required_terms) or 0} requisitos explícitos aparecem no currículo.",
        ),
        MetricResult(
            key="title_alignment",
            label="Título e senioridade",
            score=title_score,
            max_score=15,
            details=f"Título da vaga identificado como: {job_title or 'não identificado'}.",
        ),
        MetricResult(
            key="evidence_alignment",
            label="Experiência e formação",
            score=experience_education_score,
            max_score=15,
            details="Verifica se termos de experiência e formação da vaga aparecem no currículo.",
        ),
        MetricResult(
            key="terminology_fidelity",
            label="Termos técnicos",
            score=terminology_score,
            max_score=10,
            details="Premia siglas e frases técnicas que batem exatamente com a vaga.",
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
                title="Considere manter uma versão DOCX do currículo",
                details="PDF pode funcionar bem, mas DOCX costuma ser a opção mais previsível para leitura em ATS quando a vaga não exige PDF.",
            )
        )

    if "skills" in resume.missing_sections:
        if len(resume.keyword_terms) >= 6:
            suggestions.append(
                Suggestion(
                    priority="alta",
                    title="Renomeie a seção de competências para Skills ou Technical Skills",
                    details="Seu currículo parece ter termos técnicos relevantes, mas vale usar um título mais padrão para facilitar a leitura por ATS.",
                )
            )
        else:
            suggestions.append(
                Suggestion(
                    priority="alta",
                    title="Crie uma seção de skills dedicada",
                    details="Liste hard skills, ferramentas, linguagens, metodologias e certificações em uma seção clara para facilitar o match por keywords.",
                )
            )

    skill_heading = resume.section_headings.get("skills")
    if skill_heading and normalize_for_matching(skill_heading) not in CANONICAL_SKILL_HEADINGS:
        suggestions.append(
            Suggestion(
                priority="media",
                title="Use um título mais padrão para a seção de skills",
                details=f'A seção "{skill_heading}" foi reconhecida, mas "Skills" ou "Technical Skills" tende a ser mais universal para ATS.',
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
                title="Inclua resultados mensuráveis nas experiências",
                details="Troque descrições genéricas por bullets com números, percentuais, prazos, volumes ou economias geradas.",
            )
        )

    if resume.action_bullet_count < 3:
        suggestions.append(
            Suggestion(
                priority="media",
                title="Reescreva experiências com verbos de ação",
                details="Comece bullets com verbos como implementou, liderou, desenvolveu, improved ou managed para deixar o impacto mais claro.",
            )
        )

    if resume.format_risks:
        suggestions.append(
            Suggestion(
                priority="media",
                title="Simplifique a formatação para reduzir risco de parsing",
                details="Evite excesso de pipes, tabs, ícones e layouts que pareçam tabelas ou colunas.",
            )
        )

    if job_match and job_match.missing_required_terms:
        suggestions.append(
            Suggestion(
                priority="alta",
                title="Cubra os requisitos obrigatórios da vaga com a mesma terminologia",
                details=f"Considere incorporar evidências para: {', '.join(job_match.missing_required_terms[:5])}.",
            )
        )

    if job_match and job_match.missing_keywords:
        suggestions.append(
            Suggestion(
                priority="alta",
                title="Aumente a cobertura de keywords da vaga",
                details=f"Os principais termos ainda ausentes são: {', '.join(job_match.missing_keywords[:6])}.",
            )
        )

    return suggestions[:7]


def generate_resume_draft(document: ExtractedDocument, result: AnalysisResult) -> str:
    header_lines, sections = parse_resume_sections(document.cleaned_text)
    name, contacts = extract_resume_header(header_lines)

    blocks = [
        build_header_block(name, contacts),
        build_summary_block(sections.get("summary", []), result),
        build_skills_block(sections.get("skills", []), result),
        build_experience_block(sections.get("experience", []), result),
        build_education_block(sections.get("education", [])),
    ]

    certifications_block = build_optional_section("CERTIFICAÇÕES", sections.get("certifications", []))
    if certifications_block:
        blocks.append(certifications_block)

    return "\n\n".join(block for block in blocks if block).strip()


def parse_resume_sections(text: str) -> tuple[list[str], dict[str, list[str]]]:
    header_lines: list[str] = []
    sections: dict[str, list[str]] = {}
    current_section: str | None = None

    for raw_line in split_nonempty_lines(text):
        section_name = identify_section(raw_line)
        if section_name:
            current_section = section_name
            sections.setdefault(section_name, [])
            continue

        if current_section:
            sections.setdefault(current_section, []).append(raw_line.strip())
        else:
            header_lines.append(raw_line.strip())

    return header_lines, sections


def identify_section(line: str) -> str | None:
    normalized_line = normalize_for_matching(line)
    for section, aliases in SECTION_ALIASES.items():
        if matches_heading(normalized_line, aliases):
            return section
    return None


def extract_resume_header(header_lines: list[str]) -> tuple[str, list[str]]:
    if not header_lines:
        return "NOME SOBRENOME", []

    name = header_lines[0]
    contacts = header_lines[1:]
    if EMAIL_PATTERN.search(name) or PHONE_PATTERN.search(name):
        name = "NOME SOBRENOME"
        contacts = header_lines
    return name, contacts[:4]


def build_header_block(name: str, contacts: list[str]) -> str:
    lines = [name.upper()]
    lines.extend(contacts)
    return "\n".join(lines)


def build_summary_block(summary_lines: list[str], result: AnalysisResult) -> str:
    if summary_lines:
        summary_text = " ".join(line.strip("- ").strip() for line in summary_lines if line.strip())
    else:
        focus_terms = result.resume.keyword_terms[:4]
        if result.job_match and result.job_match.job_title:
            summary_text = (
                f"Profissional com experiência em {format_list_for_sentence(focus_terms)} "
                f"e foco em oportunidades de {result.job_match.job_title}."
            )
        else:
            summary_text = (
                f"Profissional com experiência em {format_list_for_sentence(focus_terms)} "
                "e foco em resultados, clareza de skills e compatibilidade com ATS."
            )

    if result.resume.quantified_achievement_count < 2:
        summary_text = (
            f"{summary_text} "
            "Inclua um resultado numérico real no resumo para reforçar impacto."
        ).strip()

    return f"RESUMO PROFISSIONAL\n{summary_text}"


def build_skills_block(skill_lines: list[str], result: AnalysisResult) -> str:
    existing_skills = collect_inline_items(skill_lines)
    for term in result.resume.keyword_terms[:10]:
        if term not in existing_skills:
            existing_skills.append(term)

    if result.job_match:
        for term in result.job_match.matched_keywords[:6]:
            if term not in existing_skills:
                existing_skills.append(term)

    if not existing_skills:
        existing_skills = [
            "Adicione aqui suas hard skills principais",
            "Ex.: Python, SQL, Excel, Power BI, Gestão de Projetos",
        ]

    return "SKILLS\n" + ", ".join(existing_skills[:16])


def build_experience_block(experience_lines: list[str], result: AnalysisResult) -> str:
    if not experience_lines:
        experience_lines = [
            "[Cargo] - [Empresa]",
            "[Período]",
            "- Descreva uma entrega relevante com verbo de ação.",
            "- Adicione um resultado numérico real: ex. reduzi prazo em 20%.",
        ]

    formatted_lines: list[str] = []
    for line in experience_lines:
        clean_line = line.strip()
        if not clean_line:
            continue
        if looks_like_resume_heading(clean_line) or DATE_PATTERN.search(clean_line):
            formatted_lines.append(clean_line)
            continue
        if clean_line.startswith(("-", "*")):
            formatted_lines.append(clean_line)
            continue
        if line_starts_with_action_verb(clean_line):
            formatted_lines.append(f"- {clean_line}")
            continue
        formatted_lines.append(clean_line if len(clean_line.split()) <= 5 else f"- {clean_line}")

    if result.resume.quantified_achievement_count < 2:
        formatted_lines.append("- [Adicionar um bullet com impacto mensurável, usando número ou percentual real.]")

    return "EXPERIÊNCIA PROFISSIONAL\n" + "\n".join(formatted_lines)


def build_education_block(education_lines: list[str]) -> str:
    if not education_lines:
        education_lines = [
            "[Curso ou grau]",
            "[Instituição] - [Ano de conclusão ou previsão]",
        ]

    return "EDUCAÇÃO\n" + "\n".join(education_lines)


def build_optional_section(title: str, lines: list[str]) -> str:
    if not lines:
        return ""
    return f"{title}\n" + "\n".join(lines)


def collect_inline_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        for item in re.split(r"[;,|]", line):
            clean_item = item.strip(" -*")
            if clean_item and clean_item not in items:
                items.append(clean_item)
    return items


def format_list_for_sentence(items: list[str]) -> str:
    if not items:
        return "resultados e melhoria continua"
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} e {items[1]}"
    return ", ".join(items[:-1]) + f" e {items[-1]}"


def looks_like_resume_heading(line: str) -> bool:
    normalized = normalize_for_matching(line)
    return bool(identify_section(normalized)) or " - " in line or line.isupper()


def detect_sections(lines: list[str]) -> list[str]:
    return list(detect_section_headings(lines).keys())


def detect_section_headings(lines: list[str]) -> dict[str, str]:
    detected: dict[str, str] = {}
    for line in lines:
        section = identify_section(line)
        if section and section not in detected:
            detected[section] = line.strip()
    return detected


def matches_heading(line: str, aliases: tuple[str, ...]) -> bool:
    trimmed = normalize_for_matching(line).strip(":- ").lower()
    word_count = len(trimmed.split())
    return any(
        trimmed == alias
        or trimmed.startswith(f"{alias}:")
        or (word_count <= 5 and re.search(rf"\b{re.escape(alias)}\b", trimmed))
        for alias in aliases
    )


def detect_format_risks(document: ExtractedDocument, lines: list[str]) -> list[str]:
    risks: list[str] = []
    raw_text = document.raw_text
    pipe_lines = sum(1 for line in lines if "|" in line)
    tab_lines = sum(1 for line in raw_text.splitlines() if "\t" in line)
    icon_hits = len(re.findall(r"[•●▪◆■♦★☎✉📧📱🔗]", raw_text))

    if pipe_lines >= 2:
        risks.append("ha sinais de colunas ou tabelas representadas por pipes")
    if tab_lines >= 2:
        risks.append("há muitos tabs, o que pode indicar layout difícil para parsing")
    if icon_hits >= 3:
        risks.append("ha varios icones ou glifos decorativos")
    if len(document.cleaned_text) < 500:
        risks.append("o texto extraído ficou curto para um currículo completo")

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
        f"Formato {document.extension}, texto extraído com {char_count} caracteres, "
        f"{len(detected_sections)} seções principais detectadas e {len(format_risks)} alertas de formatação."
    )
    return MetricResult(
        key="parsing_format",
        label="Leitura pelo ATS",
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
        f"Seções detectadas: {', '.join(detected_sections) or 'nenhuma seção padrão detectada'}."
    )
    return MetricResult(
        key="completeness",
        label="Estrutura do currículo",
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
        f"{date_hits} referências de data, {len(quantified_lines)} bullets com números, "
        f"{len(action_lines)} bullets com verbos de ação e {len(skill_terms)} hard skills detectadas."
    )
    return (
        MetricResult(
            key="content_quality",
            label="Força do conteúdo",
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
        if (
            2 <= len(line.split()) <= 8
            and not any(marker in normalized_line for marker in REQUIRED_MARKERS)
            and looks_like_job_title(line)
        ):
            return line.strip()
    return None


def looks_like_job_title(line: str) -> bool:
    normalized = normalize_for_matching(line)
    if normalized in NOISE_JOB_TITLE_LINES:
        return False
    if any(token in normalized for token in ("cookie", "privacy", "search", "navigation", "content")):
        return False
    return True


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


def display_section_name(section_key: str) -> str:
    return SECTION_DISPLAY_NAMES.get(section_key, section_key.title())


def metric_to_dict(metric: MetricResult) -> dict[str, Any]:
    return {
        "label": metric.label,
        "score": metric.score,
        "max_score": metric.max_score,
        "details": metric.details,
    }
