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
10. Define uma meta de corte para ATS e, opcionalmente, usa IA para reescrever o curriculo ate atingir a meta ou esgotar ganhos seguros.
11. Mostra o que aumentou e o que diminuiu a nota depois da otimizacao.
12. Compara o curriculo original com o otimizado lado a lado, por secao.
13. Permite aprovar manualmente as secoes sugeridas antes de compor o rascunho final editavel.

## Stack

- `Python 3.12`
- `Streamlit` para interface
- `PyPDF` e `python-docx` para extracao de texto
- `requests` e `BeautifulSoup` para leitura opcional de URL de vaga
- `OpenAI Responses API` opcional para reescrita estruturada com IA

## Como executar

```bash
python -m pip install -e .[dev]
python -m streamlit run app.py
```

Depois disso, abra a URL local mostrada pelo Streamlit no navegador.

## IA opcional

Se quiser ativar a reescrita automatica com IA, defina a chave antes de abrir o app:

```bash
set OPENAI_API_KEY=sua-chave
set OPENAI_MODEL=gpt-5-mini
python -m streamlit run app.py
```

Tambem e possivel preencher a chave diretamente na barra lateral do Streamlit.

## Como funciona a meta de corte

- Sem vaga informada: a meta padrao mira um `Base ATS` forte.
- Com vaga informada: o app busca uma combinacao de `Base ATS`, `Overall` e `Aderencia a vaga`.
- A IA para quando a meta e atingida ou quando uma nova rodada deixa de trazer ganho seguro.
- O resultado mostra explicitamente o que subiu e o que caiu na nota para ajudar a decidir se ainda vale insistir na vaga.

## Como testar

```bash
python -m pytest
```

## Documentacao do projeto

- Plano: `docs/PLANEJAMENTO.md`
- Metricas: `docs/METRICAS_ATS.md`
- Decisoes: `docs/DECISOES.md`
