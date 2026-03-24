# ATS Score Resume

Aplicacao local para analisar curriculos com foco em compatibilidade com ATS, gerar score explicavel e sugerir melhorias. O sistema tambem permite comparar o curriculo com a descricao de uma vaga ou com a URL da vaga para calcular aderencia.

## O que o MVP faz

1. Le curriculos em `PDF`, `DOCX`, `TXT` e `MD`.
2. Calcula um `ATS Readiness Score` com base em parsing, estrutura e qualidade do conteudo.
3. Sugere modificacoes praticas para aumentar o score.
4. Calcula um `Job Match Score` quando a vaga e informada.
5. Explica o breakdown do score por criterio.

## Stack

- `Python 3.12`
- `Streamlit` para interface
- `PyPDF` e `python-docx` para extracao de texto
- `requests` e `BeautifulSoup` para leitura opcional de URL de vaga

## Como executar

```bash
python -m pip install -e .[dev]
python -m streamlit run app.py
```

Depois disso, abra a URL local mostrada pelo Streamlit no navegador.

## Como testar

```bash
python -m pytest
```

## Documentacao do projeto

- Plano: `docs/PLANEJAMENTO.md`
- Metricas: `docs/METRICAS_ATS.md`
- Decisoes: `docs/DECISOES.md`
