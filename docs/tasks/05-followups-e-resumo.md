# Tarefa: Follow-ups pendentes e resumo do dia

## Objetivo

Implementar as consultas que respondem "o que pede atenção" e "o que fazer hoje".

## Especificação relacionada

`docs/specs/servidor-mcp-busca-de-emprego.md` (casos de uso "Resumo da manhã" e "Cobrança pendente") e o plano.

## Pré-condições

- Tarefa 04 concluída.

## Arquivos prováveis

- `src/job_search_mcp/summary.py`
- `tests/test_summary.py`

## Passos

1. Implementar `pending_followups(connection, reference_date, days_ahead=2)`, devolvendo vagas e contatos com situação overdue ou due_soon, ordenados por data de follow-up.
2. Excluir vagas e contatos em status que não geram follow-up.
3. Implementar `daily_summary(connection, reference_date, deadline=None)`: contagem de vagas por status, contagem de contatos ativos, itens vencidos, itens a vencer, fila de candidatura (suggested e to_apply) ordenada por nota decrescente e, se houver prazo, os dias restantes.
4. Testar com o seed e a data fixa, conferindo números e ordem.

## Critérios de conclusão

- [x] Vaga encerrada não aparece em `pending_followups`.
- [x] Os itens vêm ordenados do follow-up mais antigo para o mais recente.
- [x] A fila de candidatura vem ordenada por nota, da maior para a menor.
- [x] As contagens do resumo batem com o seed para a data fixa.
- [x] Com prazo informado, o resumo devolve os dias restantes.

## Validação

Executada em 2026-10-10, no Windows 11, com Python 3.12.7 no ambiente virtual `.venv`, sobre a branch da tarefa 04 (pull requests #5 e #6, ainda não integrados em `develop`).

| Comando | Resultado observado |
|---|---|
| `python -m pytest` | `86 passed in 4.32s` (13 em `tests/test_contacts.py`, 14 em `tests/test_db.py`, 29 em `tests/test_domain.py`, 16 em `tests/test_jobs.py`, 1 em `tests/test_smoke.py`, 13 em `tests/test_summary.py`; código 0) |
| `python -m ruff check .` | `All checks passed!` (código 0) |
| `python tools/scripts/lint_and_tests.py --strict` | pytest `86 passed`, ruff `All checks passed!`, `Skills válidas.`, `Validação estrita concluída sem falhas.` (código 0) |
| `git status --short -uall` depois dos testes | só os arquivos da tarefa; nenhum arquivo de banco |
| `find . -name "*.db" -o -name "*.sqlite*"` (fora de `.venv`) | nenhum arquivo encontrado |

Como cada critério foi comprovado:

- Vaga encerrada fora de `pending_followups`: `test_closed_and_not_started_jobs_and_contacts_are_left_out` (com data de referência em 2027, todo follow-up está vencido, e só aparecem as vagas 1 a 7 e os contatos 1, 2, 3, 4 e 7; as vagas 12, 13 e 14 estão encerradas e têm data de último contato) e `test_job_that_gets_closed_leaves_the_pending_followups` (a vaga 5 some da lista depois de passar a `rejected`).
- Ordem por follow-up: `test_pending_followups_lists_overdue_and_due_soon_from_the_seed` (ordem exata, com data e situação de cada item) e `test_pending_followups_are_ordered_from_oldest_to_most_recent`.
- Fila por nota: `test_application_queue_is_ordered_by_score_from_highest_to_lowest` (vagas 8, 9 e 10, com notas 9.5, 7.8 e 5.5) e `test_application_queue_puts_jobs_without_score_last`.
- Contagens do resumo: `test_daily_summary_counts_match_the_seed` (contagem por status igual à do seed, total de 15 vagas, 7 contatos ativos, vencidos e a vencer iguais à tabela da tarefa 02) e `test_daily_summary_overdue_and_due_soon_match_pending_followups`.
- Prazo: `test_daily_summary_with_deadline_returns_days_left` (prazo em 2026-03-31 devolve 15 dias; no próprio dia, 0; prazo passado, número negativo).

Resultado com o seed na data fixa 2026-03-16, igual à intenção registrada na tarefa 02:

| Situação | Vagas (id, na ordem devolvida) | Contatos (id, na ordem devolvida) |
|---|---|---|
| `overdue` | 5, 1 | 1, 4 |
| `due_soon` | 7, 2, 3 | 2, 7 |

Formato dos retornos:

- `pending_followups`: `reference_date`, `days_ahead`, `jobs` e `contacts`; cada item é a vaga ou o contato com `follow_up` e `state`.
- `daily_summary`: `reference_date`, `jobs_by_status`, `active_contacts`, `overdue` e `due_soon` (cada um com `jobs` e `contacts`), `application_queue`, `deadline` e `days_to_deadline`.

Desvios e decisões:

- "Contatos ativos" foi interpretado como contatos que não estão em `closed` (7 no seed), incluindo os `to_contact`. A tarefa não define o termo.
- `jobs_by_status` traz os 13 status, na ordem do domínio, inclusive os que tiverem zero vagas.
- Empates na ordem (mesma data de follow-up, mesma nota) são resolvidos pelo `id`; vaga sem nota vai para o fim da fila.
- `daily_summary` usa a janela padrão de 2 dias para "a vencer"; a tarefa não prevê `days_ahead` no resumo.
- `days_to_deadline` é a diferença em dias entre o prazo e a data de referência, e fica negativo quando o prazo já passou. Sem prazo, `deadline` e `days_to_deadline` vêm `None`.
- `reference_date` e `deadline` aceitam `date` ou texto ISO; valor inválido devolve o erro estruturado `invalid_date`. `reference_date` é obrigatório nesta camada; o padrão "hoje" do plano fica para a ferramenta (tarefa 06).
- As consultas não gravam nada no banco (`test_summary_does_not_write_to_the_database`).
- O seed não precisou de ajuste.

### Correções da revisão (pull request #7)

Executadas em 2026-10-10, no mesmo ambiente, depois de trazer por merge as correções das tarefas 03 e 04 (pull requests #5 e #6).

| Comando | Resultado observado |
|---|---|
| `python -m pytest` | `101 passed` (16 em `tests/test_contacts.py`, 14 em `tests/test_db.py`, 29 em `tests/test_domain.py`, 25 em `tests/test_jobs.py`, 1 em `tests/test_smoke.py`, 16 em `tests/test_summary.py`; código 0) |
| `python -m ruff check .` | `All checks passed!` (código 0) |
| `python tools/scripts/lint_and_tests.py --strict` | pytest `101 passed`, ruff `All checks passed!`, `Skills válidas.`, `Validação estrita concluída sem falhas.` (código 0) |
| `python -m pytest tests/test_summary.py` sem a regra da nota nula na chave de ordenação (alteração temporária, desfeita) | `1 failed, 15 passed`: falha `test_application_queue_puts_score_zero_before_jobs_without_score` |
| `python -m pytest tests/test_summary.py` com o desempate invertido (`-id`, alteração temporária, desfeita) | `1 failed, 15 passed`: falha `test_application_queue_breaks_score_ties_by_id` |

O que mudou:

- O teste `test_application_queue_puts_jobs_without_score_last` passava mesmo sem a regra "vaga sem nota vai para o fim", porque nota nula tratada como zero já ficava depois das notas positivas do seed. Teste novo: `test_application_queue_puts_score_zero_before_jobs_without_score` cria, no banco temporário, uma vaga sem nota e depois uma com nota 0 (id maior) e confere que a de nota 0 vem antes. Sem a regra, as duas empatariam em zero e o `id` poria a sem nota na frente.
- Teste novo de empate: `test_application_queue_breaks_score_ties_by_id` (três vagas com nota 7.8, em status diferentes, e duas sem nota, sempre com o menor `id` primeiro). Limite deste teste: `list_jobs` já devolve por `id` e a ordenação do Python é estável, então ele não distingue "desempate explícito por `id`" de "sem desempate"; ele pega um desempate diferente (por exemplo, `id` decrescente).
- As vagas desses testes são criadas dentro do próprio teste com `add_job`; `data/seed/` não foi alterado.
- `daily_summary` deixou de ler vagas e contatos duas vezes: antes chamava `pending_followups` (que lê as duas listas) e depois `list_jobs` e `list_contacts` de novo; agora lê cada lista uma vez e reaproveita para contagens, pendências e fila. O retorno é o mesmo (os testes anteriores do resumo passam sem alteração) e a ordem de validação também: primeiro `reference_date`, depois `deadline`. Teste: `test_daily_summary_reads_jobs_and_contacts_only_once`. A janela padrão virou a constante `summary.DEFAULT_DAYS_AHEAD` (2).
- Efeito das correções das tarefas anteriores nesta: nenhum teste do resumo precisou mudar. `test_job_that_gets_closed_leaves_the_pending_followups` usa `rejected`, que não aciona o preenchimento de `applied_on`.

## Status

```text
concluída
```
