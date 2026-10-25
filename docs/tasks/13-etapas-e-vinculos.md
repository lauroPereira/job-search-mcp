# Tarefa: Etapas e vínculos

## Objetivo

Registrar etapas datadas da candidatura e vínculos pessoa ↔ candidatura com papel, e calcular a prioridade da vaga.

## Especificação relacionada

`docs/specs/fonte-unica-v0-2-plano.md` ("APIs ou interfaces" e etapa 5); caso de uso 2 de `docs/specs/fonte-unica-v0-2.md`.

## Pré-condições

- Tarefa 12 concluída.

## Arquivos prováveis

- `src/job_search_mcp/jobs.py`, `src/job_search_mcp/contacts.py`, `src/job_search_mcp/domain.py`, `src/job_search_mcp/server.py`
- `tests/test_jobs.py`, `tests/test_contacts.py`, `tests/test_server.py`

## Passos

1. Cálculo das mudanças de `jobs_add_stage`:
   - valida tipo, resultado e data (não futura);
   - inclui o novo status da candidatura quando informado;
   - atualiza `last_contact_on` da candidatura quando a data é mais recente.
2. Cálculo das mudanças de `jobs_link_person`:
   - valida papel;
   - recusa vínculo repetido;
   - permite confirmar um vínculo existente.
3. Prioridade derivada da vaga na leitura, conforme o plano: `high`, `medium` ou `low`.
4. Leitura da vaga com `stages` (ordenadas por data) e `people` (com papel e confirmação).
5. `log_interaction` atualiza `last_contact_on` de todas as candidaturas ativas ligadas à pessoa. Na resposta:
   - `job` continua presente: é a vaga quando há uma única candidatura ligada, ou nulo;
   - `jobs` é nova e traz a lista.
6. Registrar `jobs_add_stage` e `jobs_link_person` com propostas.
7. Testes:
   - etapa com e sem status;
   - data futura recusada;
   - vínculo repetido;
   - prioridade derivada (nota e indicação confirmada);
   - interação com pessoa ligada a duas candidaturas.

## Critérios de conclusão

- [x] Caso de uso 2 (registrar uma etapa) funciona com o seed, por proposta e confirmação.
- [x] Caso de uso 3 (recusa da proposta) comprovado em teste.
- [x] A saída de `log_interaction` mantém as chaves da `v0.1.0` no resultado confirmado.
- [x] `python tools/scripts/lint_and_tests.py --strict` sem falhas.

## Validação

Data: 2026-10-25. Ambiente: Windows 11, Python 3.12.7, fastmcp 4.1.0, no `.venv` do worktree, instalado com `pip install -e ".[dev]"`. Somente dados sintéticos (seed e nomes fictícios nos testes).

- `.venv\Scripts\python.exe tools/scripts/lint_and_tests.py --strict`: estrutura e skills válidas, `301 passed` (268 em `develop` + 33 novos), `ruff check` sem achados (`All checks passed!`); `.venv\Scripts\python.exe -m ruff format --check src tests`: `25 files already formatted`.
- `tests/test_domain.py` (9 novos): prioridade derivada nos limites (7,5 → `high`, 7,4 e 7 → `medium`, 6,9 e sem nota → `low`; indicação confirmada → `high` com qualquer nota); listas de tipos de etapa, resultados e papéis iguais às do plano.
- `tests/test_jobs.py` (12 novos): etapa sem status (só a etapa, `last_contact_on` avança, histórico da etapa com origem e data de referência, `base_versions` da candidatura); etapas mais antigas não recuam `last_contact_on` e saem ordenadas por data e id; etapa com status `applied` preenche `applied_on`; erros de validação (tipo, resultado, data futura, data inválida, status, vaga inexistente, origem vazia) sem gravar nada; prioridade só sobe com `referrer` confirmado (recrutador confirmado e indicação não confirmada não contam); vínculo repetido recusado com `duplicate_link` e o vínculo existente, e demais erros sem gravar.
- `tests/test_contacts.py` (2 novos): pessoa ligada a duas candidaturas ativas (uma delas em dois papéis) e a uma encerrada: `base_versions` com o contato e as duas ativas, as duas atualizadas com histórico, a encerrada intocada, `job` nulo e `jobs` com as três; pessoa sem vaga devolve `jobs` vazio.
- `tests/test_server.py` (10 novos, mais as listas de ferramentas, parâmetros, obrigatórios e `readOnlyHint` com as duas novas): **caso de uso 2** pelo cliente MCP com o seed ("fiz a entrevista técnica hoje, foi bem, aguardo retorno" na vaga 4: prévia com a etapa, `hr_interview` → `tech_interview` e o último contato; banco igual antes da confirmação; depois, etapa em `list_jobs` e histórico com origem `conversation`); **caso de uso 3** (`referred` proposto para a Ana, descartado, banco igual e confirmação posterior recusada); data futura, data inválida, tipo, resultado e status inválidos e vaga inexistente sem proposta; vínculo repetido recusado, confirmação de vínculo existente (prévia `not confirmed` → `confirmed`, prioridade `medium` → `high`) e histórico; `log_interaction` com pessoa em duas vagas (`job` nulo, `jobs` com as duas, chaves `contact`, `follow_up`, `job`, `jobs`); proposta de etapa `stale` quando a candidatura muda antes da confirmação; as duas ferramentas novas (quatro variações) no teste parametrizado de retrato do banco igual sem `changes_confirm`.
- `tests/test_history.py` e `tests/test_migration.py` ajustados: a ordem das chaves da vaga inclui `priority`, `stages` e `people` depois das da `v0.1.0`; a comparação banco migrado × banco novo ignora `people`, porque a fixture da `v0.1.0` tem uma pessoa a mais ligada à vaga 1 (conferida à parte).

Decisões de desenho:

- **Planejadores e propostas.** `jobs.plan_add_stage` e `jobs.plan_link_person` seguem o padrão `plan_*` com `domain.Plan` e estão em `proposals.PLANNERS` como `jobs_add_stage` e `jobs_link_person`. A data da etapa passa por `server.past_date` (não futura) e é conferida de novo no planejador contra `reference_date`.
- **Etapa reutiliza `plan_update_job`.** A mudança na candidatura (status informado e `last_contact_on` quando a etapa é mais recente) é calculada por `plan_update_job`, o que traz a mesma validação de status, o preenchimento de `applied_on` ao virar `applied` e o mesmo formato de `history` no resultado. A etapa não tem `version`; a proposta depende só da `version` da candidatura. O histórico da etapa é a criação (`entity: application_stage`, um campo por linha, incluindo `application_id`). Resultado confirmado: `{"stage", "job", "history"}`.
- **Histórico do vínculo.** `application_person` não tem id próprio nem `version` (chave composta, esquema da tarefa 10), e o rowid implícito pode mudar num `VACUUM`. Por isso o vínculo grava uma linha só: `entity: application_person`, `record_id` = id da candidatura, campo `link`, com o vínculo descrito antes e depois ("Nome (contact N) as papel, confirmed/not confirmed"). Assim a criação e a confirmação ficam inequívocas mesmo com várias pessoas na mesma candidatura. Para isso `history.record_lines` grava linhas de prévia como estão. A proposta depende das versões da candidatura e da pessoa.
- **Vínculo repetido.** Mesmo pessoa, papel e candidatura é `duplicate_link` (novo código em `domain.error`, com o vínculo existente em `link`), exceto quando o vínculo não está confirmado e `confirmed=true`: aí a proposta o confirma. Desconfirmar não é suportado. Vínculo novo nasce não confirmado, salvo `confirmed=true`.
- **Prioridade derivada** em `domain.job_priority` (limiares `HIGH_PRIORITY_SCORE` 7,5 e `MEDIUM_PRIORITY_SCORE` 7); só `referrer` com `confirmed` conta como indicação.
- **Leitura da vaga.** `jobs.jobs_from_rows` acrescenta `priority`, `stages` (id, kind, date, result, feedback; por data e id) e `people` (id, name, role, confirmed booleano; por id da pessoa e papel), com duas consultas por lista. É usada por `get_job`, `list_jobs` e pela visão da empresa, então `pending_followups`, `daily_summary` e `network_company_overview` também ganham as chaves, de forma aditiva.
- **`log_interaction`.** Atualiza `last_contact_on` de toda candidatura ativa (status fora de `JOB_CLOSED_STATUSES`) ligada à pessoa em qualquer papel; `base_versions` tem a pessoa e cada candidatura ativa ligada (uma chave por candidatura, mesmo com dois papéis). `job` é a vaga quando a pessoa está ligada a exatamente uma vaga (qualquer status), senão nulo; `jobs` lista todas as vagas ligadas, por id. Diferença em relação à `v0.1.0`: uma vaga encerrada ligada à pessoa deixa de ter o último contato atualizado.
- **Erros de valor fora da lista** (`kind`, `result`, `role`) são `invalid_input` com `valid_values` (`domain.invalid_choice`).

Pendências: README e `docs/case.md` ficam para a tarefa 16, com as notas da versão; a evidência dos casos de uso em `docs/evidence/` (critério da especificação) também fica para a tarefa 16.

## Status

```text
concluída
```
