from __future__ import annotations

import re
import unicodedata
from collections import Counter

STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "com",
    "como",
    "da",
    "das",
    "de",
    "del",
    "do",
    "dos",
    "e",
    "em",
    "for",
    "from",
    "in",
    "into",
    "na",
    "nas",
    "no",
    "nos",
    "o",
    "of",
    "on",
    "or",
    "para",
    "por",
    "the",
    "to",
    "um",
    "uma",
    "with",
}

COMMON_WORDS = {
    "about",
    "after",
    "anos",
    "application",
    "candidate",
    "company",
    "curriculo",
    "desenvolvimento",
    "experience",
    "experiencia",
    "function",
    "historico",
    "improvement",
    "job",
    "leadership",
    "melhoria",
    "objetivo",
    "position",
    "professional",
    "projeto",
    "projetos",
    "qualidade",
    "quality",
    "requirements",
    "responsible",
    "resume",
    "skills",
    "sobre",
    "team",
    "trabalho",
    "vaga",
    "worked",
}

SKILL_PHRASES = (
    "agile",
    "airflow",
    "analytics",
    "api",
    "aws",
    "azure",
    "bi",
    "business intelligence",
    "ci/cd",
    "cloud",
    "crm",
    "css",
    "customer success",
    "data analysis",
    "data engineering",
    "data science",
    "design",
    "devops",
    "django",
    "docker",
    "excel",
    "fastapi",
    "figma",
    "flask",
    "gcp",
    "git",
    "github",
    "golang",
    "google analytics",
    "html",
    "java",
    "javascript",
    "jira",
    "kanban",
    "kotlin",
    "kubernetes",
    "lead generation",
    "linux",
    "machine learning",
    "marketing",
    "mysql",
    "node",
    "node.js",
    "nosql",
    "postgresql",
    "power bi",
    "product management",
    "product owner",
    "project management",
    "python",
    "pytorch",
    "react",
    "recrutamento",
    "recruiting",
    "sales",
    "salesforce",
    "sap",
    "scrum",
    "seo",
    "sql",
    "spark",
    "spring boot",
    "tableau",
    "tensorflow",
    "typescript",
    "ux",
)

DEGREE_TERMS = (
    "bachelor",
    "bacharelado",
    "degree",
    "engenharia",
    "graduacao",
    "licenciatura",
    "master",
    "mba",
    "mestrado",
    "phd",
    "pos-graduacao",
    "tecnologo",
)

SENIORITY_TERMS = ("estagio", "intern", "junior", "jr", "pleno", "mid", "senior", "sr", "lead", "principal")

ACTION_VERBS = (
    "achieved",
    "analyzed",
    "built",
    "coordinated",
    "created",
    "delivered",
    "designed",
    "developed",
    "grew",
    "implemented",
    "improved",
    "increased",
    "launched",
    "led",
    "managed",
    "optimized",
    "reduced",
    "resolved",
    "analisou",
    "aumentou",
    "coordenou",
    "criou",
    "desenvolveu",
    "entregou",
    "estruturou",
    "gerenciou",
    "implementou",
    "liderou",
    "melhorou",
    "otimizou",
    "reduziu",
)

REQUIRED_MARKERS = (
    "must",
    "required",
    "requirements",
    "mandatory",
    "need to have",
    "necessario",
    "necessaria",
    "obrigatorio",
    "obrigatoria",
    "requisito",
    "requisitos",
)

WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#./-]{1,}")


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def normalize_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def normalize_for_matching(value: str) -> str:
    value = strip_accents(value.lower())
    value = re.sub(r"[^a-z0-9+#./\n -]", " ", value)
    value = re.sub(r"[ \t]+", " ", value)
    return value.strip()


def split_nonempty_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def tokenize(value: str) -> list[str]:
    return [token.lower() for token in WORD_RE.findall(strip_accents(value.lower()))]


def keyword_counter(value: str) -> Counter[str]:
    tokens = [
        token
        for token in tokenize(value)
        if len(token) >= 2 and token not in STOPWORDS and token not in COMMON_WORDS and not token.isdigit()
    ]
    return Counter(tokens)


def extract_skill_phrases(value: str) -> list[str]:
    lowered = normalize_for_matching(value)
    return [phrase for phrase in SKILL_PHRASES if phrase in lowered]


def extract_degree_terms(value: str) -> list[str]:
    lowered = normalize_for_matching(value)
    return [term for term in DEGREE_TERMS if term in lowered]


def detect_seniority(value: str) -> str | None:
    lowered = normalize_for_matching(value)
    for term in SENIORITY_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", lowered):
            return term
    return None


def extract_significant_terms(value: str, limit: int = 20) -> list[str]:
    counter = keyword_counter(value)
    ranked = [token for token, _ in counter.most_common(limit * 2)]
    phrases = extract_skill_phrases(value)
    ordered: list[str] = []

    for item in [*phrases, *ranked]:
        if item not in ordered:
            ordered.append(item)
        if len(ordered) >= limit:
            break

    return ordered


def overlap_ratio(left: list[str], right: list[str]) -> float:
    if not left:
        return 0.0
    right_set = set(right)
    matches = sum(1 for item in left if item in right_set)
    return matches / len(left)


def clamp_score(score: float, max_score: int) -> int:
    return max(0, min(max_score, round(score)))
