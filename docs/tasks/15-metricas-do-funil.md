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

- `.venv\Scripts\python.exe tools/scripts/lint_and_tests.py --strict` — 345 testes passaram, `ruff check` sem achados, "Validação estrita concluída sem falhas".
- `.venv\Scripts\ruff.exe format --check src tests` — 27 arquivos já formatados; nenhuma linha nova acima de 100 colunas.

Testes novos:

- `tests/test_summary.py`: métricas sobre o seed em 2026-03-16 comparadas com a contagem à mão, anotada em comentário (ativas por status, em entrevista, taxa 5/10 = 0,5, semanas W09 a W12 = 1, 2, 1, 0, indicação 1/10, follow-ups vencidos 2+2 e a vencer 3+2); oito semanas, semana de domingo e virada de ano; banco vazio com taxa nula; metas e prazo da configuração (45 dias; -2 depois do prazo); `on_hold` e etapa nova mudando as contagens; `weeks` e data inválidos; nenhuma escrita.
- `tests/test_server.py`: `jobs_funnel_metrics` na lista de ferramentas, parâmetros (`reference_date`, `weeks` inteiro com padrão 4), dica de leitura; caso de uso 6 pelo cliente MCP, sem configuração e com `JOB_SEARCH_CONFIG` apontando para metas e prazo, com retrato do banco igual antes e depois; erros `invalid_date` e `invalid_input`.

Definições adotadas (`summary.funnel_metrics`):

- **Ativas:** todo status não encerrado (`domain.JOB_CLOSED_STATUSES`), `on_hold` incluído; a lista vai no retorno como `active_statuses`. Inclui `suggested`, `to_apply` e `blocked`.
- **Em entrevista (`in_interview`):** ativas hoje em `hr_interview`, `tech_interview` ou `manager_interview`.
- **Taxa de entrevista:** conforme o plano — candidaturas com `applied_on` que tiveram etapa `hr`, `technical` ou `manager` (qualquer resultado) ou estão em status de entrevista, divididas pelas candidaturas com `applied_on` (encerradas incluídas); arredondada a 4 casas; `null` quando não há candidaturas com `applied_on`. Uma candidatura em `offer` ou `hired` sem etapas registradas não conta (no seed, a vaga 12).
- **Candidaturas por semana:** semanas ISO de segunda a domingo, contadas por `applied_on` (encerradas incluídas), da mais antiga para a da data de referência, com zeros; `weeks` de 1 a 52, fora disso `invalid_input`.
- **Com e sem indicação:** ativas com ao menos um vínculo `referrer` confirmado; as demais ficam "sem".
- **Follow-ups:** contagem de vagas e pessoas vencidas e a vencer, reaproveitando `summary._pending` com 2 dias de antecedência (o mesmo de `daily_summary`).
- **Prazo e metas:** `goals.deadline`, `goals.applications_per_week` e `goals.interview_rate` da configuração local; `null` quando ausentes. A ferramenta não recebe prazo por parâmetro, como no plano.
- As contagens não filtram por data além da semana: o retrato é o estado atual dos dados.

## Status

```text
concluída
```
