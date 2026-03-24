from __future__ import annotations

from dataclasses import dataclass

from ats_score_resume.document_parser import ExtractedDocument
from ats_score_resume.job_source import JobInput
from ats_score_resume.scoring import AnalysisResult, MetricResult, analyze_document

DEFAULT_ATS_TARGET = 88
DEFAULT_JOB_MATCH_TARGET = 72
DEFAULT_OVERALL_TARGET = 84
DEFAULT_MAX_OPTIMIZATION_STEPS = 3


@dataclass(slots=True)
class ScoreTarget:
    ats_score: int = DEFAULT_ATS_TARGET
    overall_score: int = DEFAULT_OVERALL_TARGET
    job_match_score: int | None = DEFAULT_JOB_MATCH_TARGET


@dataclass(slots=True)
class ScoreChange:
    label: str
    before: int
    after: int
    max_score: int

    @property
    def delta(self) -> int:
        return self.after - self.before


@dataclass(slots=True)
class OptimizationStep:
    iteration: int
    source: str
    summary: str
    before_result: AnalysisResult
    after_result: AnalysisResult
    applied_changes: list[str]
    retained_job_terms: list[str]
    rejected_job_terms: list[str]
    confidence_notes: list[str]
    stop_signal: bool = False
    stop_reason: str = ""


@dataclass(slots=True)
class OptimizationOutcome:
    baseline_result: AnalysisResult
    starting_result: AnalysisResult
    final_result: AnalysisResult
    initial_draft: str
    final_draft: str
    target: ScoreTarget
    steps: list[OptimizationStep]
    reached_target: bool
    stop_reason: str
    continue_with_job: bool | None


@dataclass(slots=True)
class AIRewriteRequest:
    original_resume: str
    current_draft: str
    current_result: AnalysisResult
    target: ScoreTarget
    gap_hints: list[str]
    job_text: str = ""
    job_title: str = ""
    confirmed_terms: list[str] | None = None
    confirmed_title: str | None = None


@dataclass(slots=True)
class AIRewriteResponse:
    optimized_resume: str
    summary: str
    applied_changes: list[str]
    retained_job_terms: list[str]
    rejected_job_terms: list[str]
    confidence_notes: list[str]
    stop_signal: bool = False
    stop_reason: str = ""


class ResumeOptimizerProtocol:
    def rewrite_resume(self, request: AIRewriteRequest) -> AIRewriteResponse:
        raise NotImplementedError


def default_score_target(job_input: JobInput | None) -> ScoreTarget:
    if job_input and job_input.text.strip():
        return ScoreTarget()
    return ScoreTarget(overall_score=DEFAULT_ATS_TARGET, job_match_score=None)


def analyze_resume_text(
    filename: str,
    resume_text: str,
    job_input: JobInput | None = None,
) -> AnalysisResult:
    document = ExtractedDocument(
        filename=filename,
        extension=".txt",
        raw_text=resume_text,
        cleaned_text=resume_text.strip(),
    )
    return analyze_document(
        document=document,
        job_text=job_input.text if job_input else None,
        job_source=job_input.source if job_input else "",
        job_title_override=job_input.title if job_input else None,
    )


def target_gap_summary(result: AnalysisResult, target: ScoreTarget) -> list[str]:
    gaps: list[str] = []
    if result.resume.score < target.ats_score:
        gaps.append(f"Elevar a base ATS de {result.resume.score} para pelo menos {target.ats_score}.")
    if target.job_match_score is not None and result.job_match and result.job_match.score < target.job_match_score:
        gaps.append(
            f"Elevar a aderencia a vaga de {result.job_match.score} para pelo menos {target.job_match_score}."
        )
    if result.overall_score < target.overall_score:
        gaps.append(f"Elevar o score geral de {result.overall_score} para pelo menos {target.overall_score}.")

    if result.resume.action_bullet_count < 4:
        gaps.append("Reforcar bullets iniciando com verbos de acao.")
    if result.resume.quantified_achievement_count < 3:
        gaps.append("Destacar mais entregas com numeros reais.")
    if result.resume.missing_sections:
        section_names = ", ".join(result.resume.missing_sections)
        gaps.append(f"Cobrir ou padronizar secoes ausentes: {section_names}.")
    if result.job_match and result.job_match.missing_required_terms:
        gaps.append("Trazer requisitos da vaga para resumo, experiencia ou skills sem inventar fatos.")
    return gaps


def metric_changes(before: list[MetricResult], after: list[MetricResult]) -> list[ScoreChange]:
    before_map = {metric.key: metric for metric in before}
    changes: list[ScoreChange] = []
    for metric in after:
        previous = before_map.get(metric.key)
        if not previous or previous.score == metric.score:
            continue
        changes.append(
            ScoreChange(
                label=metric.label,
                before=previous.score,
                after=metric.score,
                max_score=metric.max_score,
            )
        )
    return changes


def compare_analysis_results(before: AnalysisResult, after: AnalysisResult) -> tuple[list[ScoreChange], list[ScoreChange]]:
    changes = [
        ScoreChange("Overall Score", before.overall_score, after.overall_score, 100),
        ScoreChange("Base ATS", before.resume.score, after.resume.score, 100),
    ]
    if before.job_match and after.job_match:
        changes.append(ScoreChange("Aderencia a vaga", before.job_match.score, after.job_match.score, 100))

    changes.extend(metric_changes(before.resume.metrics, after.resume.metrics))
    if before.job_match and after.job_match:
        changes.extend(metric_changes(before.job_match.metrics, after.job_match.metrics))

    improved = sorted((change for change in changes if change.delta > 0), key=lambda item: item.delta, reverse=True)
    declined = sorted((change for change in changes if change.delta < 0), key=lambda item: item.delta)
    return improved, declined


def score_distance(result: AnalysisResult, target: ScoreTarget) -> int:
    distance = max(0, target.ats_score - result.resume.score)
    distance += max(0, target.overall_score - result.overall_score)
    if target.job_match_score is not None:
        current_job_score = result.job_match.score if result.job_match else 0
        distance += max(0, target.job_match_score - current_job_score)
    return distance


def target_reached(result: AnalysisResult, target: ScoreTarget) -> bool:
    if result.resume.score < target.ats_score:
        return False
    if result.overall_score < target.overall_score:
        return False
    if target.job_match_score is not None:
        if result.job_match is None or result.job_match.score < target.job_match_score:
            return False
    return True


def should_continue_with_job(result: AnalysisResult) -> bool | None:
    if not result.job_match:
        return None
    return result.job_match.score >= 68 and result.overall_score >= 76


def optimize_resume_draft(
    *,
    filename: str,
    original_document: ExtractedDocument,
    baseline_result: AnalysisResult,
    initial_draft: str,
    job_input: JobInput | None,
    ai_optimizer: ResumeOptimizerProtocol | None = None,
    target: ScoreTarget | None = None,
    max_steps: int = DEFAULT_MAX_OPTIMIZATION_STEPS,
    confirmed_terms: list[str] | None = None,
    confirmed_title: str | None = None,
) -> OptimizationOutcome:
    target = target or default_score_target(job_input)
    current_draft = initial_draft
    current_result = analyze_resume_text(filename, current_draft, job_input)
    steps: list[OptimizationStep] = []

    if target_reached(current_result, target):
        return OptimizationOutcome(
            baseline_result=baseline_result,
            starting_result=current_result,
            final_result=current_result,
            initial_draft=initial_draft,
            final_draft=current_draft,
            target=target,
            steps=steps,
            reached_target=True,
            stop_reason="A meta de corte ja foi atingida pelo rascunho atual.",
            continue_with_job=should_continue_with_job(current_result),
        )

    if ai_optimizer is None:
        return OptimizationOutcome(
            baseline_result=baseline_result,
            starting_result=current_result,
            final_result=current_result,
            initial_draft=initial_draft,
            final_draft=current_draft,
            target=target,
            steps=steps,
            reached_target=False,
            stop_reason="A camada de IA nao esta configurada. Defina uma chave para rodar a otimizacao automatica.",
            continue_with_job=should_continue_with_job(current_result),
        )

    stop_reason = "Nao houve melhoria suficiente para justificar novas reescritas."
    for iteration in range(1, max_steps + 1):
        request = AIRewriteRequest(
            original_resume=original_document.cleaned_text,
            current_draft=current_draft,
            current_result=current_result,
            target=target,
            gap_hints=target_gap_summary(current_result, target),
            job_text=job_input.text if job_input else "",
            job_title=job_input.title if job_input and job_input.title else "",
            confirmed_terms=confirmed_terms or [],
            confirmed_title=confirmed_title,
        )
        response = ai_optimizer.rewrite_resume(request)
        candidate_draft = response.optimized_resume.strip()
        if not candidate_draft:
            stop_reason = "A IA nao devolveu um rascunho valido."
            break

        candidate_result = analyze_resume_text(filename, candidate_draft, job_input)
        accepted = is_candidate_better(current_result, candidate_result, target)

        step = OptimizationStep(
            iteration=iteration,
            source="ia",
            summary=response.summary,
            before_result=current_result,
            after_result=candidate_result,
            applied_changes=response.applied_changes,
            retained_job_terms=response.retained_job_terms,
            rejected_job_terms=response.rejected_job_terms,
            confidence_notes=response.confidence_notes,
            stop_signal=response.stop_signal,
            stop_reason=response.stop_reason,
        )
        steps.append(step)

        if not accepted:
            stop_reason = "A ultima reescrita nao melhorou a distancia ate a meta sem sacrificar pontos importantes."
            break

        current_draft = candidate_draft
        current_result = candidate_result
        if target_reached(current_result, target):
            stop_reason = "A meta de corte foi atingida."
            break
        if response.stop_signal:
            stop_reason = response.stop_reason or "A IA sinalizou que nao ha ganhos seguros adicionais."
            break

    return OptimizationOutcome(
        baseline_result=baseline_result,
        starting_result=analyze_resume_text(filename, initial_draft, job_input),
        final_result=current_result,
        initial_draft=initial_draft,
        final_draft=current_draft,
        target=target,
        steps=steps,
        reached_target=target_reached(current_result, target),
        stop_reason=stop_reason,
        continue_with_job=should_continue_with_job(current_result),
    )


def is_candidate_better(current: AnalysisResult, candidate: AnalysisResult, target: ScoreTarget) -> bool:
    current_distance = score_distance(current, target)
    candidate_distance = score_distance(candidate, target)
    if candidate_distance < current_distance:
        return True
    if candidate.resume.score > current.resume.score:
        return True
    if candidate.overall_score > current.overall_score and candidate.resume.score >= current.resume.score - 2:
        return True
    if current.job_match and candidate.job_match:
        if candidate.job_match.score > current.job_match.score and candidate.resume.score >= current.resume.score - 1:
            return True
    return False
