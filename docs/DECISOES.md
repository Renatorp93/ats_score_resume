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
