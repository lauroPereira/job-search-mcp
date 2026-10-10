# Tarefa: Contatos e interações

## Objetivo

Implementar a listagem de contatos e o registro de interações, com atualização do follow-up e da vaga vinculada.

## Especificação relacionada

`docs/specs/servidor-mcp-busca-de-emprego.md` (caso de uso "Registrar uma conversa") e o plano.

## Pré-condições

- Tarefa 03 concluída.

## Arquivos prováveis

- `src/job_search_mcp/contacts.py`
- `tests/test_contacts.py`

## Passos

1. Implementar `list_contacts` com filtros de status e empresa, devolvendo também o follow-up calculado.
2. Implementar `log_interaction(contact_id, summary, date, status=None, next_step=None)`: grava a interação, atualiza a data do último contato do contato e, se informados, o status e o próximo passo.
3. Quando o contato tiver `job_id`, atualizar a data do último contato da vaga e gravar a mudança no histórico da vaga, com origem "interação com contato".
4. Devolver o contato atualizado, o novo follow-up e a vaga vinculada, quando houver.
5. Testar: interação simples, interação com vaga vinculada, contato inexistente e status inválido.

## Critérios de conclusão

- [x] Registrar uma interação move o follow-up do contato para a data da interação mais 6 dias.
- [x] Contato vinculado a uma vaga atualiza a data do último contato da vaga.
- [x] Contato inexistente devolve erro estruturado.
- [x] Contato em status closed ou to_contact não tem follow-up.

## Validação

Executada em 2026-10-10, no Windows 11, com Python 3.12.7 no ambiente virtual `.venv`, sobre a branch da tarefa 03 (pull request #5, ainda não integrado em `develop`).

| Comando | Resultado observado |
|---|---|
| `python -m pytest` | `73 passed in 8.30s` (13 em `tests/test_contacts.py`, 14 em `tests/test_db.py`, 29 em `tests/test_domain.py`, 16 em `tests/test_jobs.py`, 1 em `tests/test_smoke.py`; código 0) |
| `python -m ruff check .` | `All checks passed!` (código 0) |
| `python tools/scripts/lint_and_tests.py --strict` | pytest `73 passed`, ruff `All checks passed!`, `Skills válidas.`, `Validação estrita concluída sem falhas.` (código 0) |
| `git status --short -uall` depois dos testes | só os arquivos da tarefa; nenhum arquivo de banco |
| `find . -name "*.db" -o -name "*.sqlite*"` (fora de `.venv`) | nenhum arquivo encontrado |

Como cada critério foi comprovado:

- Follow-up do contato: `test_log_interaction_moves_follow_up_to_interaction_date_plus_six_days` (interação em 2026-03-16, follow-up em 2026-03-22, e a linha gravada em `interaction`) e `test_log_interaction_accepts_iso_text_and_updates_status_and_next_step`.
- Vaga vinculada: `test_log_interaction_updates_last_contact_of_linked_job_with_history` (a vaga 1 passa de 2026-03-09 para 2026-03-16, com uma linha em `job_history` com valor anterior, novo e origem) e `test_log_interaction_sets_last_contact_of_linked_job_that_had_none` (vaga 2, que não tinha último contato).
- Contato inexistente: `test_log_interaction_unknown_contact_returns_error` (erro `not_found`, nenhuma interação gravada).
- Status sem follow-up: `test_contacts_in_closed_or_to_contact_status_have_no_follow_up`, `test_list_contacts_returns_all_seed_contacts_with_follow_up` (contatos 5, 6 e 8 sem follow-up; o 6 tem data de último contato e está `closed`) e `test_log_interaction_that_leaves_contact_in_status_without_follow_up`.
- Status inválido (passo 5): `test_log_interaction_with_invalid_status_returns_error_and_changes_nothing` (erro `invalid_status` com `valid_statuses`; contato, vaga, interações e histórico inalterados).
- Data atual: `test_domain_modules_do_not_read_the_current_date` (tarefa 03) percorre todos os módulos do pacote, e passou a cobrir `contacts.py`.

Desvios e decisões:

- A origem gravada no histórico da vaga é `contact_interaction` (constante `contacts.INTERACTION_SOURCE`), e não o texto "interação com contato" da tarefa, pela convenção do projeto de manter em inglês os valores gravados pelo código.
- A data do último contato nunca volta no tempo: registrar uma interação com data anterior à do último contato grava a interação, mas mantém a data mais recente no contato e na vaga, sem linha de histórico (`test_log_interaction_older_than_last_contact_keeps_the_most_recent_dates`). A tarefa não tratava desse caso.
- A data gravada em `job_history` é a data da interação (`log_interaction` não recebe outra data de referência).
- `log_interaction` devolve um dicionário com `contact`, `follow_up` (texto ISO ou `None`) e `job` (`None` quando não há vaga vinculada). Resumo vazio devolve `invalid_input`; data ausente ou inválida devolve `invalid_date`.
- O parâmetro `date` é obrigatório nesta camada; o padrão "hoje" do plano fica para a ferramenta (tarefa 06).
- `list_contacts` devolve erro `invalid_status` para filtro de status fora da lista. O filtro de empresa compara o nome inteiro, sem diferenciar maiúsculas de minúsculas em letras sem acento (`COLLATE NOCASE` do SQLite).
- A gravação da interação, do contato e da vaga acontece em uma única transação; para isso `contacts.py` reutiliza `jobs.apply_job_changes`, que não faz commit.

## Status

```text
concluída
```
