from __future__ import annotations

import math

import streamlit as st

from ats_score_resume.document_parser import ExtractedDocument, UnsupportedFileTypeError, extract_document
from ats_score_resume.exporters import build_docx_resume
from ats_score_resume.job_source import JobSourceError, resolve_job_input
from ats_score_resume.scoring import AnalysisResult, Suggestion, analyze_document, display_section_name, generate_resume_draft


def main() -> None:
    st.set_page_config(page_title="ATS Score Resume", page_icon="A", layout="wide")
    inject_styles()

    st.title("ATS Score Resume")
    st.caption("Analise curriculos com score explicavel de prontidao ATS e aderencia a vagas.")

    with st.sidebar:
        st.subheader("Como o score funciona")
        st.markdown(
            "\n".join(
                [
                    "- `Base ATS`: leitura pelo ATS, estrutura e forca do conteudo.",
                    "- `Aderencia a vaga`: palavras-chave, requisitos e alinhamento com a oportunidade.",
                    "- `Overall`: media ponderada quando a vaga e informada.",
                ]
            )
        )

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
    if not run_analysis:
        return

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
    )
    render_result(result, document)


def render_result(result: AnalysisResult, document: ExtractedDocument) -> None:
    st.success(f"Analise concluida para `{document.filename}`.")

    hero_col, metrics_col = st.columns((1.1, 1), gap="large")
    with hero_col:
        render_gauge("Overall Score", result.overall_score, score_status(result.overall_score))
    with metrics_col:
        st.markdown("<div class='metrics-grid'>", unsafe_allow_html=True)
        render_score_chip("Base ATS", result.resume.score, "Qualidade geral do curriculo para leitura automatizada.")
        if result.job_match:
            render_score_chip("Aderencia a vaga", result.job_match.score, "Conexao entre o seu curriculo e a oportunidade.")
        render_score_chip("Nivel atual", result.overall_score, summary_status_copy(result.overall_score))
        st.markdown("</div>", unsafe_allow_html=True)

    st.subheader("Resumo da analise")
    detected_sections = [display_section_name(section) for section in result.resume.detected_sections]
    missing_sections = [display_section_name(section) for section in result.resume.missing_sections]
    skill_heading = result.resume.section_headings.get("skills")
    heading_note = ""
    if skill_heading:
        heading_note = f" Secao de skills reconhecida como: `{skill_heading}`."

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

    st.subheader("Curriculo otimizado")
    with st.expander("Gerar rascunho com base nas dicas do ATS", expanded=True):
        widget_key = f"resume_draft_{document.filename}_{result.overall_score}"
        if widget_key not in st.session_state:
            st.session_state[widget_key] = generate_resume_draft(document, result)

        edited_resume = st.text_area(
            "Rascunho gerado",
            key=widget_key,
            height=420,
        )
        st.caption("Revise o texto antes de enviar. Mantenha apenas experiencias e skills que sejam verdadeiras.")

        review_key = f"resume_reviewed_{document.filename}_{result.overall_score}"
        reviewed = st.checkbox(
            "Revisei o rascunho e quero gerar o arquivo final.",
            key=review_key,
        )

        if reviewed:
            txt_col, docx_col = st.columns(2)
            with txt_col:
                st.download_button(
                    "Baixar arquivo TXT",
                    data=edited_resume,
                    file_name=build_generated_filename(document.filename, "txt"),
                    mime="text/plain",
                    use_container_width=True,
                )
            with docx_col:
                st.download_button(
                    "Baixar arquivo DOCX",
                    data=build_docx_resume(edited_resume),
                    file_name=build_generated_filename(document.filename, "docx"),
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )
        else:
            st.info("Depois de revisar o texto, marque a caixa acima para liberar a geracao do arquivo final.")


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
        .score-card {
            padding: 18px 20px;
            margin-bottom: 14px;
        }
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
        .score-card .helper {
            color: #475569;
            margin-top: 8px;
            font-size: 0.96rem;
        }
        .suggestion-card {
            padding: 16px 18px;
            margin-bottom: 12px;
            border-left: 6px solid #f59e0b;
        }
        .suggestion-card.priority-media {
            border-left-color: #2563eb;
        }
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
        .suggestion-card .badge-alta {
            background: linear-gradient(135deg, #f97316, #dc2626);
        }
        .suggestion-card .badge-media {
            background: linear-gradient(135deg, #2563eb, #0f766e);
        }
        .suggestion-card .title {
            font-size: 1.08rem;
            font-weight: 700;
            color: #0f172a;
            margin-bottom: 6px;
        }
        .suggestion-card .details,
        .breakdown-card .details {
            color: #334155;
            font-size: 0.97rem;
            line-height: 1.45;
        }
        .breakdown-card {
            padding: 18px 20px;
            margin-bottom: 12px;
        }
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
        .info-card {
            padding: 16px 18px;
            color: #334155;
        }
        .gauge-wrap {
            padding: 16px 8px 8px;
            text-align: center;
        }
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
        .gauge-subtitle {
            color: #475569;
            margin-top: -6px;
            font-size: 0.98rem;
        }
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
        <div class="gauge-title">{title}</div>
        <svg width="240" height="150" viewBox="0 0 240 150" role="img" aria-label="{title} {score} de 100">
            <path d="M 32 120 A 88 88 0 0 1 208 120" fill="none" stroke="#dbeafe" stroke-width="18" stroke-linecap="round"></path>
            <path d="M 32 120 A 88 88 0 0 1 208 120" fill="none" stroke="{color}" stroke-width="18" stroke-linecap="round"
                stroke-dasharray="{circumference:.2f}" stroke-dashoffset="{offset:.2f}"></path>
            <g transform="translate(120 120) rotate({angle:.2f})">
                <line x1="0" y1="0" x2="68" y2="0" stroke="#0f172a" stroke-width="5" stroke-linecap="round"></line>
            </g>
            <circle cx="120" cy="120" r="10" fill="#0f172a"></circle>
        </svg>
        <div class="gauge-score">{score}/100</div>
        <div class="gauge-subtitle">{subtitle}</div>
    </div>
    """
    st.markdown(gauge_html, unsafe_allow_html=True)


def render_score_chip(title: str, score: int, helper: str) -> None:
    st.markdown(
        f"""
        <div class="score-card">
            <div class="eyebrow">{title}</div>
            <div class="value">{score}/100</div>
            <div class="helper">{helper}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_suggestion_card(suggestion: Suggestion) -> None:
    priority_class = "badge-alta" if suggestion.priority == "alta" else "badge-media"
    st.markdown(
        f"""
        <div class="suggestion-card priority-{suggestion.priority}">
            <span class="badge {priority_class}">{suggestion.priority.upper()}</span>
            <div class="title">{suggestion.title}</div>
            <div class="details">{suggestion.details}</div>
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
                <div class="eyebrow">{score_status(ratio)}</div>
                <div class="title">{metric.label}</div>
                <div class="details"><strong>{metric.score}/{metric.max_score}</strong> pontos</div>
                <div class="meter"><div class="meter-fill" style="width:{ratio}%"></div></div>
                <div class="details">{metric.details}</div>
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


if __name__ == "__main__":
    main()
