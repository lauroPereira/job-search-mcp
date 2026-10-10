# Tarefa: Regras de domínio e operações de vagas

## Objetivo

Implementar os status válidos, a regra de follow-up e as operações de listar, registrar e atualizar vagas, com histórico.

## Especificação relacionada

`docs/specs/servidor-mcp-busca-de-emprego.md` (requisitos de vaga, status, follow-up e histórico) e o plano.

## Pré-condições

- Tarefa 02 concluída.

## Arquivos prováveis

- `src/job_search_mcp/domain.py`
- `src/job_search_mcp/jobs.py`
- `tests/test_domain.py`, `tests/test_jobs.py`

## Passos

1. Em `domain.py`, declarar os status de vaga e de contato e os conjuntos "encerrado" e "sem follow-up" do plano.
2. Implementar `job_follow_up(applied_on, last_contact_on)` (último contato mais 7 dias; sem contato, candidatura mais 7) e `contact_follow_up(last_contact_on)` (mais 6 dias).
3. Implementar `classify(follow_up, reference_date, days_ahead=2)` devolvendo overdue, due_soon ou on_track.
4. Em `jobs.py`, implementar `list_jobs` com os filtros de status, trilha e nota mínima.
5. Implementar `add_job`, devolvendo erro estruturado de duplicidade com a vaga existente quando o link já estiver cadastrado.
6. Implementar `update_job`, validando o status e gravando uma linha em `job_history` para cada campo alterado, com valor anterior, novo e origem.
7. Escrever os testes de cada regra com a data de referência fixa.

## Critérios de conclusão

- [x] Vaga com último contato há 7 dias é classificada como vencida; com 5 dias, como a vencer; com 2 dias, em dia.
- [x] Vaga sem último contato usa a data da candidatura.
- [x] Status inválido devolve erro com a lista de status válidos e não altera a vaga.
- [x] Link duplicado devolve erro de duplicidade e não cria vaga.
- [x] Mudar o status gera uma linha de histórico com valor anterior e novo.
- [x] Nenhuma função lê a data atual por conta própria.

## Validação

Executada em 2026-10-10, no Windows 11, com Python 3.12.7 no ambiente virtual `.venv`.

| Comando | Resultado observado |
|---|---|
| `python -m pytest` | `60 passed in 2.63s` (14 em `tests/test_db.py`, 29 em `tests/test_domain.py`, 16 em `tests/test_jobs.py`, 1 em `tests/test_smoke.py`; código 0) |
| `python -m ruff check .` | `All checks passed!` (código 0) |
| `python tools/scripts/lint_and_tests.py --strict` | pytest `60 passed`, ruff `All checks passed!`, `Skills válidas.`, `Validação estrita concluída sem falhas.` (código 0) |
| `git status --short -uall` depois dos testes | só os arquivos da tarefa; nenhum arquivo de banco |
| `find . -name "*.db" -o -name "*.sqlite*"` (fora de `.venv`) | nenhum arquivo encontrado |

Como cada critério foi comprovado:

- Classificação por dias: `test_classify_job_by_days_since_last_contact` (com a data fixa 2026-03-16: 7, 8 e 10 dias, `overdue`; 5 e 6 dias, `due_soon`; 0, 2 e 4 dias, `on_track`) e `test_classify_respects_days_ahead`.
- Vaga sem último contato: `test_job_follow_up_without_contact_uses_application_date`, `test_classify_job_without_last_contact_uses_application_date` e, com o seed, `test_list_jobs_includes_the_calculated_follow_up` (vaga 2).
- Status inválido: `test_update_job_with_invalid_status_returns_error_and_changes_nothing` (erro `invalid_status` com `valid_statuses`, vaga igual à de antes e nenhum histórico), `test_invalid_status_error_lists_the_valid_statuses` e `test_list_jobs_with_invalid_status_returns_error`.
- Link duplicado: `test_add_job_with_duplicate_url_returns_error_and_creates_nothing` (erro `duplicate_url` com a vaga existente; a contagem continua 15) e `test_add_job_twice_with_the_same_url_keeps_only_the_first`.
- Histórico: `test_update_job_status_generates_history_with_old_and_new_value` (linha com `to_apply` e `applied`, data e origem, conferida também na tabela `job_history`), `test_update_job_records_one_history_line_per_changed_field` e `test_update_job_without_real_change_generates_no_history`.
- Data atual: `test_domain_modules_do_not_read_the_current_date` procura chamadas de relógio no código de `domain.py` e `jobs.py`; as funções recebem `reference_date`. Ver a ressalva sobre `created_at` abaixo.

Formato de erro de negócio (definido uma vez, em `domain.error`): dicionário com `error` (código estável) e `detail` (mensagem), mais chaves de contexto quando houver. Códigos desta tarefa: `invalid_status` (com `valid_statuses`), `duplicate_url` (com `job`, a vaga existente), `not_found`, `invalid_date` e `invalid_input`.

Desvios e decisões:

- `job_follow_up` e `contact_follow_up` aceitam um `status` opcional além dos parâmetros da tarefa: quando informado e o status encerra ou não gera follow-up, devolvem `None`. Assim a regra "status encerrado não tem follow-up" fica em um só lugar para as tarefas 04 e 05.
- A conversão de data em texto ISO para `date` ficou em `db.to_date`, o ponto único previsto no plano (`db.py` não estava na lista de arquivos prováveis da tarefa).
- `update_job` recebe `reference_date` (não está na tabela de parâmetros da ferramenta no plano): é a data gravada no histórico, e a ferramenta da tarefa 06 passará a data atual.
- `update_job` só gera histórico para campo cujo valor mudou de fato, e grava histórico de todos os campos alterados (`status`, `next_step`, `applied_on`, `last_contact_on`), não só de status e próximo passo. Campo não informado (`None`) não é alterado; não há como limpar um campo nesta versão.
- `add_job` cria a vaga no status `suggested` (o plano não define o status inicial nem dá parâmetro de status à ferramenta) e recusa `company`, `title` ou `url` vazios com `invalid_input`. A comparação de duplicidade é pelo link exato, sem espaços nas pontas.
- `list_jobs` devolve erro `invalid_status` para filtro de status fora da lista, em vez de lista vazia. Cada vaga devolvida traz o campo calculado `follow_up` (texto ISO ou `None`).
- Datas inválidas em `applied_on` e `last_contact_on` devolvem `invalid_date` sem alterar a vaga. `track` e `score` não são validados (a especificação só fecha a lista de status).
- Ressalva sobre a data atual: `created_at` de uma vaga nova continua vindo do padrão `CURRENT_TIMESTAMP` do esquema (tarefa 02). Nenhuma função Python lê o relógio, mas o banco carimba a criação; `created_at` não participa de nenhuma regra.
- Ajustes de documentação pedidos pelo responsável, incluídos neste pull request: no plano, `url` passou a "texto, único, obrigatório" e o item "Privacidade" saiu da estratégia de testes; na especificação, o critério de aceitação de privacidade foi reescrito.

## Status

```text
concluída
```
