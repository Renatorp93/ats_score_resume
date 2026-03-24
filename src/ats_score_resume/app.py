from __future__ import annotations

import html
import math
import os
import re

import streamlit as st

from ats_score_resume.ai_optimizer import AIOptimizationError, OpenAIResumeOptimizer
from ats_score_resume.document_parser import ExtractedDocument, UnsupportedFileTypeError, extract_document
from ats_score_resume.exporters import build_docx_resume, build_html_resume
from ats_score_resume.job_source import JobInput, JobSourceError, resolve_job_input
from ats_score_resume.optimizer import (
    OptimizationOutcome,
    ScoreTarget,
    analyze_resume_text,
    compare_analysis_results,
    default_score_target,
    optimize_resume_draft,
    target_reached,
)
from ats_score_resume.scoring import AnalysisResult, Suggestion, analyze_document, display_section_name, generate_resume_draft

TERM_STYLE_MAP = {
    "api": "API",
    "aws": "AWS",
    "bi": "BI",
    "ci/cd": "CI/CD",
    "css": "CSS",
    "devops": "DevOps",
    "docker": "Docker",
    "etl": "ETL",
    "elt": "ELT",
    "git": "Git",
    "html": "HTML",
    "kpi": "KPI",
    "kubernetes": "Kubernetes",
    "mysql": "MySQL",
    "node.js": "Node.js",
    "nosql": "NoSQL",
    "power bi": "Power BI",
    "python": "Python",
    "react": "React",
    "sql": "SQL",
    "terraform": "Terraform",
    "ux": "UX",
}


def main() -> None:
    st.set_page_config(page_title="ATS Score Resume", page_icon="A", layout="wide")
    inject_styles()

    st.title("ATS Score Resume")
    st.caption("Analise curriculos com score explicavel, meta de corte e otimizacao hibrida com IA.")

    with st.sidebar:
        st.subheader("Como o score funciona")
        st.markdown(
            "\n".join(
                [
                    "- `Base ATS`: leitura pelo ATS, estrutura e forca do conteudo.",
                    "- `Aderencia a vaga`: palavras-chave, requisitos e alinhamento com a oportunidade.",
                    "- `Overall`: media ponderada quando a vaga e informada.",
                    "- `Meta de corte`: o app tenta chegar em uma nota forte antes de parar de otimizar.",
                ]
            )
        )
        render_ai_settings()

    resume_file = st.file_uploader("Envie o curriculo", type=["pdf", "docx", "txt", "md"])
    col1, col2 = st.columns(2)

    with col1:
        job_description = st.text_area(
            "Descricao da vaga (opcional)",
            height=260,
            placeholder="Cole aqui a descricao da vaga para calcular aderencia.",
        )

    with col2:
        job_url = st.text_input(
            "URL da vaga (opcional)",
            placeholder="https://empresa.com/jobs/123",
        )
        st.info("Se a URL nao puder ser lida, voce ainda pode colar a descricao manualmente.")

    run_analysis = st.button("Analisar curriculo", type="primary", use_container_width=True)
    state_key = "latest_analysis"

    if run_analysis:
        if resume_file is None:
            st.error("Envie um curriculo para iniciar a analise.")
            return

        try:
            document = extract_document(resume_file.name, resume_file.getvalue())
        except UnsupportedFileTypeError as exc:
            st.error(str(exc))
            return
        except Exception as exc:  # pragma: no cover
            st.error(f"Nao foi possivel ler o arquivo enviado: {exc}")
            return

        job_input = None
        if job_description.strip() or job_url.strip():
            try:
                job_input = resolve_job_input(job_description, job_url)
            except JobSourceError as exc:
                st.warning(str(exc))

        result = analyze_document(
            document=document,
            job_text=job_input.text if job_input else None,
            job_source=job_input.source if job_input else "",
            job_title_override=job_input.title if job_input else None,
        )
        st.session_state[state_key] = {
            "document": document,
            "result": result,
            "job_input": job_input,
        }

    saved_analysis = st.session_state.get(state_key)
    if saved_analysis:
        render_result(
            saved_analysis["result"],
            saved_analysis["document"],
            saved_analysis.get("job_input"),
        )


def render_ai_settings() -> None:
    st.subheader("IA opcional")
    env_key = os.getenv("OPENAI_API_KEY", "")
    env_model = os.getenv("OPENAI_MODEL", "gpt-5-mini")

    if "openai_api_key" not in st.session_state:
        st.session_state["openai_api_key"] = env_key
    if "openai_model" not in st.session_state:
        st.session_state["openai_model"] = env_model

    st.text_input(
        "OpenAI API key",
        key="openai_api_key",
        type="password",
        help="Opcional. Se preencher, o app usa IA para reescrever o curriculo ate bater a meta ou esgotar ganhos seguros.",
    )
    st.text_input(
        "Modelo de IA",
        key="openai_model",
        help="Padrao sugerido: gpt-5-mini.",
    )
    if st.session_state["openai_api_key"]:
        st.success("IA habilitada para reescrita estruturada.")
    else:
        st.info("Sem chave, o app continua com score deterministico e rascunho heuristico.")


def render_result(result: AnalysisResult, document: ExtractedDocument, job_input: JobInput | None = None) -> None:
    st.success(f"Analise concluida para `{document.filename}`.")

    hero_col, metrics_col = st.columns((1.1, 1), gap="large")
    with hero_col:
        render_gauge("Overall Score", result.overall_score, score_status(result.overall_score))
    with metrics_col:
        render_score_chip("Base ATS", result.resume.score, "Qualidade geral do curriculo para leitura automatizada.")
        if result.job_match:
            render_score_chip("Aderencia a vaga", result.job_match.score, "Conexao entre o seu curriculo e a oportunidade.")
        render_score_chip("Nivel atual", result.overall_score, summary_status_copy(result.overall_score))

    st.subheader("Resumo da analise")
    detected_sections = [display_section_name(section) for section in result.resume.detected_sections]
    missing_sections = [display_section_name(section) for section in result.resume.missing_sections]
    skill_heading = result.resume.section_headings.get("skills")
    heading_note = f" Secao de skills reconhecida como: `{skill_heading}`." if skill_heading else ""

    st.markdown(
        "\n".join(
            [
                f"- Secoes detectadas: {', '.join(detected_sections) or 'nenhuma secao padrao detectada'}",
                f"- Secoes ausentes: {', '.join(missing_sections) or 'nenhuma'}",
                f"- Skills detectadas: {', '.join(result.resume.keyword_terms[:8]) or 'nenhuma'}",
                f"- Contato identificado: {', '.join(result.resume.contact_hits) or 'insuficiente'}." + heading_note,
            ]
        )
    )

    st.subheader("Sugestoes para aumentar o score")
    if result.suggestions:
        for suggestion in result.suggestions:
            render_suggestion_card(suggestion)
    else:
        st.markdown("<div class='info-card'>Nenhuma sugestao critica encontrada.</div>", unsafe_allow_html=True)

    st.subheader("Como o score foi montado")
    render_breakdown_cards(result.resume.metrics, build_resume_gap_map(result))

    if result.job_match:
        st.subheader("Como a vaga influenciou o resultado")
        st.caption(f"Fonte da vaga: {result.job_match.source}")
        render_breakdown_cards(result.job_match.metrics, build_job_gap_map(result))
        st.markdown(
            "\n".join(
                [
                    f"- Keywords cobertas: {', '.join(result.job_match.matched_keywords) or 'nenhuma'}",
                    f"- Keywords ausentes: {', '.join(result.job_match.missing_keywords) or 'nenhuma'}",
                    f"- Requisitos ausentes: {', '.join(result.job_match.missing_required_terms) or 'nenhum'}",
                ]
            )
        )

    draft_key = build_state_key(document.filename, result.overall_score, "draft")
    ensure_draft_state(draft_key, document, result)

    if result.job_match:
        render_personalization_section(result, draft_key, job_input)

    current_draft = st.session_state[draft_key]
    draft_result = analyze_resume_text(document.filename, current_draft, job_input)
    target = default_score_target(job_input)
    render_optimization_section(result, document, job_input, draft_key, draft_result, target)

    st.subheader("Curriculo otimizado")
    with st.expander("Rascunho editavel", expanded=True):
        edited_resume = st.text_area(
            "Rascunho gerado",
            key=draft_key,
            height=420,
        )
        st.caption("Revise o texto antes de enviar. Mantenha apenas experiencias e skills que sejam verdadeiras.")

        latest_draft_result = analyze_resume_text(document.filename, edited_resume, job_input)
        render_inline_score_summary(latest_draft_result, target)

        review_key = build_state_key(document.filename, result.overall_score, "reviewed")
        reviewed = st.checkbox(
            "Revisei o rascunho e quero gerar o arquivo final.",
            key=review_key,
        )

        if reviewed:
            render_download_options(document.filename, edited_resume)
        else:
            st.info("Depois de revisar o texto, marque a caixa acima para liberar a geracao do arquivo final.")


def render_optimization_section(
    baseline_result: AnalysisResult,
    document: ExtractedDocument,
    job_input: JobInput | None,
    draft_key: str,
    draft_result: AnalysisResult,
    target: ScoreTarget,
) -> None:
    st.subheader("Otimizacao inteligente")
    st.markdown(
        "A meta padrao e manter o curriculo forte para ATS e bom o bastante para a vaga. "
        "A IA so entra para reescrever com mais contexto, sem inventar fatos, e para quando a meta for atingida ou quando novos ganhos deixarem de compensar."
    )

    render_target_summary(draft_result, target)

    optimization_key = f"{draft_key}_optimization"
    outcome = st.session_state.get(optimization_key)

    manual_title = st.session_state.get(f"{draft_key}_manual_title", "").strip() or None
    selected_terms = st.session_state.get(f"{draft_key}_selected_terms", [])
    apply_title = bool(st.session_state.get(f"{draft_key}_apply_title", False))

    disabled = target_reached(draft_result, target)
    if st.button("Otimizar com IA ate atingir a meta", key=f"{draft_key}_optimize_button", use_container_width=True, disabled=disabled):
        try:
            optimizer = build_ai_optimizer()
            outcome = optimize_resume_draft(
                filename=document.filename,
                original_document=document,
                baseline_result=baseline_result,
                initial_draft=st.session_state[draft_key],
                job_input=job_input,
                ai_optimizer=optimizer,
                target=target,
                confirmed_terms=selected_terms,
                confirmed_title=manual_title if apply_title else None,
            )
        except AIOptimizationError as exc:
            st.error(f"Nao foi possivel concluir a reescrita com IA: {exc}")
            return
        except Exception as exc:  # pragma: no cover
            st.error(f"Falha ao rodar a otimizacao com IA: {exc}")
            return

        st.session_state[draft_key] = outcome.final_draft
        st.session_state[optimization_key] = outcome
        st.toast("Otimizacao concluida.")
        st.rerun()

    if disabled:
        st.success("O rascunho atual ja bateu a meta de corte configurada.")
    elif not st.session_state.get("openai_api_key", "").strip():
        st.info("Preencha a chave da OpenAI na lateral para ativar a reescrita automatica ate a meta.")

    if outcome:
        render_optimization_outcome(outcome)


def render_target_summary(draft_result: AnalysisResult, target: ScoreTarget) -> None:
    col1, col2, col3 = st.columns(3)
    with col1:
        render_target_card("Base ATS", draft_result.resume.score, target.ats_score)
    with col2:
        render_target_card("Overall", draft_result.overall_score, target.overall_score)
    with col3:
        if target.job_match_score is None:
            st.markdown("<div class='info-card'>Sem vaga informada, a meta vale apenas para ATS e score geral.</div>", unsafe_allow_html=True)
        else:
            current_job_score = draft_result.job_match.score if draft_result.job_match else 0
            render_target_card("Aderencia", current_job_score, target.job_match_score)


def render_target_card(label: str, current: int, target: int) -> None:
    helper = "Meta atingida." if current >= target else f"Meta: {target}/100"
    render_score_chip(label, current, helper)


def render_inline_score_summary(result: AnalysisResult, target: ScoreTarget) -> None:
    status = "Meta atingida" if target_reached(result, target) else "Abaixo da meta"
    st.caption(
        f"Rascunho atual: ATS {result.resume.score}/100, Overall {result.overall_score}/100, "
        f"Status: {status}."
    )


def render_optimization_outcome(outcome: OptimizationOutcome) -> None:
    if outcome.reached_target:
        st.success(outcome.stop_reason)
    else:
        st.warning(outcome.stop_reason)

    summary_col, verdict_col = st.columns((1.4, 1))
    with summary_col:
        render_score_chip(
            "Antes da otimizacao",
            outcome.starting_result.overall_score,
            f"ATS {outcome.starting_result.resume.score}/100",
        )
        render_score_chip(
            "Depois da otimizacao",
            outcome.final_result.overall_score,
            f"ATS {outcome.final_result.resume.score}/100",
        )
    with verdict_col:
        if outcome.continue_with_job is None:
            st.markdown("<div class='info-card'>Sem vaga informada, a meta vale apenas para prontidao ATS.</div>", unsafe_allow_html=True)
        elif outcome.continue_with_job:
            st.markdown("<div class='info-card'>Vale seguir com esta vaga: a aderencia ficou forte o bastante para uma candidatura consciente.</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='info-card'>A vaga ainda parece exigente para o seu perfil atual. Vale decidir se compensa adaptar mais ou priorizar outra oportunidade.</div>", unsafe_allow_html=True)

    improved, declined = compare_analysis_results(outcome.starting_result, outcome.final_result)
    render_change_lists(improved, declined)

    if outcome.steps:
        st.markdown("**Rodadas da IA**")
        for step in outcome.steps:
            with st.expander(f"Rodada {step.iteration}"):
                st.markdown(f"- Resumo da rodada: {step.summary}")
                if step.applied_changes:
                    st.markdown("- Mudancas aplicadas:")
                    for item in step.applied_changes:
                        st.markdown(f"  - {item}")
                if step.retained_job_terms:
                    st.markdown(f"- Termos da vaga aproveitados: {', '.join(step.retained_job_terms)}")
                if step.rejected_job_terms:
                    st.markdown(f"- Termos rejeitados por falta de evidencia: {', '.join(step.rejected_job_terms)}")
                if step.confidence_notes:
                    for note in step.confidence_notes:
                        st.markdown(f"- Observacao: {note}")


def render_change_lists(improved: list, declined: list) -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**O que aumentou a nota**")
        if improved:
            for change in improved[:8]:
                st.markdown(f"- {change.label}: +{change.delta} ponto(s) ({change.before} -> {change.after})")
        else:
            st.markdown("- Nenhum ganho relevante registrado.")
    with col2:
        st.markdown("**O que reduziu a nota**")
        if declined:
            for change in declined[:6]:
                st.markdown(f"- {change.label}: {change.delta} ponto(s) ({change.before} -> {change.after})")
        else:
            st.markdown("- Nenhuma queda relevante registrada.")


def build_ai_optimizer() -> OpenAIResumeOptimizer | None:
    api_key = st.session_state.get("openai_api_key", "").strip()
    if not api_key:
        return None
    model = st.session_state.get("openai_model", "gpt-5-mini").strip() or "gpt-5-mini"
    return OpenAIResumeOptimizer(api_key=api_key, model=model)


def render_personalization_section(result: AnalysisResult, draft_key: str, job_input: JobInput | None) -> None:
    st.subheader("Personalizacao da vaga")
    st.markdown(
        "Essa area serve para adaptar o curriculo antes da geracao final. "
        "O titulo sugerido funciona melhor no topo do curriculo, perto do cabecalho, e os termos confirmados entram na secao de skills."
    )

    suggested_terms = personalization_terms(result)
    inferred_title = result.job_match.job_title if result.job_match else None
    fallback_title = job_input.title if job_input else None
    default_title = inferred_title or fallback_title or ""

    manual_title_key = f"{draft_key}_manual_title"
    if manual_title_key not in st.session_state:
        st.session_state[manual_title_key] = default_title

    if inferred_title:
        st.markdown(f"- Titulo sugerido para o topo do curriculo: `{inferred_title}`")
    else:
        st.warning("Nao conseguimos identificar o titulo da vaga com seguranca. Preencha manualmente abaixo.")

    manual_title = st.text_input(
        "Titulo da vaga para usar no topo do curriculo",
        key=manual_title_key,
        placeholder="Ex.: Engenharia de Dados AWS Senior",
    ).strip()

    st.checkbox(
        "Adicionar o titulo sugerido no topo do curriculo",
        key=f"{draft_key}_apply_title",
        value=bool(default_title),
        disabled=not bool(manual_title),
    )

    st.multiselect(
        "Selecione apenas as skills/termos que voce realmente domina para adicionar na secao Skills",
        options=suggested_terms,
        default=suggested_terms[: min(6, len(suggested_terms))],
        key=f"{draft_key}_selected_terms",
    )

    if st.button("Aplicar personalizacao ao rascunho", key=f"{draft_key}_apply_button", use_container_width=True):
        selected_terms = st.session_state.get(f"{draft_key}_selected_terms", [])
        apply_title = bool(st.session_state.get(f"{draft_key}_apply_title", False))
        updated_draft = apply_personalization_to_draft(
            st.session_state[draft_key],
            manual_title if apply_title else None,
            selected_terms,
        )
        st.session_state[draft_key] = updated_draft
        st.toast("Personalizacao aplicada ao rascunho.")
        st.rerun()


def render_download_options(filename: str, resume_text: str) -> None:
    txt_col, md_col = st.columns(2)
    with txt_col:
        st.download_button(
            "Baixar em TXT",
            data=resume_text,
            file_name=build_generated_filename(filename, "txt"),
            mime="text/plain",
            use_container_width=True,
        )
    with md_col:
        st.download_button(
            "Baixar em MD",
            data=resume_text,
            file_name=build_generated_filename(filename, "md"),
            mime="text/markdown",
            use_container_width=True,
        )

    docx_col, html_col = st.columns(2)
    with docx_col:
        st.download_button(
            "Baixar em DOCX",
            data=build_docx_resume(resume_text),
            file_name=build_generated_filename(filename, "docx"),
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    with html_col:
        st.download_button(
            "Baixar em HTML",
            data=build_html_resume(resume_text),
            file_name=build_generated_filename(filename, "html"),
            mime="text/html",
            use_container_width=True,
        )


def ensure_draft_state(draft_key: str, document: ExtractedDocument, result: AnalysisResult) -> None:
    if draft_key not in st.session_state:
        st.session_state[draft_key] = generate_resume_draft(document, result)


def personalization_terms(result: AnalysisResult) -> list[str]:
    if not result.job_match:
        return []

    ordered: list[str] = []
    for term in [*result.job_match.missing_required_terms, *result.job_match.missing_keywords]:
        formatted = format_skill_term(term)
        if formatted not in ordered:
            ordered.append(formatted)
    return ordered[:12]


def apply_personalization_to_draft(draft_text: str, title: str | None, selected_terms: list[str]) -> str:
    updated = draft_text
    if title:
        updated = upsert_top_title(updated, title)
    if selected_terms:
        updated = merge_terms_into_skills(updated, selected_terms)
    return updated


def upsert_top_title(draft_text: str, title: str) -> str:
    lines = draft_text.splitlines()
    if not lines:
        return title

    title_line = title.strip()
    if title_line in lines:
        return draft_text

    insert_at = 1
    while insert_at < len(lines) and lines[insert_at].strip():
        insert_at += 1

    updated_lines = lines[:insert_at] + [title_line] + lines[insert_at:]
    return "\n".join(updated_lines).strip()


def merge_terms_into_skills(draft_text: str, selected_terms: list[str]) -> str:
    sections = split_draft_sections(draft_text)

    for index, (heading, content) in enumerate(sections):
        if heading == "SKILLS":
            existing = [item.strip() for item in re.split(r"[,\n;|]", content) if item.strip()]
            cleaned_terms = [format_skill_term(term, existing) for term in selected_terms]
            merged = unique_terms(existing + cleaned_terms)
            sections[index] = ("SKILLS", ", ".join(merged))
            return join_draft_sections(sections)

    cleaned_terms = unique_terms([format_skill_term(term) for term in selected_terms])
    sections.append(("SKILLS", ", ".join(cleaned_terms)))
    return join_draft_sections(sections)


def unique_terms(items: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for item in items:
        clean = item.strip()
        if not clean:
            continue
        key = clean.casefold()
        if key not in seen:
            seen[key] = clean
    return list(seen.values())


def format_skill_term(term: str, existing_terms: list[str] | None = None) -> str:
    clean = term.strip()
    if not clean:
        return clean

    if existing_terms:
        for existing in existing_terms:
            if existing.strip().casefold() == clean.casefold():
                return existing.strip()

    lower = clean.casefold()
    if lower in TERM_STYLE_MAP:
        return TERM_STYLE_MAP[lower]

    if " / " in clean:
        return " / ".join(format_skill_term(part, existing_terms) for part in clean.split(" / "))
    if "/" in clean:
        return "/".join(format_skill_term(part, existing_terms) for part in clean.split("/"))
    if "-" in clean:
        return "-".join(format_skill_term(part, existing_terms) for part in clean.split("-"))
    if " " in clean:
        return " ".join(format_skill_term(part, existing_terms) for part in clean.split())
    if clean.isupper():
        return clean
    if len(clean) <= 3:
        return clean.upper()
    return clean[:1].upper() + clean[1:].lower()


def split_draft_sections(draft_text: str) -> list[tuple[str | None, str]]:
    lines = draft_text.splitlines()
    sections: list[tuple[str | None, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in lines:
        if is_all_caps_heading(line):
            if current_heading is not None or current_lines:
                sections.append((current_heading, current_lines))
            current_heading = line.strip()
            current_lines = []
            continue
        current_lines.append(line.rstrip())

    if current_heading is not None or current_lines:
        sections.append((current_heading, current_lines))

    normalized: list[tuple[str | None, str]] = []
    for heading, content_lines in sections:
        content = "\n".join(content_lines).strip()
        normalized.append((heading, content))
    return normalized


def join_draft_sections(sections: list[tuple[str | None, str]]) -> str:
    blocks: list[str] = []
    for heading, content in sections:
        if heading:
            block = heading if not content else f"{heading}\n{content}"
        else:
            block = content
        if block.strip():
            blocks.append(block.strip())
    return "\n\n".join(blocks).strip()


def is_all_caps_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    letters = [char for char in stripped if char.isalpha()]
    return bool(letters) and all(char.isupper() for char in letters)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(43,108,176,0.14), transparent 30%),
                radial-gradient(circle at top right, rgba(16,185,129,0.10), transparent 28%),
                linear-gradient(180deg, #f8fafc 0%, #eef4ff 100%);
        }
        .score-card,
        .suggestion-card,
        .breakdown-card,
        .info-card {
            border-radius: 20px;
            background: rgba(255,255,255,0.92);
            border: 1px solid rgba(148,163,184,0.18);
            box-shadow: 0 18px 40px rgba(15,23,42,0.08);
        }
        .score-card { padding: 18px 20px; margin-bottom: 14px; }
        .score-card .eyebrow,
        .breakdown-card .eyebrow {
            color: #64748b;
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }
        .score-card .value {
            font-size: 2rem;
            font-weight: 700;
            color: #0f172a;
            margin-top: 6px;
        }
        .score-card .helper { color: #475569; margin-top: 8px; font-size: 0.96rem; }
        .suggestion-card {
            padding: 16px 18px;
            margin-bottom: 12px;
            border-left: 6px solid #f59e0b;
        }
        .suggestion-card.priority-media { border-left-color: #2563eb; }
        .suggestion-card .badge {
            display: inline-block;
            font-size: 0.78rem;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 999px;
            color: white;
            margin-bottom: 10px;
            letter-spacing: 0.05em;
        }
        .suggestion-card .badge-alta { background: linear-gradient(135deg, #f97316, #dc2626); }
        .suggestion-card .badge-media { background: linear-gradient(135deg, #2563eb, #0f766e); }
        .suggestion-card .title {
            font-size: 1.08rem;
            font-weight: 700;
            color: #0f172a;
            margin-bottom: 6px;
        }
        .suggestion-card .details,
        .breakdown-card .details { color: #334155; font-size: 0.97rem; line-height: 1.45; }
        .breakdown-card { padding: 18px 20px; margin-bottom: 12px; }
        .breakdown-card .title {
            font-size: 1.05rem;
            font-weight: 700;
            color: #0f172a;
            margin: 2px 0 8px;
        }
        .breakdown-card .meter {
            height: 10px;
            border-radius: 999px;
            background: #e2e8f0;
            overflow: hidden;
            margin: 12px 0 10px;
        }
        .breakdown-card .meter-fill {
            height: 100%;
            border-radius: 999px;
            background: linear-gradient(90deg, #2563eb 0%, #14b8a6 100%);
        }
        .info-card { padding: 16px 18px; color: #334155; }
        .gauge-wrap { padding: 16px 8px 8px; text-align: center; }
        .gauge-title {
            color: #475569;
            text-transform: uppercase;
            letter-spacing: 0.09em;
            font-size: 0.82rem;
            margin-bottom: 6px;
        }
        .gauge-score {
            font-size: 2.5rem;
            font-weight: 800;
            color: #0f172a;
            margin-top: -10px;
        }
        .gauge-subtitle { color: #475569; margin-top: -6px; font-size: 0.98rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_gauge(title: str, score: int, subtitle: str) -> None:
    radius = 88
    circumference = math.pi * radius
    progress = max(0, min(100, score)) / 100
    offset = circumference * (1 - progress)
    color = score_color(score)
    angle = -180 + (180 * progress)

    gauge_html = f"""
    <div class="score-card gauge-wrap">
        <div class="gauge-title">{html.escape(title)}</div>
        <svg width="240" height="150" viewBox="0 0 240 150" role="img" aria-label="{html.escape(title)} {score} de 100">
            <path d="M 32 120 A 88 88 0 0 1 208 120" fill="none" stroke="#dbeafe" stroke-width="18" stroke-linecap="round"></path>
            <path d="M 32 120 A 88 88 0 0 1 208 120" fill="none" stroke="{color}" stroke-width="18" stroke-linecap="round"
                stroke-dasharray="{circumference:.2f}" stroke-dashoffset="{offset:.2f}"></path>
            <g transform="translate(120 120) rotate({angle:.2f})">
                <line x1="0" y1="0" x2="68" y2="0" stroke="#0f172a" stroke-width="5" stroke-linecap="round"></line>
            </g>
            <circle cx="120" cy="120" r="10" fill="#0f172a"></circle>
        </svg>
        <div class="gauge-score">{score}/100</div>
        <div class="gauge-subtitle">{html.escape(subtitle)}</div>
    </div>
    """
    st.markdown(gauge_html, unsafe_allow_html=True)


def render_score_chip(title: str, score: int, helper: str) -> None:
    st.markdown(
        f"""
        <div class="score-card">
            <div class="eyebrow">{html.escape(title)}</div>
            <div class="value">{score}/100</div>
            <div class="helper">{html.escape(helper)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_suggestion_card(suggestion: Suggestion) -> None:
    priority_class = "badge-alta" if suggestion.priority == "alta" else "badge-media"
    st.markdown(
        f"""
        <div class="suggestion-card priority-{suggestion.priority}">
            <span class="badge {priority_class}">{html.escape(suggestion.priority.upper())}</span>
            <div class="title">{html.escape(suggestion.title)}</div>
            <div class="details">{html.escape(suggestion.details)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_breakdown_cards(metrics: list, gap_map: dict[str, list[str]]) -> None:
    for metric in metrics:
        ratio = 0 if metric.max_score == 0 else round((metric.score / metric.max_score) * 100)
        missing_items = gap_map.get(metric.key, [])
        with st.container():
            st.markdown(
                f"""
                <div class="breakdown-card">
                    <div class="eyebrow">{html.escape(score_status(ratio))}</div>
                    <div class="title">{html.escape(metric.label)}</div>
                    <div class="details"><strong>{metric.score}/{metric.max_score}</strong> pontos</div>
                    <div class="meter"><div class="meter-fill" style="width:{ratio}%"></div></div>
                    <div class="details">{html.escape(metric.details)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if missing_items:
                label = summarize_missing_items(missing_items)
                with st.expander(label):
                    for item in missing_items:
                        st.markdown(f"- {item}")


def build_resume_gap_map(result: AnalysisResult) -> dict[str, list[str]]:
    gaps: dict[str, list[str]] = {
        "parsing_format": [],
        "completeness": [],
        "content_quality": [],
    }

    if result.resume.format_risks:
        gaps["parsing_format"].extend(result.resume.format_risks)
    if result.resume.missing_sections:
        gaps["parsing_format"].append("Padronizar os headings principais ajuda a leitura do ATS.")

    required_contacts = {
        "email": "Adicionar e-mail.",
        "telefone": "Adicionar telefone.",
        "localizacao": "Adicionar localizacao.",
    }
    for key, message in required_contacts.items():
        if key not in result.resume.contact_hits:
            gaps["completeness"].append(message)
    for section in result.resume.missing_sections:
        gaps["completeness"].append(f"Incluir a secao {display_section_name(section)}.")

    if result.resume.quantified_achievement_count < 2:
        gaps["content_quality"].append("Adicionar mais resultados com numeros ou percentuais.")
    if result.resume.action_bullet_count < 3:
        gaps["content_quality"].append("Usar mais bullets iniciando com verbos de acao.")
    if len(result.resume.keyword_terms) < 8:
        gaps["content_quality"].append("Expandir a densidade de hard skills relevantes.")

    return gaps


def build_job_gap_map(result: AnalysisResult) -> dict[str, list[str]]:
    if not result.job_match:
        return {}

    gaps: dict[str, list[str]] = {
        "keyword_coverage": [f"Incluir ou reforcar: {term}" for term in result.job_match.missing_keywords[:10]],
        "required_terms": [f"Comprovar requisito: {term}" for term in result.job_match.missing_required_terms[:10]],
        "title_alignment": [],
        "evidence_alignment": [],
        "terminology_fidelity": [],
    }

    if not result.job_match.job_title:
        gaps["title_alignment"].append("Preencher manualmente o titulo da vaga para melhorar o alinhamento.")
    else:
        gaps["title_alignment"].append(f"Confirmar se o titulo alvo deve ser: {result.job_match.job_title}.")
    if result.job_match.missing_required_terms:
        gaps["evidence_alignment"].append("Mover requisitos confirmados para experiencia, resumo ou skills.")
    if result.job_match.missing_keywords:
        gaps["terminology_fidelity"].append("Usar a mesma grafia da vaga para ferramentas e tecnologias principais.")

    return gaps


def summarize_missing_items(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return "Ver 1 ponto de atencao"
    return f"Ver {len(items)} pontos de atencao"


def score_color(score: int) -> str:
    if score >= 80:
        return "#16a34a"
    if score >= 60:
        return "#f59e0b"
    return "#dc2626"


def score_status(score: int) -> str:
    if score >= 80:
        return "Muito forte"
    if score >= 60:
        return "Bom potencial"
    return "Precisa de reforco"


def summary_status_copy(score: int) -> str:
    if score >= 80:
        return "Seu curriculo ja esta competitivo e com boa leitura automatizada."
    if score >= 60:
        return "Ha uma base boa, com espaco claro para subir o score."
    return "Vale ajustar estrutura e conteudo antes de usar em processos seletivos."


def build_generated_filename(filename: str, extension: str) -> str:
    base_name = filename.rsplit(".", maxsplit=1)[0]
    return f"{base_name}_otimizado.{extension}"


def build_state_key(filename: str, score: int, suffix: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_-]", "_", filename)
    return f"{sanitized}_{score}_{suffix}"


if __name__ == "__main__":
    main()
