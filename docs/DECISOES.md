# Log de Decisoes

## 2026-03-24

### D001 - Comecar pelo modelo de metricas antes do codigo

Contexto:
O usuario pediu explicitamente pesquisa previa sobre metricas de ATS e como ranquear curriculos.

Decisao:
Formalizar primeiro o plano e o conjunto de metricas em arquivos versionados.

Motivo:
Evita que a implementacao nasca com score arbitrario e sem rastreabilidade.

### D002 - Separar score de prontidao ATS e score de aderencia a vaga

Contexto:
O produto precisa funcionar tanto sem vaga quanto com descricao/link da vaga.

Decisao:
Criar dois scores complementares:

1. `ATS Readiness Score`
2. `Job Match Score`

Motivo:
Permite entregar valor imediatamente com o curriculo isolado e, depois, aprofundar a analise quando houver contexto da vaga.

### D003 - Adotar heuristicas explicaveis em vez de tentar simular um ATS proprietario

Contexto:
Nao existe uma formula publica universal de score ATS.

Decisao:
Construir um motor de regras transparente com pesos documentados.

Motivo:
O sistema fica auditavel, ajustavel e mais honesto com o usuario final.

### D004 - Escolher Python com interface web simples para o MVP

Contexto:
O repositorio esta vazio e a entrega precisa sair de forma incremental.

Decisao:
Seguir com `Python 3.12` e uma interface web leve.

Motivo:
Acelera o MVP, simplifica parsing de arquivos e deixa espaco para evolucao posterior para API ou frontend dedicado.

### D005 - Usar Streamlit como interface do MVP

Contexto:
Era necessario escolher rapidamente uma forma de expor upload de arquivo, score e sugestoes.

Decisao:
Usar `Streamlit` na primeira versao da aplicacao.

Motivo:
Entrega uma interface local funcional com pouco codigo de infraestrutura e deixa o foco no motor de analise.

### D006 - Suportar `PDF`, `DOCX`, `TXT` e `MD` no MVP

Contexto:
O produto precisa ler curriculos reais, mas tambem ser facil de testar.

Decisao:
Aceitar `PDF` e `DOCX` como formatos principais e `TXT`/`MD` como formatos auxiliares para testes e depuracao.

Motivo:
Equilibra realismo de uso com simplicidade para desenvolvimento e testes.

### D007 - Fazer o score com heuristicas deterministicas e nao com modelo generativo

Contexto:
O usuario pediu metricas explicitas e um arquivo com os criterios utilizados.

Decisao:
Implementar o score com regras e pesos fixos, deixando LLM fora do calculo principal.

Motivo:
Mantem o resultado auditavel, reproduzivel e facil de explicar.

### D008 - Criar um `app.py` raiz para facilitar a execucao do Streamlit

Contexto:
Projetos com layout `src/` nem sempre resolvem imports automaticamente quando o Streamlit executa o script dentro do pacote.

Decisao:
Adicionar um arquivo `app.py` na raiz que injeta `src/` no `sys.path` e delega para a aplicacao principal.

Motivo:
Simplifica a experiencia de execucao com `streamlit run app.py` e reduz atrito para quem clonar o repositorio.

### D009 - Gerar um rascunho otimizado sem inventar experiencia

Contexto:
O proximo passo pedido foi permitir a geracao do curriculo a partir das dicas encontradas.

Decisao:
Gerar um rascunho editavel com estrutura ATS, reaproveitando o conteudo extraido do curriculo original e adicionando placeholders e notas de customizacao quando faltarem dados.

Motivo:
Entrega valor pratico imediatamente sem correr o risco de inventar skills, resultados ou experiencias que a pessoa nao possui.

### D010 - Dar preferencia visual a cards e gauge no resultado

Contexto:
O breakdown em tabela estava tecnico demais e pouco amigavel para leitura rapida.

Decisao:
Substituir a tabela por cards com linguagem mais humana e adicionar um velocimetro para o score geral.

Motivo:
Facilita a interpretacao do resultado e deixa a experiencia mais clara e atraente.

### D011 - Separar a personalizacao da vaga do rascunho final

Contexto:
O bloco `PERSONALIZACAO PARA ESTA VAGA` nao deveria aparecer no corpo final do curriculo.

Decisao:
Mover a personalizacao para uma sessao propria antes do rascunho, com aplicacao explicita pelo usuario.

Motivo:
Mantem o curriculo final limpo e evita que instrucoes internas vazem para o documento exportado.

### D012 - Combinar deteccao automatica e titulo manual da vaga

Contexto:
Algumas paginas de vaga retornam ruidos como `Clear text` ou falham em expor o titulo correto no HTML extraido.

Decisao:
Melhorar a deteccao do titulo usando `meta`, `title` e `h1`, e abrir um campo manual no app quando a identificacao nao for confiavel.

Motivo:
Evita travar a personalizacao da vaga e deixa o usuario no controle quando a automacao nao encontra um titulo valido.

### D013 - Explicar os gaps do score em modo compacto e expansivel

Contexto:
O breakdown visual mostrava a nota por categoria, mas ainda faltava mostrar com clareza o que exatamente estava pesando contra o score.

Decisao:
Adicionar um resumo curto por categoria e um expander com os pontos faltantes mais relevantes.

Motivo:
Ajuda o usuario a agir sobre o score sem precisar inferir sozinho o que melhorar em cada bloco.

### D014 - Preservar a estrutura humana do rascunho ao aplicar personalizacao

Contexto:
Adicionar skills ao rascunho por regex simples podia capturar secoes seguintes e degradar a leitura humana do curriculo.

Decisao:
Atualizar a personalizacao para operar por secoes do documento, preservando headings, blocos e espacamento.

Motivo:
O curriculo precisa continuar legivel para recrutadores humanos, nao apenas para ATS.

### D015 - Reescrever bullets genericos e filtrar ruido de job boards

Contexto:
O rascunho otimizado ainda podia sair com frases nominais demais, e algumas paginas de vaga traziam termos ruidosos como `brazil`, `jobs` e `ago` para dentro do score.

Decisao:
Passar a converter descricoes comuns em bullets com verbos de acao, formatar skills sugeridas com grafia tecnica mais natural e excluir termos de navegacao/job board da extracao de keywords.

Motivo:
Melhora a leitura humana do curriculo gerado e evita que o score reaja a ruido que nao representa requisito real da vaga.

### D016 - Usar arquitetura hibrida para otimizar ate uma meta de corte

Contexto:
As heuristicas explicaveis ajudam a auditar a nota, mas so renomear secoes e ajustar regex nao basta para entregar um curriculo mais pronto para recrutadores humanos.

Decisao:
Manter o score deterministico como fonte de verdade e adicionar uma camada opcional de IA para reescrita estruturada, com guardrails para nao inventar fatos, rodando em loop ate atingir a meta de corte ou ate os ganhos seguros se esgotarem.

Motivo:
Combina auditabilidade, controle de risco e uma reescrita muito mais contextual, alem de mostrar com clareza o que subiu, o que caiu e se ainda faz sentido insistir na vaga.

### D017 - Comparar original e otimizado por secao

Contexto:
Quando a IA ou o motor heuristico reescrevem o curriculo, o usuario precisa validar rapido se as mudancas ainda representam fielmente sua experiencia.

Decisao:
Adicionar uma comparacao lado a lado entre o curriculo original e o otimizado, com resumo de secoes alteradas e detalhes por secao mostrando o que entrou e o que saiu.

Motivo:
Deixa a revisao mais segura, acelera a aprovacao humana e reduz o risco de exportar um texto que melhorou a nota, mas perdeu fidelidade.
