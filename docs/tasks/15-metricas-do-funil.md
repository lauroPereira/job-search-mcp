# Tarefa: Métricas do funil

## Objetivo

Expor `jobs_funnel_metrics`, com as métricas do funil calculadas por consulta.

## Especificação relacionada

`docs/specs/fonte-unica-v0-2-plano.md` ("APIs ou interfaces" e etapa 7); caso de uso 6 de `docs/specs/fonte-unica-v0-2.md`.

## Pré-condições

- Tarefa 14 concluída (seed novo com etapas).

## Arquivos prováveis

- `src/job_search_mcp/summary.py`, `src/job_search_mcp/server.py`
- `tests/test_summary.py`, `tests/test_server.py`

## Passos

1. Calcular, para uma data de referência:
   - candidaturas ativas por status (`on_hold` conta como ativa);
   - em entrevista;
   - taxa de entrevista, conforme a definição do plano;
   - candidaturas por semana nas últimas `weeks` semanas;
   - ativas com e sem indicação confirmada;
   - follow-ups vencidos e a vencer;
   - dias até `goals.deadline`;
   - metas da configuração, quando houver.
2. Registrar `jobs_funnel_metrics` como ferramenta de leitura.
3. Testes com o seed e data fixa, comparando com valores contados à mão e anotados no teste; taxa de entrevista sem candidaturas devolve nulo, sem divisão por zero.

## Critérios de conclusão

- [x] As métricas batem com a contagem feita à mão sobre o seed (teste).
- [x] Funciona sem configuração (sem prazo-âncora e sem metas).
- [x] `python tools/scripts/lint_and_tests.py --strict` sem falhas.

## Validação

Data: 2026-10-25. Ambiente: Windows 11, Python do `.venv` do worktree, branch `feat/15-metricas-do-funil` a partir de `develop` (tarefas 09 a 14 integradas).

Comandos e resultados:

- `.venv\Scripts\python.exe tools/scripts/lint_and_tests.py --strict` — 346 testes passaram (após as correções da revisão), `ruff check` sem achados, "Validação estrita concluída sem falhas".
- `.venv\Scripts\ruff.exe format --check src tests` — 27 arquivos já formatados; nenhuma linha nova acima de 100 colunas.

Testes novos:

- `tests/test_summary.py`: métricas sobre o seed em 2026-03-16 comparadas com a contagem à mão, anotada em comentário (ativas por status, fila 4, em andamento 7 com indicação 1 e sem 6, em entrevista 3, taxa 6/10 = 0,6, semanas W09 a W12 = 1, 2, 1, 0 com W12 parcial de 1 dia, follow-ups vencidos 2+2 e a vencer 3+2); oito semanas, semana de domingo (completa), contagem limitada à data de referência e virada de ano; etapa cancelada não conta e etapa `offer` conta; banco vazio com taxa nula; metas e prazo da configuração (45 dias; -2 depois do prazo); `on_hold` e etapa nova mudando as contagens; `weeks` e data inválidos; nenhuma escrita.
- `tests/test_server.py`: `jobs_funnel_metrics` na lista de ferramentas, parâmetros (`reference_date`, `weeks` inteiro com padrão 4), dica de leitura; caso de uso 6 pelo cliente MCP, sem configuração e com `JOB_SEARCH_CONFIG` apontando para metas e prazo, com retrato do banco igual antes e depois; erros `invalid_date` e `invalid_input`.

Definições adotadas (`summary.funnel_metrics`):

- **Ativas:** todo status não encerrado (`domain.JOB_CLOSED_STATUSES`), `on_hold` incluído; a lista vai no retorno como `active_statuses`, com `active_by_status` e `active_total`.
- **Fila (`queue`):** ativas ainda não candidatadas — `suggested`, `to_apply` e `blocked` — com `statuses` e `total`.
- **Em andamento (`in_progress`):** ativas de `applied` até `offer`, mais `on_hold`, com `statuses`, `total`, `with_referral` e `without_referral`.
- **Em entrevista (`in_interview`):** ativas hoje em `hr_interview`, `tech_interview` ou `manager_interview`.
- **Taxa de entrevista (decisão do Supervisor, registrada no plano):** candidaturas com `applied_on` cujo status é `hr_interview`, `tech_interview`, `manager_interview`, `offer` ou `hired`, ou que têm etapa `hr`, `technical`, `manager` ou `offer` com resultado diferente de `cancelled`, divididas pelas candidaturas com `applied_on` (encerradas incluídas); arredondada a 4 casas; `null` quando não há candidaturas com `applied_on`.
- **Candidaturas por semana:** semanas ISO de segunda a domingo, contadas por `applied_on` até a data de referência (encerradas incluídas), da mais antiga para a da data de referência, com zeros; cada semana traz `days_elapsed` e `partial` (verdadeiro enquanto a semana da referência tem menos de 7 dias decorridos; num domingo ela está completa); `weeks` de 1 a 52, fora disso `invalid_input`.
- **Com e sem indicação:** em andamento com ao menos um vínculo `referrer` confirmado; as demais em andamento ficam "sem".
- **Follow-ups:** contagem de vagas e pessoas vencidas e a vencer, reaproveitando `summary._pending` com 2 dias de antecedência (o mesmo de `daily_summary`); a lista fica em `pending_followups`.
- **Prazo e metas:** `goals.deadline`, `goals.applications_per_week` e `goals.interview_rate` da configuração local; `null` quando ausentes. A ferramenta não recebe prazo por parâmetro, como no plano.
- Só as semanas, os follow-ups e o prazo dependem da data de referência; as demais contagens são o estado atual dos dados (dito na descrição do parâmetro e na docstring).

Achados da revisão (PR 24, parecer não apto por um achado alto), corrigidos na mesma branch:

| # | Severidade | Achado | Decisão |
|---|---|---|---|
| 1 | Alta | A taxa de entrevista caía quando a candidatura avançava: `offer` e `hired` sem etapas não contavam. | Corrigido conforme decisão do Supervisor: conta status `hr_interview`, `tech_interview`, `manager_interview`, `offer` ou `hired`, ou etapa `hr`, `technical`, `manager` ou `offer` com resultado diferente de `cancelled`. Seed passa a 6/10 (a vaga 12, `hired`, entra). Interpretação registrada no plano. Testes com etapa cancelada e etapa `offer`. |
| 2 | Média | Ativas misturavam a fila (ainda não candidatadas) com o andamento, e a indicação era contada sobre todas. | Corrigido: mantido `active_by_status`; acrescentados `queue` (`suggested`, `to_apply`, `blocked`) e `in_progress` (`applied` até `offer`, mais `on_hold`), com `with_referral` e `without_referral` sobre `in_progress`. Chaves documentadas na ferramenta e na função. |
| 3 | Baixa | Semanas contavam `applied_on` posterior à data de referência e não indicavam a semana incompleta. | Corrigido: contagem até a data de referência; cada semana traz `days_elapsed` e `partial`. A descrição de `reference_date` diz que só semanas, follow-ups e prazo dependem da data. |
| 4 | Baixa | A docstring não dizia onde ver a lista dos follow-ups. | Corrigido: indica `pending_followups`. |

## Status

```text
concluída
```
