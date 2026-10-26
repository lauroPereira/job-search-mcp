# Tarefa: Gravação em duas etapas

## Objetivo

Fazer toda ferramenta de escrita devolver uma proposta e só gravar com `changes_confirm`, recusando propostas desatualizadas ou vencidas.

## Especificação relacionada

`docs/specs/fonte-unica-v0-2-plano.md` (decisões técnicas, "APIs ou interfaces" e etapa 3); decisão `docs/architecture/decisions/0006-gravacao-em-duas-etapas.md`.

## Pré-condições

- Tarefa 10 concluída.

## Arquivos prováveis

- `src/job_search_mcp/proposals.py` (novo), `src/job_search_mcp/db.py` (tabela `proposal`)
- `src/job_search_mcp/jobs.py`, `src/job_search_mcp/contacts.py`, `src/job_search_mcp/server.py`
- `tests/test_proposals.py` (novo), `tests/test_server.py`, `tests/test_jobs.py`, `tests/test_contacts.py`

## Passos

1. Separar, em `add_job`, `update_job` e `log_interaction`, o cálculo das mudanças (puro, sem gravar) da aplicação. A mesma função de cálculo serve à prévia e à confirmação.
2. Criar `proposals.py`:
   - `create`: grava argumentos, prévia, versões lidas e expiração (`proposals.ttl_hours` da configuração);
   - `confirm`: recalcula e compara versões e prévia; aplica numa transação; marca `applied`;
   - `discard`;
   - `list_pending`: marca as vencidas como `expired`.
3. Erros novos: `stale_proposal`, `expired_proposal` e `not_found` para propostas.
4. No servidor:
   - as três ferramentas de escrita passam a devolver `{"proposal": {"id", "tool", "changes", "expires_at"}}`;
   - registrar `changes_confirm`, `changes_discard` e `changes_list_pending`.
5. `source` aceita os tipos de origem do plano; texto livre continua aceito como `user`, com o texto em `source_ref`; vazio é recusado.
6. Testes:
   - para cada ferramenta de escrita, retrato do banco igual antes e depois da proposta;
   - confirmação aplica e grava histórico;
   - proposta desatualizada e proposta vencida são recusadas;
   - descarte não altera nada.

## Critérios de conclusão

- [x] Nenhuma ferramenta de escrita altera o banco sem `changes_confirm` (teste).
- [x] Confirmação de proposta desatualizada devolve `stale_proposal` (teste).
- [x] Proposta vencida devolve `expired_proposal` (teste).
- [x] Escrita sem origem é recusada (teste).
- [x] `python tools/scripts/lint_and_tests.py --strict` sem falhas.

## Validação

Data: 2026-10-25. Ambiente: Windows 11, Python 3.12.7 (SQLite 3.45.3) no `.venv` do worktree, instalado com `pip install -e ".[dev]"`.

- `.venv\Scripts\python.exe tools/scripts/lint_and_tests.py --strict`: estrutura e skills válidas, `230 passed`, `ruff check` sem achados (`All checks passed!`); `ruff format --check src tests` sem diferenças.
- Dos 207 testes anteriores (em `develop`), os das três ferramentas de escrita passam a propor e confirmar: nos testes de domínio (`test_jobs.py`, `test_contacts.py`, `test_summary.py`, `test_history.py`, `test_migration.py`), `jobs.add_job(...)` virou `write(connection, jobs.plan_add_job(..., reference_date=...))` (e o mesmo para `plan_update_job` e `plan_log_interaction`), com `tests/helpers.py::write` aplicando o plano numa transação; nos testes do servidor, `confirmed(...)` chama a ferramenta e depois `changes_confirm`. Asserções de resultado não mudaram. `test_db.py` passou a esperar a tabela `proposal`, e os testes de lista de ferramentas, parâmetros e `readOnlyHint` incluem as três `changes_*` e o `source` de `add_job`.
- `tests/test_proposals.py` (17 testes): para cada ferramenta de escrita, retrato de todas as tabelas exceto `proposal` igual antes e depois da proposta, e confirmação que aplica, grava histórico e marca `applied`; prévia de `update_job` e resultado no formato da `v0.1.0`; prévia e histórico de criação de `add_job` (empresa nova, vaga, candidatura); erros de validação sem proposta (inclusive `source` vazio); proposta desatualizada por versão (`stale_proposal`, sem alterar nada, marcada `stale`), por prévia diferente (empresa criada por outra proposta) e por operação que passou a falhar (URL duplicada, com `reason`); proposta vencida (`expired_proposal` com o relógio 24 h depois, marcada `expired`, descarte também recusado); validade vinda de `Settings.proposal_ttl_hours`; `list_pending` marcando as vencidas; descarte sem alterar nada e sem poder confirmar depois; confirmar duas vezes não reaplica (`not_found`, `status: applied`); id inexistente (`not_found`); falha durante a aplicação desfaz tudo e mantém a proposta pendente; banco v2 sem a tabela `proposal` a recebe ao abrir.
- `tests/test_server.py` (novos): pelo cliente MCP em memória, para cada ferramenta de escrita, retrato igual após a proposta e após `changes_list_pending`, chaves da proposta e de cada mudança, `expires_at` 24 h depois, confirmação que aplica e grava histórico com `source_type`, segunda confirmação recusada; `changes_discard`; `stale_proposal`, `expired_proposal` (relógio do servidor trocado) e `not_found`; `source` vazio recusado em `add_job` e `update_job`; `source="print"` gravado no histórico da vaga criada.

Decisões de desenho:

- **Cálculo separado da aplicação.** `jobs.plan_add_job`, `jobs.plan_update_job` e `contacts.plan_log_interaction` validam e calculam sem gravar e devolvem um erro estruturado ou um `domain.Plan` com `changes` (a prévia), `base_versions` (`"entidade:id"` → `version` lida) e `apply` (grava sem commit e devolve o resultado da `v0.1.0`). As antigas `add_job`, `update_job` e `log_interaction` do domínio foram substituídas, sem código morto; os testes de domínio aplicam o plano pelo auxiliar `write`.
- **Prévia.** Lista de `{entity, record_id, field, old_value, new_value}`; `record_id` é null em criação. `history.diff` calcula a prévia de alteração (os mesmos campos que `record_changes` grava) e `history.creation` a de criação (campos informados). `update_job` sem mudança real gera proposta com `changes` vazio; confirmada, devolve a vaga e `history` vazio.
- **Proposta.** `proposals.create` grava id (`secrets.token_urlsafe(16)`), ferramenta, argumentos, prévia e versões em JSON canônico (`sort_keys`), status `pending`, `created_at` e `expires_at` em UTC no formato `YYYY-MM-DD HH:MM:SS`, com `proposals.ttl_hours` da configuração (24 por padrão). Os argumentos guardam a data de referência do dia da proposta (`reference_date` de `add_job` e `update_job`, `date` de `log_interaction`), para que a confirmação aplique exatamente o que foi mostrado, mesmo em outro dia.
- **Confirmação.** `proposals.confirm` abre `BEGIN IMMEDIATE`, marca as vencidas, recalcula o plano com os argumentos guardados e compara prévia e versões em JSON canônico; se diferirem, ou se a operação agora falhar (por exemplo, URL cadastrada nesse meio-tempo, com o erro em `reason`), marca `stale` e devolve `stale_proposal`; senão aplica e marca `applied` na mesma transação. Proposta já aplicada ou descartada devolve `not_found` com a chave `status` (o plano prevê só `stale_proposal`, `expired_proposal` e `not_found`); vencida, `expired_proposal`; desatualizada, `stale_proposal` de novo.
- **Tabela `proposal` em bancos v2 existentes.** Fica no `SCHEMA` (versão 2, sem nova migração): como todo comando é `CREATE ... IF NOT EXISTS`, `db.create_schema` roda o `SCHEMA` também quando o banco já está na versão 2, o que cria a tabela num banco feito pela tarefa 10 e não faz nada num banco completo. A `v0.2.0` ainda não foi publicada, então não há banco v2 sem a tabela fora de desenvolvimento.
- **Histórico de criação.** `add_job` passa a gravar histórico: uma linha por campo informado da empresa (se for nova), da vaga e da candidatura, com `old_value` null (`history.record_creation`). A interação não ganha linhas: é um registro só de inclusão, e o histórico cobre os registros alteráveis (com `version`). A prévia de `add_job` mostra a criação da empresa quando ela ainda não existe; duas propostas para a mesma empresa nova deixam a segunda desatualizada depois da primeira confirmação, o que é o comportamento seguro.
- **Origem.** `add_job` ganha `source` opcional (padrão `user`, aditivo); `update_job` mantém `source` obrigatório. Tipo conhecido (`domain.SOURCE_TYPES`) vai para `source_type`; texto livre vira `user` com o texto em `source_ref`; vazio ou só espaços é recusado com `invalid_input`. `log_interaction` não ganhou parâmetro: as mudanças continuam com `source_type = user` e `source_ref = contact_interaction`.
- **Relógio.** `server.now()` (UTC) é a única leitura de hora, ao lado de `server.today()`; `proposals.py` recebe `now`, e o teste de módulos sem relógio continua passando.
- **Servidor.** As três ferramentas devolvem `{"proposal": {"id", "tool", "changes", "expires_at"}}`; `changes_confirm`, `changes_discard` e `changes_list_pending` (esta com `readOnlyHint`, embora marque as vencidas) foram registradas; descrições e `instructions` explicam o fluxo proposta → confirmação.

Achados da revisão (PR 20, parecer apto, sem achados altos ou médios), tratados na mesma branch:

| # | Severidade | Achado | Decisão |
|---|---|---|---|
| 1 | Baixa | Banco da `v0.1.0` com referência órfã: cada abertura (toda chamada MCP) criava uma cópia nova (`.v1.bak`, `.v1.1.bak`...). | Corrigido: a checagem de órfãos (só leitura) roda antes da cópia; a falha não copia nada e diz que o banco ficou inalterado. Teste com três aberturas seguidas: nenhuma cópia. |
| 2 | Baixa | Propostas descartadas, vencidas ou desatualizadas guardavam argumentos e prévia (notas pessoais) indefinidamente. | Corrigido: ao descartar, vencer ou ficar `stale`, `arguments` e `preview` passam a `'{}'` (as colunas são `NOT NULL` em bancos v2 que já têm a tabela); ficam id, ferramenta, status, versões e datas. Propostas aplicadas mantêm os dados. Teste. |
| 3 | Baixa | `changes_list_pending` tem `readOnlyHint` mas marca as vencidas como `expired`. | Mantido como decisão: o plano a classifica como leitura; marcar a validade é manutenção da própria tabela de propostas e não altera dados de vagas, pessoas ou histórico. |
| 4 | Baixa | `update_job` sem mudança real gera proposta com `changes` vazio. | Mantido como decisão: o fluxo fica igual para o agente (sempre há proposta), e a confirmação devolve a vaga com `history` vazio, sem gravar nada. |
| 5 | Baixa | O plano dizia que as ferramentas de escrita "não ganham parâmetro novo", mas `add_job` ganhou `source`. | Corrigido em `docs/specs/fonte-unica-v0-2-plano.md` (decisão técnica e tabela de ferramentas): `source` opcional, aditivo. |
| 6 | Baixa | Contagem de testes anteriores errada nesta tarefa (213; `develop` tinha 207). | Corrigido acima. |
| 7 | Baixa | Linha longa na docstring de `domain.error`. | Corrigido. |
| 8 | Baixa | O servidor não distingue um agente que confirma sem perguntar à pessoa. | Limitação registrada para as notas da versão (tarefa 16): a barreira garante que nada é gravado sem `changes_confirm`, mas a aprovação humana entre a proposta e a confirmação depende do cliente. |

Depois das correções: `.venv\Scripts\python.exe tools/scripts/lint_and_tests.py --strict` com `231 passed`, `All checks passed!` e `ruff format --check src tests` sem diferenças.

Pendências: o README e `docs/case.md` ainda descrevem as ferramentas de escrita gravando direto; a atualização fica para a tarefa 16, com as notas da versão.

## Status

```text
concluída
```
