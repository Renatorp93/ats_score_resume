from __future__ import annotations

import json
from dataclasses import dataclass

import requests

from ats_score_resume.optimizer import AIRewriteRequest, AIRewriteResponse, ResumeOptimizerProtocol

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


class AIOptimizationError(RuntimeError):
    """Raised when the AI optimization service cannot return a valid resume rewrite."""


@dataclass(slots=True)
class OpenAIResumeOptimizer(ResumeOptimizerProtocol):
    api_key: str
    model: str = "gpt-5-mini"
    timeout_seconds: int = 90

    def rewrite_resume(self, request: AIRewriteRequest) -> AIRewriteResponse:
        payload = {
            "model": self.model,
            "reasoning": {"effort": "medium"},
            "input": [
                {"role": "system", "content": build_system_prompt()},
                {"role": "user", "content": build_user_prompt(request)},
            ],
            "max_output_tokens": 2200,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "resume_optimization_result",
                    "strict": True,
                    "schema": response_schema(),
                }
            },
        }
        response = requests.post(
            OPENAI_RESPONSES_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        output_text = extract_output_text(data)
        if not output_text:
            raise AIOptimizationError("A resposta da IA nao trouxe o campo output_text esperado.")

        parsed = json.loads(output_text)
        optimized_resume = str(parsed.get("optimized_resume", "")).strip()
        if not optimized_resume:
            raise AIOptimizationError("A resposta estruturada nao incluiu um curriculo otimizado.")

        return AIRewriteResponse(
            optimized_resume=optimized_resume,
            summary=str(parsed.get("summary", "")).strip() or "Reescrita aplicada com foco em ATS e leitura humana.",
            applied_changes=[str(item).strip() for item in parsed.get("applied_changes", []) if str(item).strip()],
            retained_job_terms=[str(item).strip() for item in parsed.get("retained_job_terms", []) if str(item).strip()],
            rejected_job_terms=[str(item).strip() for item in parsed.get("rejected_job_terms", []) if str(item).strip()],
            confidence_notes=[str(item).strip() for item in parsed.get("confidence_notes", []) if str(item).strip()],
            stop_signal=bool(parsed.get("stop_signal", False)),
            stop_reason=str(parsed.get("stop_reason", "")).strip(),
        )


def build_system_prompt() -> str:
    return (
        "You are an expert resume optimizer for ATS systems and human recruiters. "
        "Rewrite resumes into clean plain-text sections with strong bullets, but never invent facts, employers, degrees, dates, metrics, certifications, tools, or seniority. "
        "Only use information grounded in the original resume or in user-confirmed inputs. "
        "Prefer concise, readable writing, preserve the candidate's language, and keep headings clear for ATS parsing. "
        "If a job requirement is not supported by the source resume, omit it from the final resume and explain that choice in the JSON output."
    )


def build_user_prompt(request: AIRewriteRequest) -> str:
    confirmed_terms = ", ".join(request.confirmed_terms or []) or "none"
    current_job_score = request.current_result.job_match.score if request.current_result.job_match else "n/a"
    return (
        "Optimize the resume below until it gets closer to the target score without hallucinating.\n\n"
        f"Target ATS score: {request.target.ats_score}\n"
        f"Target overall score: {request.target.overall_score}\n"
        f"Target job-match score: {request.target.job_match_score if request.target.job_match_score is not None else 'n/a'}\n"
        f"Current ATS score: {request.current_result.resume.score}\n"
        f"Current overall score: {request.current_result.overall_score}\n"
        f"Current job-match score: {current_job_score}\n"
        f"Confirmed title from user: {request.confirmed_title or 'none'}\n"
        f"Confirmed terms from user: {confirmed_terms}\n"
        f"Gap hints: {' | '.join(request.gap_hints) or 'none'}\n"
        f"Job title: {request.job_title or 'none'}\n"
        "Preferred output style:\n"
        "- Keep uppercase section headings.\n"
        "- Keep header concise.\n"
        "- Use short summary paragraphs.\n"
        "- Write experience as bullet points starting with action verbs.\n"
        "- Reuse numbers already present in the source when possible.\n"
        "- Add only job terms that are already supported by the source resume or explicitly confirmed by the user.\n"
        "- If the target score cannot be reached safely, still produce the strongest safe version and explain blockers.\n\n"
        f"Original resume:\n{request.original_resume}\n\n"
        f"Current draft:\n{request.current_draft}\n\n"
        f"Job description:\n{request.job_text or 'none'}\n"
    )


def response_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "optimized_resume": {"type": "string"},
            "summary": {"type": "string"},
            "applied_changes": {
                "type": "array",
                "items": {"type": "string"},
            },
            "retained_job_terms": {
                "type": "array",
                "items": {"type": "string"},
            },
            "rejected_job_terms": {
                "type": "array",
                "items": {"type": "string"},
            },
            "confidence_notes": {
                "type": "array",
                "items": {"type": "string"},
            },
            "stop_signal": {"type": "boolean"},
            "stop_reason": {"type": "string"},
        },
        "required": [
            "optimized_resume",
            "summary",
            "applied_changes",
            "retained_job_terms",
            "rejected_job_terms",
            "confidence_notes",
            "stop_signal",
            "stop_reason",
        ],
    }


def extract_output_text(data: dict[str, object]) -> str:
    output_text = str(data.get("output_text", "")).strip()
    if output_text:
        return output_text

    output = data.get("output", [])
    if not isinstance(output, list):
        return ""

    chunks: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content", [])
        if not isinstance(content, list):
            continue
        for content_item in content:
            if not isinstance(content_item, dict):
                continue
            text = content_item.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())

    return "\n".join(chunks).strip()
