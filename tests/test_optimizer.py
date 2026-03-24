from ats_score_resume.document_parser import ExtractedDocument
from ats_score_resume.ai_optimizer import extract_output_text
from ats_score_resume.optimizer import (
    AIRewriteRequest,
    AIRewriteResponse,
    ScoreTarget,
    default_score_target,
    optimize_resume_draft,
)
from ats_score_resume.scoring import analyze_document


def make_document(filename: str, extension: str, text: str) -> ExtractedDocument:
    return ExtractedDocument(
        filename=filename,
        extension=extension,
        raw_text=text,
        cleaned_text=text.strip(),
    )


class FakeOptimizer:
    def __init__(self, response: AIRewriteResponse) -> None:
        self.response = response
        self.calls: list[AIRewriteRequest] = []

    def rewrite_resume(self, request: AIRewriteRequest) -> AIRewriteResponse:
        self.calls.append(request)
        return self.response


def test_default_score_target_without_job_disables_job_match_goal() -> None:
    target = default_score_target(None)

    assert target.ats_score == 88
    assert target.overall_score == 88
    assert target.job_match_score is None


def test_optimize_resume_draft_reports_missing_ai_configuration() -> None:
    document = make_document(
        "resume.txt",
        ".txt",
        """
Ana Souza
ana@example.com

Experiencia
2021 - 2025
Responsavel por dashboards e relatorios.
""",
    )
    baseline_result = analyze_document(document)
    initial_draft = """
ANA SOUZA
ana@example.com

EXPERIENCIA PROFISSIONAL
2021 - 2025
- Responsavel por dashboards e relatorios.
""".strip()

    outcome = optimize_resume_draft(
        filename=document.filename,
        original_document=document,
        baseline_result=baseline_result,
        initial_draft=initial_draft,
        job_input=None,
        ai_optimizer=None,
    )

    assert outcome.reached_target is False
    assert "camada de IA" in outcome.stop_reason
    assert outcome.final_draft == initial_draft


def test_optimize_resume_draft_accepts_improving_ai_rewrite() -> None:
    document = make_document(
        "resume.txt",
        ".txt",
        """
John Doe
john@example.com
Sao Paulo, SP
linkedin.com/in/johndoe

Experience
Data Analyst - ACME
2021 - 2025
Responsible for dashboards and reporting.

Education
Bachelor in Computer Science
""",
    )
    baseline_result = analyze_document(document)
    initial_draft = """
JOHN DOE
john@example.com
Sao Paulo, SP
linkedin.com/in/johndoe

EXPERIENCIA PROFISSIONAL
Data Analyst - ACME
2021 - 2025
- Responsible for dashboards and reporting.

EDUCACAO
Bachelor in Computer Science
""".strip()
    improved_draft = """
JOHN DOE
john@example.com
Sao Paulo, SP
linkedin.com/in/johndoe

RESUMO PROFISSIONAL
Data analyst with 6 years of experience in SQL, Python, Power BI and stakeholder management.

SKILLS
Python, SQL, Power BI, Analytics

EXPERIENCIA PROFISSIONAL
Data Analyst - ACME
2021 - 2025
- Developed KPI dashboards for 12 business areas and reduced reporting time by 40%.
- Implemented SQL pipelines that improved data freshness by 25%.

EDUCACAO
Bachelor in Computer Science
""".strip()
    fake_optimizer = FakeOptimizer(
        AIRewriteResponse(
            optimized_resume=improved_draft,
            summary="Reescreveu o resumo, adicionou skills e fortaleceu os bullets com numeros.",
            applied_changes=["Adicionou resumo profissional.", "Reescreveu bullets com verbos de acao e metricas."],
            retained_job_terms=[],
            rejected_job_terms=[],
            confidence_notes=["Nao inventou experiencias ou certificacoes."],
        )
    )

    outcome = optimize_resume_draft(
        filename=document.filename,
        original_document=document,
        baseline_result=baseline_result,
        initial_draft=initial_draft,
        job_input=None,
        ai_optimizer=fake_optimizer,
        target=ScoreTarget(ats_score=80, overall_score=80, job_match_score=None),
        max_steps=1,
    )

    assert len(fake_optimizer.calls) == 1
    assert outcome.final_draft == improved_draft
    assert outcome.final_result.resume.score >= outcome.starting_result.resume.score
    assert outcome.final_result.overall_score >= outcome.starting_result.overall_score
    assert outcome.steps[0].applied_changes


def test_extract_output_text_falls_back_to_output_content() -> None:
    payload = {
        "output": [
            {
                "content": [
                    {
                        "text": '{"optimized_resume":"JOHN DOE","summary":"ok","applied_changes":[],"retained_job_terms":[],"rejected_job_terms":[],"confidence_notes":[],"stop_signal":false,"stop_reason":""}'
                    }
                ]
            }
        ]
    }

    extracted = extract_output_text(payload)

    assert '"optimized_resume":"JOHN DOE"' in extracted
