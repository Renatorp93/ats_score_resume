from ats_score_resume.document_parser import ExtractedDocument
from ats_score_resume.exporters import build_docx_resume
from ats_score_resume.scoring import analyze_document, analyze_resume, generate_resume_draft


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


def test_generated_resume_creates_sections_and_customization_notes() -> None:
    document = make_document(
        "resume.txt",
        ".txt",
        """
Ana Souza
ana@example.com
+55 11 97777-6666

Experiencia
Analista de Dados - ACME
2021 - 2025
Implementou dashboards para operacoes.

Educacao
Bacharelado em Estatistica
""",
    )

    job_description = """
Senior Data Analyst
Required:
- SQL
- Power BI
- Python
"""

    result = analyze_document(document, job_text=job_description, job_source="descricao manual")
    generated_resume = generate_resume_draft(document, result)

    assert "RESUMO PROFISSIONAL" in generated_resume
    assert "SKILLS" in generated_resume
    assert "PERSONALIZACAO PARA ESTA VAGA" in generated_resume
    assert "SQL" in generated_resume or "sql" in generated_resume


def test_competencias_tecnicas_is_detected_as_skills_section() -> None:
    document = make_document(
        "resume.txt",
        ".txt",
        """
Carlos Lima
carlos@example.com

Resumo
Profissional com experiencia em analytics, cloud e automacao.

Experiencia
2021 - 2024
- Liderou melhorias de dados em times de produto.

Educacao
Bacharelado em Sistemas de Informacao

Competencias Tecnicas
Python, SQL, AWS, API, CI/CD
""",
    )

    result = analyze_document(document)

    assert "skills" in result.resume.detected_sections
    assert result.resume.section_headings["skills"] == "Competencias Tecnicas"
    assert any("Skills" in suggestion.details for suggestion in result.suggestions)


def test_docx_exporter_returns_document_bytes() -> None:
    content = "NOME SOBRENOME\n\nSKILLS\nPython, SQL"
    docx_bytes = build_docx_resume(content)

    assert len(docx_bytes) > 100
