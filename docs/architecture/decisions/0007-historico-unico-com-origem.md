# 0007. Histórico único com origem obrigatória

## Título

Toda alteração de qualquer entidade gera uma linha num histórico único, com valor anterior, valor novo, data e origem.

## Status

```text
aceita
```

Aceita pelo autor em 2026-10-25 (discovery do [modelo de domínios](../../specs/modelo-de-dominios.md), A3).

## Contexto

Na `v0.1.0` só as vagas têm histórico (`job_history`). No uso real, só a planilha de candidaturas tinha log; mudanças de contatos e do plano de estudos ficavam em observações de texto, e o histórico de status precisava ser reconstruído à mão.

## Decisão

- Uma tabela de histórico para todas as entidades: entidade, registro, campo, valor anterior, valor novo, data e origem.
- A origem tem tipo (conversa, print, áudio, e-mail, reunião, importação, usuário) e referência opcional, e é obrigatória em toda escrita.
- O histórico atual de vagas é migrado para a tabela única.
- As datas de entrada em cada status e etapa saem do histórico, o que permite métricas do funil por consulta.

## Alternativas consideradas

- **Uma tabela de histórico por entidade.** Descartada: repete esquema e código.
- **Guardar só o estado atual.** Descartada: perde a rastreabilidade que o uso real mostrou ser necessária.

## Consequências

- Qualquer pergunta "quando e por que isso mudou?" tem resposta.
- Métricas como taxa de entrevista e tempo em cada etapa passam a ser calculáveis.
- Valores antigos ficam guardados; dados sensíveis no histórico seguem a mesma regra do banco (só local).

## Data

2026-10-25
