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
class ResumeSection:
    key: str
    label: str
    heading: str | None
    lines: list[str]


@dataclass(slots=True)
class ResumeComparison:
    sections: list[SectionComparison]
    added_line_count: int
    removed_line_count: int
    changed_section_count: int


def compare_resume_versions(original_text: str, optimized_text: str) -> ResumeComparison:
    original_sections = {section.key: section.lines for section in extract_resume_sections_for_comparison(original_text)}
    optimized_sections = {section.key: section.lines for section in extract_resume_sections_for_comparison(optimized_text)}

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


def extract_resume_sections_for_comparison(text: str) -> list[ResumeSection]:
    sections: list[ResumeSection] = []
    current_key = "header"
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in split_nonempty_lines(text):
        section_key = detect_comparison_heading(line)
        if section_key:
            if current_heading is not None or current_lines:
                sections.append(
                    ResumeSection(
                        key=current_key,
                        label=display_section_name(current_key) if current_key != "header" else "Cabecalho",
                        heading=current_heading,
                        lines=current_lines,
                    )
                )
            current_key = section_key
            current_heading = line.strip()
            current_lines = []
            continue
        current_lines.append(line)

    if current_heading is not None or current_lines:
        sections.append(
            ResumeSection(
                key=current_key,
                label=display_section_name(current_key) if current_key != "header" else "Cabecalho",
                heading=current_heading,
                lines=current_lines,
            )
        )

    return [section for section in sections if section.lines]


def build_approved_resume_text(original_text: str, proposed_text: str, approved_keys: list[str]) -> str:
    original_sections = {section.key: section for section in extract_resume_sections_for_comparison(original_text)}
    proposed_sections = {section.key: section for section in extract_resume_sections_for_comparison(proposed_text)}
    ordered = ordered_keys(
        {section.key: section.lines for section in original_sections.values()},
        {section.key: section.lines for section in proposed_sections.values()},
    )

    blocks: list[str] = []
    for key in ordered:
        if key in approved_keys and key in proposed_sections:
            section = proposed_sections[key]
        elif key in original_sections:
            section = original_sections[key]
        elif key in proposed_sections:
            section = proposed_sections[key]
        else:
            continue

        if section.key == "header":
            block = "\n".join(section.lines).strip()
        else:
            heading = section.heading or section.label.upper()
            body = "\n".join(section.lines).strip()
            block = heading if not body else f"{heading}\n{body}"
        if block.strip():
            blocks.append(block.strip())

    return "\n\n".join(blocks).strip()


def ordered_keys(left: dict[str, list[str]], right: dict[str, list[str]]) -> list[str]:
    ordered: list[str] = []
    for source in (left, right):
        for key in source:
            if key not in ordered:
                ordered.append(key)
    return ordered


def detect_comparison_heading(line: str) -> str | None:
    trimmed = line.strip()
    if trimmed.endswith(".") or len(trimmed.split()) > 4:
        return None
    return identify_section(trimmed)


def similarity_percentage(left: list[str], right: list[str]) -> int:
    left_text = "\n".join(left)
    right_text = "\n".join(right)
    if not left_text and not right_text:
        return 100
    if not left_text or not right_text:
        return 0
    return round(SequenceMatcher(a=left_text, b=right_text).ratio() * 100)
