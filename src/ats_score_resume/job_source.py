from __future__ import annotations

from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from ats_score_resume.text_utils import normalize_text


@dataclass(slots=True)
class JobInput:
    text: str
    source: str


class JobSourceError(RuntimeError):
    """Raised when a job description cannot be fetched."""


def resolve_job_input(description: str | None, url: str | None) -> JobInput | None:
    if description and description.strip():
        return JobInput(text=normalize_text(description), source="descricao manual")

    if url and url.strip():
        return JobInput(text=fetch_job_text(url.strip()), source=url.strip())

    return None


def fetch_job_text(url: str) -> str:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 ATSResumeAnalyzer/0.1"},
            timeout=12,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise JobSourceError(f"Nao foi possivel acessar a URL da vaga: {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    candidates: list[str] = []
    selectors = [
        "[class*='job']",
        "[class*='description']",
        "[class*='content']",
        "main",
        "article",
        "body",
    ]

    for selector in selectors:
        for node in soup.select(selector):
            text = normalize_text(node.get_text("\n", strip=True))
            if len(text) >= 400:
                candidates.append(text)

    text = max(candidates, key=len, default=normalize_text(soup.get_text("\n", strip=True)))
    if len(text) < 120:
        raise JobSourceError("A URL retornou pouco texto util. Cole a descricao manualmente para continuar.")

    return text
