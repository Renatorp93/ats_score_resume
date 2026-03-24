# Plano de Execucao

Data de inicio: 2026-03-24

## Objetivo

Construir uma aplicacao que:

1. Leia um curriculo em `PDF`, `DOCX` ou `TXT`.
2. Calcule um score de prontidao para ATS.
3. Explique o score por criterio e sugira melhorias.
4. Permita informar uma descricao de vaga ou URL para calcular aderencia entre curriculo e vaga.

## Entregaveis

1. Aplicacao web executavel localmente.
2. Motor de scoring com criterios explicitados em arquivo proprio.
3. Log de decisoes tecnicas e de produto.
4. Testes do nucleo de analise.
5. Documentacao de uso.

## Fases

### Fase 1 - Pesquisa e definicao de criterios

Saidas:

- Consolidar boas praticas de ATS em `docs/METRICAS_ATS.md`.
- Registrar a arquitetura inicial e as decisoes em `docs/DECISOES.md`.

### Fase 2 - Estruturacao do projeto

Saidas:

- Definir stack do MVP.
- Criar estrutura de pastas, configuracao de dependencias e arquivos base.

### Fase 3 - Analise de curriculo

Saidas:

- Extracao de texto de `PDF`, `DOCX` e `TXT`.
- Heuristicas para parsing, estrutura, conteudo e score base.
- Sugestoes acionaveis para melhorar o curriculo.

### Fase 4 - Analise de vaga

Saidas:

- Entrada de descricao textual da vaga.
- Entrada opcional de URL da vaga.
- Calculo de aderencia vaga x curriculo.

### Fase 5 - Qualidade e documentacao

Saidas:

- Testes automatizados do nucleo.
- Atualizacao do `README.md` com instrucoes de execucao.

### Fase 6 - Versionamento

Saidas:

- Commits incrementais por bloco funcional.
- Push final para `origin/main`.

## Plano tecnico inicial

Stack escolhida para o MVP:

- `Python 3.12`
- Interface web simples com `Streamlit`
- Extracao de texto com bibliotecas especificas por formato
- Motor de regras em Python puro para manter o score auditavel

## Riscos mapeados

1. Nao existe um padrao universal de pontuacao ATS; o score precisara ser explicavel e heuristico.
2. Extracao de texto de PDF pode variar de acordo com a qualidade do arquivo.
3. URL de vaga pode ter bloqueios anti-bot; o sistema precisara aceitar texto manual como fallback.

## Criterios de pronto do MVP

1. Usuario consegue subir um curriculo e receber score + explicacao + sugestoes.
2. Usuario consegue informar descricao ou link da vaga e receber um score de aderencia.
3. O sistema registra claramente quais metricas foram usadas.
