from __future__ import annotations

import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from ats_score_resume.text_utils import normalize_text


@dataclass(slots=True)
class JobInput:
    text: str
    source: str
    title: str | None = None


class JobSourceError(RuntimeError):
    """Raised when a job description cannot be fetched."""


def resolve_job_input(description: str | None, url: str | None) -> JobInput | None:
    if description and description.strip():
        return JobInput(text=normalize_text(description), source="descrição manual")

    if url and url.strip():
        return fetch_job_input(url.strip())

    return None


def fetch_job_input(url: str) -> JobInput:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 ATSResumeAnalyzer/0.1"},
            timeout=12,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise JobSourceError(f"Não foi possível acessar a URL da vaga: {exc}") from exc

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
        raise JobSourceError("A URL retornou pouco texto útil. Cole a descrição manualmente para continuar.")

    return JobInput(
        text=text,
        source=url,
        title=extract_job_page_title(soup),
    )


def extract_job_page_title(soup: BeautifulSoup) -> str | None:
    candidates: list[str] = []

    meta_selectors = [
        ("meta", {"property": "og:title"}),
        ("meta", {"name": "title"}),
        ("meta", {"property": "twitter:title"}),
    ]
    for tag_name, attrs in meta_selectors:
        tag = soup.find(tag_name, attrs=attrs)
        if tag and tag.get("content"):
            candidates.append(tag["content"])

    if soup.title and soup.title.string:
        candidates.append(soup.title.string)

    for heading in soup.find_all(["h1", "h2"], limit=5):
        text = normalize_text(heading.get_text(" ", strip=True))
        if text:
            candidates.append(text)

    for candidate in candidates:
        cleaned = sanitize_title_candidate(candidate)
        if cleaned:
            return cleaned

    return None


def sanitize_title_candidate(value: str) -> str | None:
    cleaned = normalize_text(value)
    if not cleaned:
        return None

    cleaned = cleaned.replace("Vaga para ", "").replace("Vaga de ", "")
    cleaned = cleaned.replace("Clear text", "").strip()
    cleaned = normalize_text(cleaned)
    cleaned = re.sub(r"^.+?\bhiring\b\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^.+?\bcontrata(?:ndo)?\b\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.split("|")[0].strip()
    cleaned = cleaned.split("–")[0].strip() if "linkedin" in cleaned.lower() else cleaned
    cleaned = cleaned.split(" at ")[0].strip()
    cleaned = cleaned.split(" na ")[0].strip() if cleaned.lower().count(" na ") == 1 and len(cleaned.split()) > 5 else cleaned
    cleaned = re.sub(r"\s*-\s*ID\s*\d+\b.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("  ", " ").strip(" -")

    cleaned = normalize_text(cleaned)
    if len(cleaned.split()) < 2:
        return None

    return cleaned
