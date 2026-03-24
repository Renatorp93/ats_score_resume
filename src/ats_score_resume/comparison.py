from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from ats_score_resume.scoring import display_section_name, identify_section
from ats_score_resume.text_utils import split_nonempty_lines


@dataclass(slots=True)
class SectionComparison:
    key: str
    label: str
    original_lines: list[str]
    optimized_lines: list[str]
    added_lines: list[str]
    removed_lines: list[str]
    similarity_ratio: int


@dataclass(slots=True)
class ResumeComparison:
    sections: list[SectionComparison]
    added_line_count: int
    removed_line_count: int
    changed_section_count: int


def compare_resume_versions(original_text: str, optimized_text: str) -> ResumeComparison:
    original_sections = extract_resume_sections_for_comparison(original_text)
    optimized_sections = extract_resume_sections_for_comparison(optimized_text)

    section_order = ordered_keys(original_sections, optimized_sections)
    comparisons: list[SectionComparison] = []
    added_total = 0
    removed_total = 0
    changed_sections = 0

    for key in section_order:
        original_lines = original_sections.get(key, [])
        optimized_lines = optimized_sections.get(key, [])
        added_lines = [line for line in optimized_lines if line not in original_lines]
        removed_lines = [line for line in original_lines if line not in optimized_lines]
        similarity_ratio = similarity_percentage(original_lines, optimized_lines)
        if added_lines or removed_lines:
            changed_sections += 1
        added_total += len(added_lines)
        removed_total += len(removed_lines)
        comparisons.append(
            SectionComparison(
                key=key,
                label=display_section_name(key) if key != "header" else "Cabecalho",
                original_lines=original_lines,
                optimized_lines=optimized_lines,
                added_lines=added_lines,
                removed_lines=removed_lines,
                similarity_ratio=similarity_ratio,
            )
        )

    return ResumeComparison(
        sections=comparisons,
        added_line_count=added_total,
        removed_line_count=removed_total,
        changed_section_count=changed_sections,
    )


def extract_resume_sections_for_comparison(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_key = "header"

    for line in split_nonempty_lines(text):
        section_key = identify_section(line)
        if section_key:
            current_key = section_key
            sections.setdefault(section_key, [])
            continue
        sections.setdefault(current_key, []).append(line)

    return {key: value for key, value in sections.items() if value}


def ordered_keys(left: dict[str, list[str]], right: dict[str, list[str]]) -> list[str]:
    ordered: list[str] = []
    for source in (left, right):
        for key in source:
            if key not in ordered:
                ordered.append(key)
    return ordered


def similarity_percentage(left: list[str], right: list[str]) -> int:
    left_text = "\n".join(left)
    right_text = "\n".join(right)
    if not left_text and not right_text:
        return 100
    if not left_text or not right_text:
        return 0
    return round(SequenceMatcher(a=left_text, b=right_text).ratio() * 100)
