# Metricas ATS

Data da consolidacao: 2026-03-24

## Fontes consultadas

1. Indeed, "How To Write an ATS Resume (With Template and Tips)", atualizado em 2025-12-15:
   https://www.indeed.com/career-advice/resumes-cover-letters/ats-resume-template
2. Indeed, "Get Your Resume Seen With ATS Keywords", atualizado em 2026-01-19:
   https://www.indeed.com/career-advice/resumes-cover-letters/ats-resume-keywords
3. Indeed, "How to Organize Sections of a Resume", atualizado em 2025-12-11:
   https://www.indeed.com/career-advice/resumes-cover-letters/sections-of-a-resume
4. Workable, "What is resume parsing and how an applicant tracking system (ATS) reads a resume)", publicado em 2023-09:
   https://resources.workable.com/stories-and-insights/how-ATS-reads-resumes

## Principios extraidos das fontes

As fontes convergem nos pontos abaixo:

1. ATS prioriza texto extraivel, headings padrao e ausencia de elementos que dificultem parsing.
2. Keywords da vaga sao usadas para ranquear candidatos.
3. Secoes basicas como `Contact Information`, `Summary/Objective`, `Work Experience`, `Education` e `Skills` ajudam o sistema a localizar informacoes.
4. Formatos simples e cronologicos tendem a ser mais compativeis.
5. O curriculo precisa continuar legivel para humanos; logo, nao faz sentido premiar keyword stuffing.

## Modelo de score adotado

Observacao importante:
Nao existe uma formula publica universal de score ATS. O modelo abaixo e uma traducao de boas praticas de mercado para heuristicas de produto. Onde houver inferencia de engenharia, isso sera sinalizado.

### 1. ATS Readiness Score

Score de `0 a 100` calculado sem depender da vaga.

#### 1.1 Compatibilidade de parsing e formato - 30 pontos

1. Tipo de arquivo e seguranca de parsing - 8 pontos
2. Volume de texto extraido e legibilidade minima - 8 pontos
3. Presenca de sinais de formatacao arriscada no texto extraido - 8 pontos
4. Presenca de headings padrao - 6 pontos

Justificativa:
Indeed e Workable destacam formato simples, ausencia de tabelas/colunas/graficos e uso de headings padrao.

#### 1.2 Completude estrutural - 30 pontos

1. Informacoes de contato detectadas - 10 pontos
2. Resumo ou objetivo - 5 pontos
3. Experiencia profissional - 7 pontos
4. Educacao - 4 pontos
5. Skills - 4 pontos

Justificativa:
Indeed lista essas secoes como base de um curriculo bem organizado e compativel com triagem.

#### 1.3 Qualidade de conteudo - 40 pontos

1. Datas e cronologia identificaveis - 8 pontos
2. Evidencias de impacto quantificado - 10 pontos
3. Bullets orientados a acao - 8 pontos
4. Densidade minima de hard skills relevantes - 8 pontos
5. Sinais de excesso de repeticao ou stuffing - 6 pontos

Justificativa:
Parte deste bloco e inferencia de engenharia para transformar orientacoes de clareza, relevancia e leitura humana em score pratico.

### 2. Job Match Score

Score de `0 a 100` calculado quando houver descricao da vaga ou URL.

#### 2.1 Cobertura de keywords - 35 pontos

Comparar termos recorrentes da vaga com o curriculo.

#### 2.2 Cobertura de requisitos obrigatorios - 25 pontos

Detectar hard skills, certificacoes, ferramentas e termos explicitamente exigidos.

#### 2.3 Alinhamento de titulo e senioridade - 15 pontos

Verificar proximidade entre titulo alvo da vaga e titulos presentes no curriculo.

#### 2.4 Evidencias de experiencia e educacao - 15 pontos

Verificar se os temas exigidos aparecem em experiencia, educacao ou certificacoes.

#### 2.5 Fidelidade terminologica - 10 pontos

Premiar uso de grafias consistentes, siglas e formas expandidas quando apropriado.

Justificativa:
Indeed recomenda extrair keywords da vaga, usa-las nas secoes corretas e manter grafia, numeros e abreviacoes consistentes.

### 3. Overall Score

1. Sem vaga informada:
   `Overall Score = ATS Readiness Score`
2. Com vaga informada:
   `Overall Score = 45% ATS Readiness + 55% Job Match`

Justificativa:
Inferencia de produto. Aderencia a vaga deve pesar mais quando houver contexto real de candidatura.

## Regras de sugestao

As sugestoes do sistema devem ser derivadas diretamente dos gaps detectados, por exemplo:

1. Falta de secao `Skills` -> sugerir criacao da secao com termos relevantes.
2. Poucas evidencias numericas -> sugerir bullets com impacto mensuravel.
3. Baixa cobertura de keywords da vaga -> sugerir incorporar termos da descricao em resumo, experiencia e skills.
4. Arquivo em formato menos seguro para ATS -> sugerir `DOCX` quando a vaga nao exigir outro formato.

## Limites conhecidos

1. O score nao garante aprovacao em ATS real.
2. Diferentes ATS usam algoritmos distintos e configuracoes diferentes por empresa.
3. O score do sistema deve ser apresentado como indicativo e explicavel, nao como verdade absoluta.
