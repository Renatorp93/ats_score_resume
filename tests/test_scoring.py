from ats_score_resume.app import apply_personalization_to_draft
from ats_score_resume.document_parser import ExtractedDocument
from ats_score_resume.exporters import build_docx_resume, build_html_resume
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
    assert "PERSONALIZACAO PARA ESTA VAGA" not in generated_resume


def test_generated_resume_rewrites_experience_into_action_bullets() -> None:
    document = make_document(
        "resume.txt",
        ".txt",
        """
Ana Souza
ana@example.com

Experiencia
Engenheira de Dados - ACME
2021 - 2025
Desenvolvimento de pipelines ETL para analytics e operacoes.
Implementacao de infraestrutura como codigo com Terraform na AWS.

Educacao
Bacharelado em Estatistica

Skills
Python, SQL, AWS, Terraform
""",
    )

    result = analyze_document(document)
    generated_resume = generate_resume_draft(document, result)
    generated_result = analyze_resume(make_document("generated.txt", ".txt", generated_resume))

    assert "- Desenvolveu pipelines ETL para analytics e operacoes." in generated_resume
    assert "- Implementou infraestrutura como codigo com Terraform na AWS." in generated_resume
    assert generated_result.action_bullet_count >= 2


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


def test_html_exporter_returns_html_document() -> None:
    html_content = build_html_resume("NOME\n\nSKILLS\nPython, SQL")

    assert "<html>" in html_content.lower()
    assert "Python, SQL" in html_content


def test_personalization_updates_title_and_skills_section() -> None:
    draft = """
ANA SOUZA
ana@example.com

RESUMO PROFISSIONAL
Profissional com experiencia em dados.

SKILLS
Python, SQL
""".strip()

    updated = apply_personalization_to_draft(draft, "Senior Data Analyst", ["devops", "mysql", "nosql"])

    assert "Senior Data Analyst" in updated.splitlines()[:4]
    assert "Python, SQL, DevOps, MySQL, NoSQL" in updated


def test_job_title_ignores_navigation_noise_from_page() -> None:
    document = make_document(
        "resume.txt",
        ".txt",
        """
Marina Rocha
marina@example.com

Resumo
Profissional com experiencia em dados e analytics.

Experiencia
2020 - 2025
- Liderou automacoes com Python.

Educacao
Bacharelado em Sistemas de Informacao

Skills
Python, SQL, Analytics
""",
    )

    job_description = """
Skip to main content
Clear text
Senior Data Analyst
Required:
- Python
- SQL
"""

    result = analyze_document(document, job_text=job_description, job_source="descricao manual")

    assert result.job_match is not None
    assert result.job_match.job_title == "Senior Data Analyst"


def test_job_title_override_is_sanitized_before_personalization() -> None:
    document = make_document(
        "resume.txt",
        ".txt",
        """
Joao Lima
joao@example.com

Resumo
Profissional com experiencia em engenharia de dados.

Experiencia
2021 - 2025
- Implementou pipelines com Python e SQL.

Educacao
Bacharelado em Computacao

Skills
Python, SQL, AWS
""",
    )

    result = analyze_document(
        document,
        job_text="Descricao longa da vaga",
        job_source="https://example.com/job",
        job_title_override="GFT Technologies hiring Engenharia de Dados AWS Senior - ID 121504 | LinkedIn",
    )

    assert result.job_match is not None
    assert result.job_match.job_title == "Engenharia de Dados AWS Senior"


def test_job_match_ignores_job_board_noise_terms() -> None:
    document = make_document(
        "resume.txt",
        ".txt",
        """
Renato Rocha
renato@example.com

Resumo
Profissional com experiencia em AWS, Python, SQL e Kubernetes.

Experiencia
2021 - 2025
- Implementou pipelines de dados na AWS.

Educacao
Bacharelado em Sistemas de Informacao

Skills
AWS, Python, SQL, Kubernetes
""",
    )

    job_description = """
Clear text
Engenharia de Dados AWS Senior
Brazil - shared 10 months ago - jobs
Required:
- AWS
- Python
- SQL
- Kubernetes
"""

    result = analyze_document(document, job_text=job_description, job_source="linkedin")

    assert result.job_match is not None
    assert "brazil" not in result.job_match.missing_keywords
    assert "engineer" not in result.job_match.missing_keywords
    assert "ago" not in result.job_match.missing_keywords
    assert "jobs" not in result.job_match.missing_keywords
