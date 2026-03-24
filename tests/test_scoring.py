from ats_score_resume.document_parser import ExtractedDocument
from ats_score_resume.scoring import analyze_document, analyze_resume


def make_document(filename: str, extension: str, text: str) -> ExtractedDocument:
    return ExtractedDocument(
        filename=filename,
        extension=extension,
        raw_text=text,
        cleaned_text=text.strip(),
    )


def test_resume_with_core_sections_scores_reasonably_well() -> None:
    document = make_document(
        "resume.docx",
        ".docx",
        """
John Doe
john@example.com
+55 11 99999-0000
Sao Paulo, SP
linkedin.com/in/johndoe

Summary
Data analyst with 6 years of experience in SQL, Python, Power BI and stakeholder management.

Experience
Data Analyst - ACME
2021 - 2025
- Developed KPI dashboards for 12 business areas and reduced reporting time by 40%.
- Implemented SQL pipelines that improved data freshness by 25%.

Education
Bachelor in Computer Science

Skills
SQL, Python, Power BI, Excel, Tableau, Analytics
""",
    )

    result = analyze_resume(document)

    assert result.score >= 70
    assert "skills" in result.detected_sections
    assert result.quantified_achievement_count >= 1


def test_resume_missing_sections_gets_actionable_suggestions() -> None:
    document = make_document(
        "resume.pdf",
        ".pdf",
        """
Jane Doe
jane@example.com

Profile
Professional with experience in operations and customer service.

Experience
2022 - 2024
Responsible for customer support and issue tracking.
""",
    )

    result = analyze_document(document)

    assert result.resume.score < 70
    assert any("skills" in suggestion.title.lower() for suggestion in result.suggestions)
    assert any("docx" in suggestion.details.lower() for suggestion in result.suggestions)


def test_job_match_finds_missing_keywords() -> None:
    document = make_document(
        "resume.txt",
        ".txt",
        """
Maria Silva
maria@example.com
+55 11 98888-7777

Resumo
Profissional de dados com experiencia em Python e SQL.

Experiencia
2020 - 2025
- Implementou pipelines de dados com Python e SQL.

Formacao
Bacharelado em Engenharia

Habilidades
Python, SQL, Docker
""",
    )

    job_description = """
Senior Data Engineer
Required:
- Python
- SQL
- AWS
- Spark
- Airflow
"""

    result = analyze_document(document, job_text=job_description, job_source="descricao manual")

    assert result.job_match is not None
    assert "aws" in result.job_match.missing_keywords or "aws" in result.job_match.missing_required_terms
    assert result.overall_score <= 85
