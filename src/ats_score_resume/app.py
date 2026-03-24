from __future__ import annotations

import html
import math
import re

import streamlit as st

from ats_score_resume.document_parser import ExtractedDocument, UnsupportedFileTypeError, extract_document
from ats_score_resume.exporters import build_docx_resume, build_html_resume
from ats_score_resume.job_source import JobInput, JobSourceError, resolve_job_input
from ats_score_resume.scoring import AnalysisResult, Suggestion, analyze_document, display_section_name, generate_resume_draft


def main() -> None:
    st.set_page_config(page_title="ATS Score Resume", page_icon="A", layout="wide")
    inject_styles()

    st.title("ATS Score Resume")
    st.caption("Analise currículos com score explicável de prontidão para ATS e aderência a vagas.")

    with st.sidebar:
        st.subheader("Como o score funciona")
        st.markdown(
            "\n".join(
                [
                    "- `Base ATS`: leitura pelo ATS, estrutura e força do conteúdo.",
                    "- `Aderência à vaga`: palavras-chave, requisitos e alinhamento com a oportunidade.",
                    "- `Overall`: média ponderada quando a vaga é informada.",
                ]
            )
        )

    resume_file = st.file_uploader("Envie o currículo", type=["pdf", "docx", "txt", "md"])
    col1, col2 = st.columns(2)

    with col1:
        job_description = st.text_area(
            "Descrição da vaga (opcional)",
            height=260,
            placeholder="Cole aqui a descrição da vaga para calcular aderência.",
        )

    with col2:
        job_url = st.text_input(
            "URL da vaga (opcional)",
            placeholder="https://empresa.com/jobs/123",
        )
        st.info("Se a URL não puder ser lida, você ainda pode colar a descrição manualmente.")

    run_analysis = st.button("Analisar currículo", type="primary", use_container_width=True)
    state_key = "latest_analysis"

    if run_analysis:
        if resume_file is None:
            st.error("Envie um currículo para iniciar a análise.")
            return

        try:
            document = extract_document(resume_file.name, resume_file.getvalue())
        except UnsupportedFileTypeError as exc:
            st.error(str(exc))
            return
        except Exception as exc:  # pragma: no cover
            st.error(f"Não foi possível ler o arquivo enviado: {exc}")
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


def render_result(result: AnalysisResult, document: ExtractedDocument, job_input: JobInput | None = None) -> None:
    st.success(f"Análise concluída para `{document.filename}`.")

    hero_col, metrics_col = st.columns((1.1, 1), gap="large")
    with hero_col:
        render_gauge("Overall Score", result.overall_score, score_status(result.overall_score))
    with metrics_col:
        render_score_chip("Base ATS", result.resume.score, "Qualidade geral do currículo para leitura automatizada.")
        if result.job_match:
            render_score_chip("Aderência à vaga", result.job_match.score, "Conexão entre o seu currículo e a oportunidade.")
        render_score_chip("Nível atual", result.overall_score, summary_status_copy(result.overall_score))

    st.subheader("Resumo da análise")
    detected_sections = [display_section_name(section) for section in result.resume.detected_sections]
    missing_sections = [display_section_name(section) for section in result.resume.missing_sections]
    skill_heading = result.resume.section_headings.get("skills")
    heading_note = f" Seção de skills reconhecida como: `{skill_heading}`." if skill_heading else ""

    st.markdown(
        "\n".join(
            [
                f"- Seções detectadas: {', '.join(detected_sections) or 'nenhuma seção padrão detectada'}",
                f"- Seções ausentes: {', '.join(missing_sections) or 'nenhuma'}",
                f"- Skills detectadas: {', '.join(result.resume.keyword_terms[:8]) or 'nenhuma'}",
                f"- Contato identificado: {', '.join(result.resume.contact_hits) or 'insuficiente'}." + heading_note,
            ]
        )
    )

    st.subheader("Sugestões para aumentar o score")
    if result.suggestions:
        for suggestion in result.suggestions:
            render_suggestion_card(suggestion)
    else:
        st.markdown("<div class='info-card'>Nenhuma sugestão crítica encontrada.</div>", unsafe_allow_html=True)

    st.subheader("Como o score foi montado")
    render_breakdown_cards(result.resume.metrics)

    if result.job_match:
        st.subheader("Como a vaga influenciou o resultado")
        st.caption(f"Fonte da vaga: {result.job_match.source}")
        render_breakdown_cards(result.job_match.metrics)
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

    st.subheader("Currículo otimizado")
    with st.expander("Rascunho editável", expanded=True):
        edited_resume = st.text_area(
            "Rascunho gerado",
            key=draft_key,
            height=420,
        )
        st.caption("Revise o texto antes de enviar. Mantenha apenas experiências e skills que sejam verdadeiras.")

        review_key = build_state_key(document.filename, result.overall_score, "reviewed")
        reviewed = st.checkbox(
            "Revisei o rascunho e quero gerar o arquivo final.",
            key=review_key,
        )

        if reviewed:
            render_download_options(document.filename, edited_resume)
        else:
            st.info("Depois de revisar o texto, marque a caixa acima para liberar a geração do arquivo final.")


def render_personalization_section(result: AnalysisResult, draft_key: str, job_input: JobInput | None) -> None:
    st.subheader("Personalização da vaga")
    st.markdown(
        "Essa área serve para adaptar o currículo antes da geração final. "
        "O título sugerido funciona melhor no topo do currículo, perto do cabeçalho, e os termos confirmados entram na seção de skills."
    )

    suggested_terms = personalization_terms(result)
    inferred_title = result.job_match.job_title if result.job_match else None
    fallback_title = job_input.title if job_input else None
    default_title = inferred_title or fallback_title or ""

    manual_title_key = f"{draft_key}_manual_title"
    if manual_title_key not in st.session_state:
        st.session_state[manual_title_key] = default_title

    if inferred_title:
        st.markdown(f"- Título sugerido para o topo do currículo: `{inferred_title}`")
    else:
        st.warning("Não conseguimos identificar o título da vaga com segurança. Preencha manualmente abaixo.")

    manual_title = st.text_input(
        "Título da vaga para usar no topo do currículo",
        key=manual_title_key,
        placeholder="Ex.: Engenharia de Dados AWS Sênior",
    ).strip()

    apply_title = st.checkbox(
        "Adicionar o título sugerido no topo do currículo",
        key=f"{draft_key}_apply_title",
        value=bool(default_title),
        disabled=not bool(manual_title),
    )

    selected_terms = st.multiselect(
        "Selecione apenas as skills/termos que você realmente domina para adicionar na seção Skills",
        options=suggested_terms,
        default=suggested_terms[: min(6, len(suggested_terms))],
        key=f"{draft_key}_selected_terms",
    )

    if st.button("Aplicar personalização ao rascunho", key=f"{draft_key}_apply_button", use_container_width=True):
        updated_draft = apply_personalization_to_draft(
            st.session_state[draft_key],
            manual_title if apply_title else None,
            selected_terms,
        )
        st.session_state[draft_key] = updated_draft
        st.toast("Personalização aplicada ao rascunho.")
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
        if term not in ordered:
            ordered.append(term)
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
    match = re.search(r"(?ms)^SKILLS\s*\n(.*?)(?=\n[A-Z][A-Z ]+\n|\Z)", draft_text)
    cleaned_terms = unique_terms(selected_terms)

    if match:
        existing = [item.strip() for item in re.split(r"[,\n;|]", match.group(1)) if item.strip()]
        merged = unique_terms(existing + cleaned_terms)
        replacement = "SKILLS\n" + ", ".join(merged)
        return draft_text[: match.start()] + replacement + draft_text[match.end() :]

    skills_block = "SKILLS\n" + ", ".join(cleaned_terms)
    return draft_text.rstrip() + "\n\n" + skills_block


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


def render_breakdown_cards(metrics: list) -> None:
    for metric in metrics:
        ratio = 0 if metric.max_score == 0 else round((metric.score / metric.max_score) * 100)
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
    return "Precisa de reforço"


def summary_status_copy(score: int) -> str:
    if score >= 80:
        return "Seu currículo já está competitivo e com boa leitura automatizada."
    if score >= 60:
        return "Há uma base boa, com espaço claro para subir o score."
    return "Vale ajustar estrutura e conteúdo antes de usar em processos seletivos."


def build_generated_filename(filename: str, extension: str) -> str:
    base_name = filename.rsplit(".", maxsplit=1)[0]
    return f"{base_name}_otimizado.{extension}"


def build_state_key(filename: str, score: int, suffix: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_-]", "_", filename)
    return f"{sanitized}_{score}_{suffix}"


if __name__ == "__main__":
    main()
