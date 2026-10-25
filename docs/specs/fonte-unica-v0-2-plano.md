# Plano: fonte única (v0.2)

## Especificação relacionada

`docs/specs/fonte-unica-v0-2.md`, com o [modelo de domínios](modelo-de-dominios.md) e as decisões 0005 a 0008.

## Decisões técnicas

- **Candidatura 1:1 com a vaga.** Toda vaga nasce com uma candidatura, que guarda o andamento: status, datas, currículo e pretensão enviados, próximo passo. A vaga fica com o que descreve o anúncio (empresa, título, link, trilha, nota). Atende "no máximo uma candidatura ativa" sem a ideia de vaga sem candidatura, e mantém as ferramentas da `v0.1.0` com o mesmo formato: elas leem vaga e candidatura juntas.
- **A tabela `contact` continua com esse nome.** Ela passa a representar a pessoa do domínio Network; renomear só trocaria nomes, sem ganho.
- **Versão do esquema em `PRAGMA user_version`.** O banco da `v0.1.0` tem versão 0; ao abrir, o servidor aplica a migração para a versão 2 numa transação única. Banco novo é criado direto na versão 2.
- **Gravação em duas etapas (decisão 0006) com tabela de propostas e versão por registro.** Cada tabela alterável ganha a coluna `version`, incrementada a cada gravação. A ferramenta de escrita valida, calcula a prévia e grava uma proposta com os argumentos, a prévia e as versões lidas. `changes_confirm` reaplica a operação só se as versões não mudaram; caso contrário devolve `stale_proposal`. A confirmação é uma ferramenta à parte, o que mantém os argumentos da `v0.1.0`; a única mudança de parâmetro é aditiva: `add_job` ganhou `source` opcional (padrão `user`) na tarefa 11, para que a criação também tenha origem no histórico.
- **Histórico único (decisão 0007).** Tabela `history` com `entity`, `record_id`, `field`, `old_value`, `new_value`, `date`, `source_type` e `source_ref`. Um único ponto do código (`history.py`) grava alterações de qualquer entidade; `job_history` é migrada e removida.
- **Configuração local em TOML (decisão 0008).** Lida com `tomllib`, da biblioteca padrão, no caminho de `JOB_SEARCH_CONFIG`. Sem o arquivo, valem os padrões. O repositório traz `config.example.toml` com valores fictícios. Responde à questão Q2 da especificação.
- **Expiração das propostas: 24 horas, configurável.** A aprovação humana pode esperar a pessoa voltar à conversa; propostas vencidas são marcadas ao consultar. Responde à questão Q1 da especificação.
- **Importação e exportação pela linha de comando, não por ferramenta MCP.** É uma operação em lote feita pela pessoa: `job-search-mcp import <pasta>` mostra o relatório, e só grava com `--apply`. Isso equivale às duas etapas da decisão 0006. O seed passa a usar o mesmo formato e o mesmo importador.
- **Prefixo por domínio nas ferramentas novas** (`network_*`, `jobs_*`, `changes_*`). As sete da `v0.1.0` mantêm os nomes.
- **Prioridade derivada, não gravada.** A prioridade da vaga é calculada na leitura:
  - `high` com nota ≥ 7,5 ou indicação confirmada;
  - `medium` com nota ≥ 7;
  - `low` nos demais casos.
  
  A prioridade A da empresa é sugerida quando ela tem pessoa ativa ou candidatura ativa; o que fica gravado é a escolha da pessoa.

## Componentes afetados

```text
src/job_search_mcp/
  config.py       novo: leitura do TOML e padrões
  db.py           esquema v2, user_version, migração da v0.1.0, seed pelo importador
  history.py      novo: gravação única do histórico
  proposals.py    novo: criar, confirmar, descartar e listar propostas
  domain.py       on_hold, papéis, tipos de etapa e de origem, prioridade derivada, dias de follow-up vindos da configuração
  companies.py    novo: empresas e visão da empresa
  jobs.py         vaga e candidatura juntas, etapas e vínculos com pessoas
  contacts.py     empresa por referência, on_hold, interação ligada às candidaturas da pessoa
  summary.py      métricas do funil; follow-ups com on_hold
  transfer.py     novo: importação e exportação CSV
  server.py       ferramentas novas, escrita em duas etapas, subcomandos import e export
data/seed/        CSV no formato de importação (empresas, pessoas, vagas, interações, etapas, vínculos)
config.example.toml
docs/import-format.md   formato documentado dos CSV
tests/            um arquivo por módulo novo, e test_migration.py
```

## Modelo de dados

Esquema versão 2. As colunas novas aparecem em **negrito**.

**company** (nova): id, name, **normalized_name** (único), sector, priority (`A`, `B`, `C` ou nulo), job_platform, notes, version, created_at.

**job** (vaga): id, **company_id**, title, url (único), track, score, version, created_at. O texto `company` da `v0.1.0` é migrado para `company`, com a união feita por nome normalizado: minúsculas, sem acento, sem espaços nas pontas.

**application** (nova, 1:1 com `job`): id, job_id (único), status, applied_on, last_contact_on, next_step, resume_track, salary_ask, contract_type, version. Os campos de andamento da `v0.1.0` (`status`, `next_step`, `applied_on`, `last_contact_on`) são migrados de `job`.

**application_stage** (nova): id, application_id, kind, date, result, feedback.
- `kind`: `screening`, `test`, `culture_fit`, `hr`, `technical`, `manager`, `offer`.
- `result`: `pending`, `passed`, `failed`, `cancelled`.

**application_person** (nova): application_id, contact_id, role, confirmed; chave composta pelos três primeiros.
- `role`: `referrer`, `recruiter`, `hiring_manager`, `contact`.
- A coluna `contact.job_id` da `v0.1.0` é migrada para cá, com papel `contact` e `confirmed` verdadeiro, e depois removida.

**contact** (pessoa): id, name, **company_id**, **role_title**, relationship, channel, status, next_step, last_contact_on, version.

**interaction**: id, contact_id, date, summary, **channel**, **source_type**.

**history** (nova, substitui `job_history`): id, entity, record_id, field, old_value, new_value, date, source_type, source_ref.
- `source_type`: `conversation`, `print`, `audio`, `email`, `meeting`, `import`, `user`.
- O campo livre `source` da `v0.1.0` vira `source_type = user`, com o texto original em `source_ref`.

**proposal** (nova): id (texto aleatório), tool, arguments (JSON), preview (JSON), base_versions (JSON), status, created_at, expires_at.
- `status`: `pending`, `applied`, `discarded`, `expired`, `stale`.

**Status:** os da `v0.1.0`, mais `on_hold` para candidatura e para pessoa.
- `on_hold` não gera follow-up.
- `on_hold` não encerra o registro: a candidatura continua contando como ativa no funil.

## APIs ou interfaces

### Ferramentas da v0.1.0

| Ferramenta | Mudança |
|---|---|
| `list_jobs`, `list_contacts`, `pending_followups`, `daily_summary` | **Compatível.** Mesmos parâmetros e chaves. Novas chaves aditivas: `company_id`, `priority`, `stages` na vaga; `company_id`, `role_title` na pessoa. |
| `add_job`, `update_job`, `log_interaction` | **Incompatível.** Devolvem `{"proposal": {...}}` em vez do resultado; o resultado vem de `changes_confirm`. Os parâmetros continuam; `add_job` ganha `source` opcional (padrão `user`). `update_job` ganha `resume_track`, `salary_ask` e `contract_type`, opcionais. `source` passa a aceitar os tipos de origem. Texto livre continua aceito, como `user`, com o texto em `source_ref`. |
| `log_interaction` (resultado confirmado) | **Mudança de comportamento.** Atualiza `last_contact_on` de todas as candidaturas **ativas** ligadas à pessoa, em qualquer papel; candidatura encerrada (`hired`, `rejected`, `withdrawn`, `closed`) deixa de ser atualizada, o que a `v0.1.0` fazia com a vaga vinculada. `job` continua (a vaga quando a pessoa está ligada a exatamente uma, em qualquer papel; senão nulo) e `jobs` é aditiva. `contact.job_id` segue só o papel `contact`. |

### Ferramentas novas

| Ferramenta | Tipo | Parâmetros | Retorno |
|---|---|---|---|
| `changes_confirm` | escrita | `proposal_id` | resultado da operação, ou erro `stale_proposal`, `expired_proposal` ou `not_found` |
| `changes_discard` | escrita | `proposal_id` | proposta descartada |
| `changes_list_pending` | leitura | nenhum | propostas pendentes, com a prévia |
| `network_list_companies` | leitura | `priority?` | empresas, com `suggested_priority` |
| `network_company_overview` | leitura | `company_id` | empresa, pessoas ligadas e candidaturas ativas |
| `network_save_company` | escrita (proposta) | `company_id?`, `name`, `sector?`, `priority?`, `job_platform?`, `notes?`, `source` | proposta |
| `network_save_person` | escrita (proposta) | `contact_id?`, `name`, `company?`, `role_title?`, `relationship?`, `channel?`, `status?`, `next_step?`, `source` | proposta |
| `jobs_add_stage` | escrita (proposta) | `job_id`, `kind`, `date`, `result?`, `feedback?`, `status?`, `source` | proposta (a etapa e, se informado, o novo status da candidatura) |
| `jobs_link_person` | escrita (proposta) | `job_id`, `contact_id`, `role`, `confirmed?`, `source` | proposta |
| `jobs_funnel_metrics` | leitura | `reference_date?`, `weeks?` (padrão 4) | ativas por status, em entrevista, taxa de entrevista, candidaturas por semana, com e sem indicação, follow-ups vencidos e a vencer, dias até o prazo-âncora |

### Linha de comando

- `job-search-mcp import <pasta> [--apply]` e `job-search-mcp export <pasta>`.
- `--seed` continua existindo e passa a usar o importador.

**Taxa de entrevista:** candidaturas que chegaram a uma etapa `hr`, `technical` ou `manager`, ou a um status de entrevista, dividido pelas candidaturas com `applied_on`.

## Estratégia de testes

Cada critério de aceitação da especificação tem um teste:

| Critério | Teste |
|---|---|
| Nenhuma escrita sem confirmação | Para cada ferramenta de escrita: chamar sem confirmar e comparar um retrato do banco antes e depois (`test_proposals.py`, `test_server.py`). |
| Proposta desatualizada recusada | Propor, alterar o registro por outra proposta confirmada, tentar confirmar a primeira e receber `stale_proposal`. |
| Histórico com origem | Toda confirmação gera linhas em `history` com `source_type`; escrita com origem vazia é recusada. |
| Migração sem perda | Criar um banco com o esquema e o seed da `v0.1.0` (fixture com o SQL da versão antiga), abrir com a `v0.2.0` e conferir: contagens, empresas unidas por nome, histórico migrado, vínculos vindos de `contact.job_id`. |
| Importação idempotente | Importar duas vezes a mesma pasta e conferir que as contagens não mudam; o relatório da segunda vez lista tudo como duplicado. |
| Métricas | Comparar com contagem à mão sobre o seed sintético, com data fixa. |
| Sem configuração | Rodar com `JOB_SEARCH_CONFIG` ausente e com arquivo de exemplo. |
| Casos de uso | Verificação por cliente MCP programático e conversa real no Claude Code, registradas em `docs/evidence/`. |

Os 152 testes atuais continuam passando, exceto os das três ferramentas de escrita, que passam a confirmar a proposta.

## Riscos técnicos

- **Migração destrutiva.** A migração remove colunas e uma tabela. Mitigação:
  - transação única;
  - cópia do arquivo do banco antes de migrar (`<nome>.v1.bak`);
  - teste com o banco da `v0.1.0`.
  
  Para reverter: restaurar a cópia.
- **Reexecutar a operação na confirmação.** A prévia e a gravação podem divergir. Mitigação: a mesma função calcula as mudanças nos dois momentos, e a confirmação compara a prévia gravada com a recalculada; se diferirem, devolve `stale_proposal`.
- **SQLite sem `DROP COLUMN` em todas as versões.** Mitigação: recriar as tabelas `job` e `contact` na migração (criar a nova, copiar, renomear).
- **Crescimento do servidor.** De 7 para 17 ferramentas. Mitigação:
  - prefixos por domínio;
  - descrições curtas;
  - o cliente pode filtrar ferramentas por prefixo (decisão D7 do modelo).

## Plano de implementação

Cada etapa é uma tarefa em `docs/tasks/`, na ordem:

1. `09-configuracao-local.md` — `config.py`, `config.example.toml`, dias de follow-up e prazo-âncora vindos da configuração.
2. `10-esquema-v2-e-migracao.md` — esquema versão 2, migração da `v0.1.0`, `history.py`, vaga e candidatura juntas nas leituras, `on_hold`; ferramentas atuais sem mudança de contrato.
3. `11-gravacao-em-duas-etapas.md` — `proposals.py`, coluna `version`, `changes_*`, e `add_job`, `update_job` e `log_interaction` passando a propor.
4. `12-empresas-e-pessoas.md` — `companies.py`, `network_*`, prioridade sugerida da empresa.
5. `13-etapas-e-vinculos.md` — `jobs_add_stage`, `jobs_link_person`, prioridade derivada da vaga, interação ligada às candidaturas da pessoa.
6. `14-importacao-e-exportacao.md` — `transfer.py`, `docs/import-format.md`, subcomandos, seed no formato novo com dados sintéticos de empresas, etapas e vínculos.
7. `15-metricas-do-funil.md` — `jobs_funnel_metrics`.
8. `16-readme-evidencia-e-versao.md` — README, evidência dos seis casos de uso (cliente programático e Claude Code), notas da versão com a mudança de contrato.
