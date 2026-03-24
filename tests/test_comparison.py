from ats_score_resume.comparison import build_approved_resume_text, compare_resume_versions


def test_compare_resume_versions_highlights_changed_sections() -> None:
    original = """
Renato Rocha
renato@example.com

Resumo
Profissional com experiencia em dados.

Experiencia
2021 - 2025
- Responsavel por dashboards.

Educacao
Bacharelado em Sistemas de Informacao
""".strip()

    optimized = """
RENATO ROCHA
renato@example.com

RESUMO PROFISSIONAL
Profissional com experiencia em dados, analytics e automacao.

SKILLS
Python, SQL, Power BI

EXPERIENCIA PROFISSIONAL
2021 - 2025
- Desenvolveu dashboards para 12 areas e reduziu o tempo de reporte em 40%.

EDUCACAO
Bacharelado em Sistemas de Informacao
""".strip()

    comparison = compare_resume_versions(original, optimized)

    assert comparison.changed_section_count >= 3
    assert comparison.added_line_count >= 3
    assert comparison.removed_line_count >= 1
    assert any(section.key == "skills" for section in comparison.sections)
    assert any(
        "Power BI" in line
        for section in comparison.sections
        for line in section.added_lines
    )


def test_compare_resume_versions_keeps_header_as_comparable_section() -> None:
    original = """
Renato Rocha
renato@example.com
Sao Paulo, SP
""".strip()

    optimized = """
RENATO ROCHA
renato@example.com
Sao Paulo, SP
Senior Data Engineer
""".strip()

    comparison = compare_resume_versions(original, optimized)
    header = next(section for section in comparison.sections if section.key == "header")

    assert "Senior Data Engineer" in header.added_lines


def test_build_approved_resume_text_only_applies_selected_sections() -> None:
    original = """
Renato Rocha
renato@example.com

Resumo
Profissional com experiencia em dados.

Experiencia
- Responsavel por dashboards.
""".strip()

    proposed = """
RENATO ROCHA
renato@example.com

RESUMO PROFISSIONAL
Profissional com experiencia em dados, analytics e automacao.

SKILLS
Python, SQL, Power BI

EXPERIENCIA PROFISSIONAL
- Desenvolveu dashboards para 12 areas e reduziu o tempo de reporte em 40%.
""".strip()

    approved = build_approved_resume_text(original, proposed, ["skills"])

    assert "Python, SQL, Power BI" in approved
    assert "Profissional com experiencia em dados." in approved
    assert "Desenvolveu dashboards" not in approved
