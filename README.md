# ATS Score Resume

Aplicacao local para analisar curriculos com foco em compatibilidade com ATS, gerar score explicavel e sugerir melhorias. O sistema tambem permite comparar o curriculo com a descricao de uma vaga ou com a URL da vaga para calcular aderencia.

## O que o MVP faz

1. Le curriculos em `PDF`, `DOCX`, `TXT` e `MD`.
2. Calcula um `ATS Readiness Score` com base em parsing, estrutura e qualidade do conteudo.
3. Sugere modificacoes praticas para aumentar o score.
4. Destaca o resultado com painel visual e velocimetro de score.
5. Gera um rascunho de curriculo otimizado com base nas dicas encontradas.
6. Separa a personalizacao da vaga do rascunho principal e permite aplicar apenas o que o usuario confirmar.
7. Permite validar o rascunho e baixar o curriculo final em `TXT`, `MD`, `DOCX` ou `HTML`.
8. Calcula um `Job Match Score` quando a vaga e informada.
9. Explica o breakdown do score por criterio.

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
