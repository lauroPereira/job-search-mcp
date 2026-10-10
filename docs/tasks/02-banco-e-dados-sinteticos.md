# Tarefa: Banco SQLite e dados sintéticos

## Objetivo

Criar o esquema do banco, a conexão e a carga de dados de demonstração sintéticos.

## Especificação relacionada

`docs/specs/servidor-mcp-busca-de-emprego-plano.md` (etapa 2, seção "Modelo de dados").

## Pré-condições

- Tarefa 01 concluída.

## Arquivos prováveis

- `src/job_search_mcp/db.py`
- `data/seed/jobs.csv`, `data/seed/contacts.csv`
- `tests/conftest.py`, `tests/test_db.py`

## Passos

1. Em `db.py`, criar `connect(path)` que abre o SQLite com chaves estrangeiras ligadas e linhas acessíveis por nome.
2. Criar `create_schema(connection)` com as tabelas `job`, `contact`, `interaction` e `job_history` do plano, incluindo a restrição de unicidade em `job.url` (campo obrigatório).
3. Resolver o caminho padrão do banco pela variável `JOB_SEARCH_DB`, com padrão `data/local/job_search.db` ancorado na raiz do projeto (não no diretório de trabalho).
4. Escrever `data/seed/jobs.csv` (cerca de 12 vagas) e `data/seed/contacts.csv` (cerca de 8 contatos) com dados fictícios: empresas inventadas (por exemplo, "Banco Aurora" e "Loja Horizonte") e nomes genéricos. Cobrir todos os status e datas que gerem itens vencidos, a vencer e em dia para uma data de referência fixa.
5. Criar `load_seed(connection)` que lê os CSV e insere os registros em uma única transação (só para banco vazio).
6. Em `tests/conftest.py`, criar uma fixture com banco em diretório temporário, esquema criado e seed carregado, e outra com a data de referência fixa.
7. Testar: esquema criado, seed carregado com as contagens esperadas e link duplicado rejeitado pelo banco.

## Critérios de conclusão

- [x] O banco é criado do zero por `create_schema` sem erro.
- [x] A carga do seed resulta nas contagens documentadas no teste.
- [x] Inserir um link repetido levanta erro de integridade.
- [x] Inserir uma vaga sem link levanta erro de integridade.
- [x] Uma segunda carga do seed falha sem deixar carga parcial.
- [x] O caminho padrão do banco não depende do diretório de trabalho, e `JOB_SEARCH_DB` o sobrescreve.
- [x] Nenhum arquivo de banco aparece em `git status` depois dos testes.
- [x] Os CSV não contêm nomes de pessoas ou de empresas reais.

## Validação

Executada em 2026-10-10, no Windows 11, com Python 3.12.7 no ambiente virtual `.venv`. A tabela abaixo é da reexecução feita depois da revisão do pull request, com o ambiente recriado e as correções da tarefa 01 incorporadas (`fastmcp==4.1.0`).

| Comando | Resultado observado |
|---|---|
| `python -m pytest` | `15 passed in 0.90s` (14 em `tests/test_db.py`, 1 em `tests/test_smoke.py`; código 0) |
| `python -m ruff check .` | `All checks passed!` (código 0) |
| `python tools/scripts/lint_and_tests.py --strict` | pytest `15 passed`, ruff `All checks passed!`, `Skills válidas.`, `Validação estrita concluída sem falhas.` (código 0) |
| `git status --short -uall` depois dos testes | só os arquivos alterados da tarefa; nenhum arquivo de banco |
| `find . -name "*.db" -o -name "*.sqlite*"` (fora de `.venv`) | nenhum arquivo encontrado; `data/` continua só com `seed/` |

Como cada critério foi comprovado:

- Esquema do zero: `test_create_schema_creates_the_four_tables`.
- Contagens do seed: `test_seed_loads_expected_counts` (15 vagas, 8 contatos, 0 interações, 0 linhas de histórico, e a contagem por status).
- Link repetido: `test_duplicate_url_is_rejected` (`sqlite3.IntegrityError`).
- Vaga sem link: `test_job_without_url_is_rejected` (`sqlite3.IntegrityError`).
- Segunda carga do seed: `test_second_seed_load_fails_and_keeps_the_first_load` (a segunda chamada levanta `sqlite3.IntegrityError` e as contagens continuam 15 e 8) e `test_failed_seed_load_leaves_no_partial_data` (com um contato conflitante já gravado, as vagas chegam a ser inseridas, a carga falha nos contatos e a transação é desfeita: 0 vagas no banco).
- Caminho padrão: `test_default_db_path_is_anchored_at_project_root` (sem a variável e com o diretório de trabalho trocado para um temporário, o caminho é absoluto e igual a `<raiz do projeto>/data/local/job_search.db`; o teste só calcula o caminho, não abre banco) e `test_default_db_path_uses_environment_variable` e `test_connect_without_path_uses_environment_variable` (com a variável, `connect()` sem argumento abre o banco no diretório temporário indicado).
- Banco fora do repositório: os testes usam `tmp_path`; `test_test_database_lives_in_temporary_directory` falha se o banco de teste não estiver em diretório temporário.
- Dados fictícios: conferência manual dos CSV. As empresas são inventadas, os nomes de pessoas usam sobrenomes como "Exemplo", "Modelo" e "Teste", e os links usam o domínio reservado `example.com`. Os nomes inventados não foram comparados com cadastros de empresas existentes; o responsável aceitou o risco de homonímia e decidiu manter os nomes, sem teste automático de privacidade.

Dados do seed para a data de referência fixa **2026-03-16** (fixture `reference_date`), segundo as regras da especificação (vaga: último contato ou candidatura mais 7 dias; contato: última interação mais 6 dias):

| Follow-up em 2026-03-16 | Vagas (id) | Contatos (id) |
|---|---|---|
| Vencido | 1, 5 | 1, 4 |
| A vencer em até 2 dias | 2, 3, 7 | 2, 7 |
| Em dia | 4, 6 | 3 |
| Sem follow-up (status não gera ou encerra) | 8 a 15 | 5, 6, 8 |

A vaga 2 não tem último contato: o follow-up parte da data da candidatura. A classificação acima é a intenção do seed; as regras só serão implementadas e testadas nas tarefas 03 a 05.

Desvios e decisões:

- O seed tem 15 vagas, e não "cerca de 12": há 13 status de vaga, e foram mantidas duas vagas em `applied` (uma delas sem último contato) e duas em `to_apply` (para a ordenação da fila por nota).
- `jobs.csv` traz a coluna `id`, para que `contacts.csv` aponte a vaga vinculada por `job_id`.
- `connect(path)` cria o diretório do banco quando ele não existe (o padrão `data/local/` não é versionado) e, sem argumento, usa `default_db_path()`.
- O caminho padrão é ancorado na raiz do projeto (`PROJECT_ROOT`, o mesmo critério usado para localizar `data/seed/`), e não no diretório de trabalho; `JOB_SEARCH_DB` continua sobrescrevendo. Vale para a instalação editável, como o seed.
- `load_seed` é só para banco vazio: não é idempotente (ids fixos e links únicos), e a segunda carga falha com erro de integridade sem gravar nada. Ela lê de `data/seed/` na raiz do repositório (funciona na instalação editável); empacotar os CSV fica para quando houver distribuição.
- `job.url` é `NOT NULL` além de único (o plano dizia só "único"): sem isso o SQLite aceitaria várias vagas sem link, e a regra de duplicidade deixaria de valer. O seed já trazia link em todas as vagas e não mudou.
- `created_at` é gravado em UTC no formato `AAAA-MM-DD HH:MM:SS` (o de `CURRENT_TIMESTAMP`), registrado em comentário no esquema.
- O esquema não tem `CHECK` para status: a lista fechada é validada no domínio (tarefa 03).

## Status

```text
concluída
```
