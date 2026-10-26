# Tarefa: Esquema versão 2 e migração

## Objetivo

Criar o esquema da `v0.2.0` (empresa, candidatura, etapas, vínculos, histórico único, `on_hold`) e migrar sem perda um banco da `v0.1.0`, mantendo o contrato das sete ferramentas.

## Especificação relacionada

`docs/specs/fonte-unica-v0-2-plano.md` (seção "Modelo de dados" e etapa 2); decisão `docs/architecture/decisions/0007-historico-unico-com-origem.md`.

## Pré-condições

- Tarefa 09 concluída.

## Arquivos prováveis

- `src/job_search_mcp/db.py`, `src/job_search_mcp/history.py` (novo)
- `src/job_search_mcp/domain.py`, `src/job_search_mcp/jobs.py`, `src/job_search_mcp/contacts.py`, `src/job_search_mcp/summary.py`
- `tests/test_migration.py` (novo), `tests/fixtures/schema_v1.sql` (novo), testes existentes

## Passos

1. Escrever o esquema versão 2 do plano, com `version` nas tabelas alteráveis, e gravar `PRAGMA user_version = 2` em banco novo.
2. Criar `history.py` com uma função única que compara valores, grava as mudanças e as linhas de `history` (entidade, registro, campo, antes, depois, data, `source_type`, `source_ref`). Vagas e contatos passam a usá-la.
3. Escrever a migração da versão 0 para a 2, aplicada ao abrir o banco:
   - copiar o arquivo do banco para `<nome>.v1.bak` antes de começar;
   - empresas criadas a partir dos textos de `job.company` e `contact.company`, unidas por nome normalizado;
   - recriar `job` (sem os campos de andamento) e criar `application` com eles;
   - recriar `contact` com `company_id` e `role_title`;
   - mover `contact.job_id` para `application_person` com papel `contact` e `confirmed` verdadeiro;
   - mover `job_history` para `history`: `source` livre vira `source_type = user`, com o texto em `source_ref`;
   - tudo numa transação.
4. Ajustar as leituras para juntar vaga, candidatura e empresa, e manter as chaves de saída da `v0.1.0` (`company` continua sendo o nome da empresa). Acrescentar `company_id`.
5. Acrescentar `on_hold` aos status de candidatura e de pessoa, sem follow-up.
6. Ajustar o seed atual para carregar no esquema novo (o formato novo do seed fica para a tarefa 14).
7. Teste de migração: fixture com o SQL da `v0.1.0` mais o seed; conferir contagens, empresas unidas, histórico e vínculos migrados, e a cópia de segurança criada.

## Critérios de conclusão

- [x] Banco da `v0.1.0` migra sem perda e o teste de migração passa.
- [x] As sete ferramentas devolvem as mesmas chaves da `v0.1.0`, mais as aditivas.
- [x] `on_hold` aceito para candidatura e pessoa e fora dos follow-ups.
- [x] Toda alteração de vaga ou pessoa grava em `history`.
- [x] `python tools/scripts/lint_and_tests.py --strict` sem falhas.

## Validação

Data: 2026-10-25. Ambiente: Windows 11, Python 3.12.7 (SQLite 3.45.3) no `.venv` do worktree, instalado com `pip install -e ".[dev]"`.

- `.venv\Scripts\python.exe tools/scripts/lint_and_tests.py --strict`: estrutura e skills válidas, `202 passed` (antes da revisão), `ruff check` sem achados (`All checks passed!`); `ruff format --check src tests` sem diferenças.
- Dos 178 testes anteriores, todos continuam passando. Só foram ajustados os que liam o esquema interno: consultas a `job_history` passam a ler `history` (com o mesmo formato da `v0.1.0` montado na consulta), `SELECT ... FROM job` de campos de andamento passa a ler `application`, `INSERT INTO job (company, ...)` passa a usar `company_id`, a linha de `interaction` ganha `channel` e `source_type` nulos, e as listas de status contam `on_hold` (o teste parametrizado por status ganhou um caso: 179). Nenhum teste de contrato das ferramentas (chaves e valores devolvidos) mudou.
- `tests/test_migration.py` (15 testes depois da revisão): banco criado com `tests/fixtures/schema_v1.sql` (o `SCHEMA` da `v0.1.0`, copiado antes da mudança), o seed carregado do jeito antigo e linhas extras sintéticas (contatos com empresa `"  banco ÁURORA "` e `"Banco  Aurora"`, contato sem empresa, contato com empresa em branco, duas interações e três linhas de `job_history`). Confere: `user_version = 2`, contagens (15 vagas e candidaturas, 12 pessoas, 2 interações, 3 linhas de histórico), sem tabelas antigas, `foreign_key_check` vazio; cópia `job_search.db.v1.bak` com `user_version = 0` e os dados antigos; 16 empresas, com as variantes unidas a Banco Aurora e a empresa em branco como null; 7 vínculos em `application_person` (papel `contact`, confirmado); histórico com `entity = application`, `source_type = user` e o texto original em `source_ref`; `list_jobs` e `list_contacts` do banco migrado iguais aos de um banco novo com o mesmo seed; escrita após a migração; reabrir não migra de novo nem recria a cópia; migração com linha de histórico órfã falha, volta atrás e deixa o banco na versão 0 com as quatro tabelas; banco em memória migra sem cópia.
- `tests/test_history.py` (10 testes): `split_source`, gravação só do que muda com uma única subida de `version`, recusa de entidade, campo ou tipo de origem desconhecidos sem escrever nada, `update_job` com tipo de origem conhecido, `log_interaction` gravando as mudanças da pessoa, `on_hold` sem follow-up e contando como ativo (vaga e pessoa), e a ordem das chaves das leituras.
- `job-search-mcp --seed` com `JOB_SEARCH_DB` num arquivo novo: carrega (16 empresas, 15 vagas e candidaturas, 8 pessoas, 6 vínculos, `user_version = 2`); na segunda vez recusa com código 1.

Decisões de desenho:

- **Versão do esquema.** `db.create_schema` lê `PRAGMA user_version`: 2, nada a fazer; 0 com `job_history`, migra; 0 sem tabelas, cria direto na versão 2; outro valor, `sqlite3.DatabaseError`. É chamada a cada abertura, como antes. A criação e a migração rodam numa transação `BEGIN IMMEDIATE`, e a versão é relida depois de obter a trava de escrita: se outro processo migrou nesse meio-tempo, nada é feito (o `SCHEMA` é executado comando a comando, porque `executescript` faria commit).
- **Migração.** Cópia por `sqlite3.Connection.backup`, lida por uma segunda conexão (a primeira já tem a trava de escrita), para `<arquivo>.v1.bak` ao lado do banco (por exemplo, `job_search.db.v1.bak`). Uma cópia existente nunca é sobrescrita: o próximo nome livre é `<arquivo>.v1.1.bak`, `<arquivo>.v1.2.bak` e assim por diante. Banco em memória não tem cópia. Com `foreign_keys` desligado e `legacy_alter_table` ligado (para `interaction` continuar apontando para `contact`), as tabelas antigas são renomeadas, o esquema novo é criado, os dados copiados e as antigas removidas; `interaction` ganha as colunas por `ALTER TABLE ADD COLUMN`. A candidatura migrada recebe o mesmo id da vaga. Antes de mexer nas tabelas, a migração procura contatos e linhas de `job_history` que apontam para vagas inexistentes e, se houver, para com um erro que lista os ids e o caminho da cópia; antes do commit roda `foreign_key_check`. Qualquer falha desfaz tudo.
- **Relatório da migração.** Vai para stderr (nunca stdout, que carrega o protocolo MCP), depois do commit: uma linha com o caminho da cópia e uma por texto de empresa guardado com outro nome (unido a outra grafia ou sem os espaços das pontas), por exemplo `Company '  banco ÁURORA ' stored as 'Banco Aurora'.`
- **Empresas.** `db.normalize_name` (minúsculas, sem acento, sem espaços nas pontas e com espaços internos repetidos reduzidos a um; esse último item é um desvio pequeno do plano, decidido pelo Supervisor, para que `Banco  Aurora` e `Banco Aurora` sejam a mesma empresa) e `db.ensure_company` (busca por `normalized_name`, cria se faltar). O nome guardado é o primeiro visto: vagas antes de pessoas, por id. Usado pela migração, pelo seed e por `add_job`.
- **Histórico.** `history.record_changes` é o único ponto que grava mudanças: compara, faz um `UPDATE` com só os campos alterados e `version = version + 1`, e grava uma linha de `history` por campo. Entidades e campos permitidos ficam em `history.UPDATABLE_FIELDS` (`application`, `contact`), porque os nomes entram no texto SQL. A entidade é a tabela onde o campo vive: os campos de andamento da vaga são da `application`.
- **Origem.** `history.split_source`: se o texto de `source` for um dos tipos (`domain.SOURCE_TYPES`), vira `source_type` sem referência; senão, `source_type = user` com o texto em `source_ref`. As mudanças feitas por `log_interaction` (pessoa e vaga) usam `source_type = user` e `source_ref = contact_interaction`, o mesmo texto da `v0.1.0`.
- **Retorno `history` de `update_job`.** Mantém as chaves da `v0.1.0`: `job_id` é o id da vaga; `date`, `field`, `old_value` e `new_value` vêm da linha; `source` é `source_ref` quando existe, senão `source_type`. Assim `source="user"` volta `"user"` e um texto livre volta o próprio texto, como antes.
- **Leituras.** Vaga = `job` + `application` + `company`, com as chaves e a ordem da `v0.1.0` (`company` é o nome) e `company_id` aditivo. Pessoa = `contact` + `company`, com `company_id` e `role_title` aditivos; `job_id` é a vaga da primeira candidatura (menor id) ligada à pessoa com papel `contact`, ou null. `list_contacts(company=...)` compara `company.normalized_name` com `db.normalize_name(company)`: ignora maiúsculas (também as acentuadas), acentos e espaços extras, e encontra as pessoas cuja empresa foi unida a outra grafia.
- **`on_hold`.** Acrescentado a `JOB_STATUSES` (depois de `offer`) e a `CONTACT_STATUSES` (antes de `closed`), e aos conjuntos sem follow-up; não entra nos encerrados, então conta como ativo. `jobs_by_status` passa a trazer a chave `on_hold`.
- **Seed.** Os CSV continuam no formato da `v0.1.0`; `load_seed` cria empresa, vaga, candidatura, pessoa e vínculo numa transação, e recusa um `job_id` de contato sem vaga. `--seed` verifica as tabelas `company`, `job`, `contact`, `interaction` e `history`.
- **Fora do escopo.** A tabela `proposal` fica para a tarefa 11, como sugerido. `add_job` não grava histórico (criação, como na `v0.1.0`). `interaction.channel` e `interaction.source_type` ficam nulos até as tarefas que os preenchem. `application_stage` é criada vazia.
- **Mudança de valor.** Uma pessoa com empresa em branco (por exemplo `"   "`) passa a ser lida com `company: null` e `company_id: null`; na `v0.1.0` voltava o texto em branco. As chaves não mudam.
- **README.** Só as listas de status ganharam `on_hold`; a documentação da migração fica para a tarefa 16.

Achados da revisão (PR 19, parecer apto), corrigidos na mesma branch:

| Severidade | Achado | Correção |
|---|---|---|
| Média | `list_contacts(company=...)` usava `company.name = ? COLLATE NOCASE`: uma pessoa com `Banco Áurora`, unida a `Banco Aurora`, sumia do filtro pela grafia original, e `NOCASE` só ignora maiúsculas ASCII. | O filtro compara `company.normalized_name` com `db.normalize_name(company)`. Testes com grafias acentuadas, maiúsculas e espaços extras, no seed e no banco migrado. |
| Baixa | Dois processos abrindo o mesmo banco da versão 0 ao mesmo tempo: o segundo sobrescrevia a `.v1.bak` com o banco já migrado. | `BEGIN IMMEDIATE`, releitura de `user_version` sob a trava antes de copiar, e cópia nunca sobrescrita (sufixo numérico). Testes com duas conexões intercaladas (a segunda leu a versão 0 antes da trava), com duas threads abrindo o banco ao mesmo tempo e com uma `.v1.bak` já existente. |
| Baixa | A falha por referência órfã não dizia quais registros nem onde estava a cópia. | A mensagem lista os ids de contato e de `job_history` e o caminho da cópia. |
| Baixa | `Banco  Aurora` (espaços internos repetidos) virava outra empresa. | `normalize_name` reduz espaços internos repetidos; desvio pequeno do plano, decidido pelo Supervisor. |
| Baixa | A migração não informava o que fez. | Relatório em stderr: caminho da cópia e uma linha por empresa unida ou renomeada. |

Depois das correções: `lint_and_tests.py --strict` com `207 passed` e `All checks passed!`.

## Status

```text
concluída
```
