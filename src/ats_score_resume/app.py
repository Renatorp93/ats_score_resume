from __future__ import annotations

from dataclasses import asdict

import streamlit as st

from ats_score_resume.document_parser import UnsupportedFileTypeError, extract_document
from ats_score_resume.job_source import JobSourceError, resolve_job_input
from ats_score_resume.scoring import AnalysisResult, analyze_document, generate_resume_draft


def main() -> None:
    st.set_page_config(page_title="ATS Score Resume", page_icon="A", layout="wide")
    st.title("ATS Score Resume")
    st.caption("Analise curriculos com score explicavel de prontidao ATS e aderencia a vagas.")

    with st.sidebar:
        st.subheader("Como o score funciona")
        st.markdown(
            "\n".join(
                [
                    "- `ATS Readiness`: parsing, estrutura e qualidade do conteudo.",
                    "- `Job Match`: cobertura de keywords, requisitos e alinhamento com a vaga.",
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


def render_result(result: AnalysisResult, document) -> None:
    st.success(f"Analise concluida para `{document.filename}`.")
    st.progress(result.overall_score / 100)

    metrics_columns = st.columns(3 if result.job_match else 2)
    metrics_columns[0].metric("Overall Score", f"{result.overall_score}/100")
    metrics_columns[1].metric("ATS Readiness", f"{result.resume.score}/100")
    if result.job_match:
        metrics_columns[2].metric("Job Match", f"{result.job_match.score}/100")

    st.subheader("Resumo da analise")
    st.markdown(
        "\n".join(
            [
                f"- Secoes detectadas: {', '.join(result.resume.detected_sections) or 'nenhuma secao padrao detectada'}",
                f"- Secoes ausentes: {', '.join(result.resume.missing_sections) or 'nenhuma'}",
                f"- Skills detectadas: {', '.join(result.resume.keyword_terms[:8]) or 'nenhuma'}",
            ]
        )
    )

    st.subheader("Sugestoes para aumentar o score")
    if result.suggestions:
        for suggestion in result.suggestions:
            st.markdown(f"- `{suggestion.priority.upper()}` {suggestion.title}: {suggestion.details}")
    else:
        st.markdown("- Nenhuma sugestao critica encontrada.")

    st.subheader("Breakdown do score")
    st.table([asdict(metric) for metric in result.resume.metrics])

    if result.job_match:
        st.subheader("Breakdown de aderencia a vaga")
        st.caption(f"Fonte da vaga: {result.job_match.source}")
        st.table([asdict(metric) for metric in result.job_match.metrics])
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
    with st.expander("Gerar rascunho com base nas dicas do ATS", expanded=False):
        generated_resume = generate_resume_draft(document, result)
        st.caption("Revise o texto antes de enviar. Mantenha apenas experiencias e skills que sejam verdadeiras.")
        st.text_area(
            "Rascunho gerado",
            value=generated_resume,
            height=420,
        )
        st.download_button(
            "Baixar rascunho em TXT",
            data=generated_resume,
            file_name=build_generated_filename(document.filename),
            mime="text/plain",
            use_container_width=True,
        )


def build_generated_filename(filename: str) -> str:
    base_name = filename.rsplit(".", maxsplit=1)[0]
    return f"{base_name}_otimizado.txt"


if __name__ == "__main__":
    main()
