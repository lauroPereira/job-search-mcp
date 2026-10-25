# Verificação da v0.2.0 por cliente MCP via stdio

## O que este documento é, e o que não é

Registro da execução dos seis casos de uso da [especificação da fonte única](../specs/fonte-unica-v0-2.md) contra o servidor real, em 2026-10-25, mais a importação de um CSV sintético e a abertura de um banco da `v0.1.0`.

**Nível da verificação: automatizada/programática.** Um script chamou as ferramentas por um cliente MCP, por stdio, com os argumentos que um agente passaria; a "confirmação da pessoa" foi o próprio script chamando `changes_confirm` ou `changes_discard`. O documento comprova que o servidor sobe, expõe as 17 ferramentas, propõe sem gravar, grava só na confirmação e devolve os resultados esperados. Ele **não** comprova que um agente escolhe a ferramenta certa a partir de uma frase, nem que ele mostra a proposta e espera a resposta da pessoa antes de confirmar. Essa verificação continua **pendente** (ver a última seção).

## Método

- **Versão:** `develop` @ `d0af3e5` (tarefas 09 a 15 integradas). Os parâmetros novos de `update_job`, acrescentados depois na tarefa 16, foram verificados à parte (seção "Parâmetros novos de update_job").
- **Ambiente:** Windows 11, Python 3.12.7. Ambiente virtual novo, criado só para esta verificação, com `pip install -e .` (sem as dependências de desenvolvimento): `fastmcp` 4.1.0 e `mcp` 2.3.0.
- **Servidor:** o executável `job-search-mcp.exe` desse ambiente, iniciado como subprocesso pelo cliente.
- **Cliente:** `Client(StdioTransport(command=<job-search-mcp.exe>, args=[], env={..., "JOB_SEARCH_DB": <banco>}, keep_alive=False))`, do pacote fastmcp, em um script descartável, não versionado. Chamadas com `call_tool(nome, argumentos, raise_on_error=False)`. Para conferir que nada foi gravado, o script tirou um retrato de todas as tabelas, exceto `proposal`, antes e depois das chamadas.
- **Bancos:** arquivos novos em diretório temporário, fora do repositório: `demo.db` (seed, casos 2 a 6), `import.db` (caso 1, vazio antes da importação), `demo2.db` (seed intacto, caso 6 de referência e exemplos do README) e `v1.db` (banco da `v0.1.0`). Os dois seeds foram carregados com `job-search-mcp --seed` (`Demo data loaded into ...`, código 0).
- **Configuração:** sem `JOB_SEARCH_CONFIG` em todas as chamadas, exceto uma do caso 6, feita com `config.example.toml`.
- **Data de referência declarada: 2026-03-16**, passada em `reference_date` e nas datas dos registros. A data real, que o servidor usa como "hoje", foi 2026-10-25: ela aparece nas datas das linhas de histórico e no `expires_at` das propostas (UTC, 24 horas depois).
- **Ordem:** os casos 2 a 6 rodaram em sequência no mesmo banco; os registros dos casos 2 e 5 aparecem no funil do caso 6.

Em todas as chamadas o cliente recebeu `is_error=False` e conteúdo estruturado. Os retornos abaixo estão resumidos.

## Conexão

```text
server: job-search | protocol: 2026-07-28
tool list_jobs: params=['status', 'track', 'min_score'] required=[] readOnly=True
tool add_job: params=['company', 'title', 'url', 'track', 'score', 'next_step', 'source'] required=['company', 'title', 'url']
tool update_job: params=['job_id', 'source', 'status', 'next_step', 'applied_on', 'last_contact_on'] required=['job_id', 'source']
tool list_contacts: params=['status', 'company'] required=[] readOnly=True
tool log_interaction: params=['contact_id', 'summary', 'date', 'status', 'next_step'] required=['contact_id', 'summary']
tool network_list_companies: params=['priority'] required=[] readOnly=True
tool network_company_overview: params=['company_id'] required=['company_id'] readOnly=True
tool network_save_company: params=['source', 'name', 'company_id', 'sector', 'priority', 'job_platform', 'notes'] required=['source']
tool network_save_person: params=['source', 'name', 'contact_id', 'company', 'role_title', 'relationship', 'channel', 'status', 'next_step'] required=['source']
tool jobs_add_stage: params=['job_id', 'kind', 'date', 'source', 'result', 'feedback', 'status'] required=['job_id', 'kind', 'date', 'source']
tool jobs_link_person: params=['job_id', 'contact_id', 'role', 'source', 'confirmed'] required=['job_id', 'contact_id', 'role', 'source']
tool changes_confirm: params=['proposal_id'] required=['proposal_id']
tool changes_discard: params=['proposal_id'] required=['proposal_id']
tool changes_list_pending: params=[] required=[] readOnly=True
tool pending_followups: params=['reference_date', 'days_ahead'] required=[] readOnly=True
tool daily_summary: params=['reference_date', 'deadline'] required=[] readOnly=True
tool jobs_funnel_metrics: params=['reference_date', 'weeks'] required=[] readOnly=True
tool_count: 17
```

As sete ferramentas da `v0.1.0` mantêm os parâmetros; a única diferença é `source` opcional em `add_job`.

## Caso 1: importar o controle atual

**Pedido:** "Converti minhas planilhas para CSV; quero ver o que entra antes de gravar."

**Dados:** uma pasta com os seis arquivos, todos sintéticos (empresas "Cooperativa Ipê" e "Laboratório Quasar", pessoas "Marta Hipotética" e "Nuno Provisório", links em `vagas.example.com`). `people.csv` foi gravado como o Excel em português salva "CSV UTF-8": separador `;` e BOM. Três linhas com problema de propósito: `  cooperativa IPÊ ` repetida em `companies.csv`, uma vaga com link `-` e um vínculo com pessoa inexistente.

**Comando 1:** `job-search-mcp import <pasta>` (código 0)

```text
companies.csv: 2 new, 1 duplicates, 0 with errors
  line 4: duplicate: company 'cooperativa IPÊ' of companies.csv:2
people.csv: 2 new, 0 duplicates, 0 with errors
jobs.csv: 2 new, 0 duplicates, 1 with errors
  line 4: error: invalid url '-': use a full link starting with http:// or https:// (...)
interactions.csv: 1 new, 0 duplicates, 0 with errors
stages.csv: 1 new, 0 duplicates, 0 with errors
links.csv: 1 new, 0 duplicates, 1 with errors
  line 3: error: unknown person 'Pessoa Inexistente' at 'Laboratório Quasar'
Nothing was written: run again with --apply to write the new rows.
```

Retrato do banco depois do relatório: todas as tabelas vazias.

**Comando 2:** `job-search-mcp import <pasta> --apply` (código 0): o mesmo relatório, terminando em `Applied: the new rows were written to the database.` O histórico ficou com 45 linhas, todas `source_type = import`, com `source_ref` no formato `jobs.csv:2` e data 2026-10-25.

**Comandos 3 e 4:** o mesmo `import`, sem e com `--apply` (código 0): `0 new` em todos os arquivos, com cada linha listada como duplicada (`already in the database`) e as duas linhas com erro de novo. Retrato do banco igual antes e depois do segundo `--apply`.

**Uso pelo servidor:** `network_list_companies()` devolveu Cooperativa Ipê (prioridade A, sugerida A) e Laboratório Quasar (B, sugerida A, por ter candidatura ativa). `list_jobs()` devolveu as duas vagas: Data Engineer da Cooperativa Ipê com a etapa `hr` de 2026-03-10, Marta Hipotética como `referrer` confirmada (`sim` no CSV) e prioridade `high`; Analytics Engineer do Laboratório Quasar com prioridade `medium`.

**Exportação:** `job-search-mcp export <pasta nova>` (código 0): 2, 2, 2, 1, 1 e 1 linhas. A segunda vez na mesma pasta foi recusada com código 1 (`Refused: ... already has companies.csv, ... nothing was written.`).

## Caso 2: registrar uma etapa

**Pedido:** "Fiz a entrevista técnica hoje na Clínica Boreal, foi bem, aguardo retorno."

**Chamada 1:** `list_jobs(status="hr_interview")` → vaga 4, Clínica Boreal, Product Analyst, `last_contact_on` 2026-03-13, sem etapas.

**Chamada 2:** `jobs_add_stage(job_id=4, kind="technical", date="2026-03-16", result="pending", feedback="Foi bem; aguardo retorno", status="tech_interview", source="conversation")`

**Retorno:** `{"proposal": {"id": "-lVK...", "tool": "jobs_add_stage", "changes": [...], "expires_at": "2026-10-26 14:48:10"}}`, com sete mudanças:

| `entity` | `record_id` | `field` | `old_value` | `new_value` |
|---|---|---|---|---|
| application_stage | nulo | application_id, kind, date, result, feedback | nulo | 4, technical, 2026-03-16, pending, "Foi bem; aguardo retorno" |
| application | 4 | status | hr_interview | tech_interview |
| application | 4 | last_contact_on | 2026-03-13 | 2026-03-16 |

Retrato do banco igual depois da proposta e depois de `changes_list_pending()` (que listou a proposta com as sete mudanças).

**Chamada 3:** `changes_confirm(proposal_id="-lVK...")` → `stage` id 10 (technical, 2026-03-16, pending); `job` 4 em `tech_interview`, `last_contact_on` 2026-03-16, `follow_up` 2026-03-23; `history` com status e `last_contact_on`, `source` "conversation". No banco, sete linhas de histórico (cinco da etapa, duas da candidatura), todas com `source_type = conversation` e data 2026-10-25.

**Chamada 4:** a mesma confirmação de novo → `{"error": "not_found", "detail": "No pending proposal with id ...: it was already applied.", "status": "applied"}`.

**Extra, proposta desatualizada:** duas propostas de `update_job` para a vaga 9 (`next_step` e `status="blocked"`); confirmada a segunda, a primeira foi recusada com `stale_proposal` ("the records changed since it was made, so nothing was changed"), com o banco igual.

## Caso 3: recusa da proposta

**Pedido:** o agente propõe `referred` para a Ana Exemplo; a pessoa responde "não, deixa como está".

**Chamada 1:** `log_interaction(contact_id=1, summary="Conversa sobre a indicação", date="2026-03-16", status="referred", next_step="Aguardar o RH")` → proposta com a interação nova, `contact.status` awaiting_reply → referred, `last_contact_on` e `next_step` da pessoa e `application.last_contact_on` 2026-03-09 → 2026-03-16 da vaga 1.

**Chamada 2:** `changes_discard(proposal_id=...)` → `{"proposal": {"id": ..., "tool": "log_interaction", "status": "discarded"}}`.

**Conferência:** retrato do banco igual ao de antes da proposta. `changes_confirm` da mesma proposta → `not_found` com `status: discarded`. `list_contacts(company="banco aurora")` → Ana Exemplo ainda em `awaiting_reply`, último contato 2026-03-08 (o filtro ignorou maiúsculas).

## Caso 4: quem eu conheço na empresa

**Pedido:** "Quem eu conheço no Banco Aurora e o que tenho aberto lá?"

**Chamada 1:** `network_list_companies(priority="A")` → Transportadora Pampa, Usina Solaris e Financeira Colibri. Sem filtro, as 16 empresas; Banco Aurora tem `priority` nula e `suggested_priority` A.

**Chamada 2:** `network_company_overview(company_id=1)`:

- `company`: Banco Aurora, setor Bancos, `priority` nula, `suggested_priority` A;
- `people`: Ana Exemplo (`awaiting_reply`, `job_id` 1, `follow_up` 2026-03-14);
- `applications`: vaga 1, Data Engineer, `applied`, prioridade `high`, com Ana Exemplo nos papéis `contact` e `referrer`, ambos confirmados.

**Chamada 3:** `network_company_overview(company_id=999)` → `{"error": "not_found", "detail": "No company with id 999."}`.

## Caso 5: em espera

**Pedido:** "Não precisa cobrar o Diego até eu avisar."

**Chamada 1:** `pending_followups(reference_date="2026-03-16")` → contatos: Ana Exemplo (vencido, 14/03), Diego Amostra (vencido, 16/03), Bruno Modelo (a vencer, 17/03), Gabriela Ensaio (a vencer, 18/03).

**Chamada 2:** `network_save_person(contact_id=4, status="on_hold", next_step="Não cobrar até nova ordem", source="conversation")` → proposta com `status` referred → on_hold e o novo `next_step`; banco igual.

**Chamada 3:** `changes_confirm(...)` → `contact` 4 em `on_hold`, `follow_up` nulo. Histórico: duas linhas, `source_type = conversation`.

**Chamada 4:** `pending_followups(reference_date="2026-03-16")` → Ana, Bruno e Gabriela; Diego saiu. `list_contacts(status="on_hold")` → só Diego Amostra.

## Caso 6: funil da semana

**Pedido:** "Como está meu funil esta semana?"

**Chamada:** `jobs_funnel_metrics(reference_date="2026-03-16")`, primeiro no seed intacto (`demo2.db`), sem configuração, comparada com a contagem feita à mão na tarefa 15:

| Métrica | Retorno | Contagem à mão |
|---|---|---|
| `active_total`, `active_by_status` | 11: suggested 1, to_apply 2, blocked 1, applied 2, in_review 1, hr_interview 1, tech_interview 1, manager_interview 1, offer 1, on_hold 0 | igual |
| `queue.total` | 4 | 4 |
| `in_progress` | 7, com indicação 1, sem 6 | igual |
| `in_interview` | 3 | 3 |
| `interview_rate` | 6 de 10, `rate` 0.6 | 6/10 |
| `applications_per_week` | W09 1, W10 2, W11 1, W12 0 (`days_elapsed` 1, `partial` true) | 1, 2, 1, 0 |
| `follow_ups` | vencidos: 2 vagas e 2 pessoas; a vencer: 3 e 2 | igual |
| `deadline`, `days_to_deadline`, `goals` | nulos | sem configuração |

Retrato do banco igual antes e depois. A mesma chamada com `JOB_SEARCH_CONFIG` apontando para `config.example.toml` trouxe `deadline` 2099-12-31, `days_to_deadline` 26953 e `goals` `{"applications_per_week": 5, "interview_rate": 0.2}`; com `weeks=0`, `invalid_input` ("Use an integer from 1 to 52").

No banco dos casos 2 a 5 (`demo.db`), o funil refletiu as mudanças: `hr_interview` 0 e `tech_interview` 2 (caso 2), `to_apply` 1 e `blocked` 2 (extra do caso 2) e um contato vencido a menos (caso 5); o restante igual.

## Exemplos do README, no seed intacto

Depois do caso 6, no `demo2.db`:

- `daily_summary(reference_date="2026-03-16", deadline="2026-04-15")`: os mesmos números da `v0.1.0` (vencidos: vagas 5 e 1, contatos 1 e 4; a vencer: vagas 7, 2 e 3, contatos 2 e 7; fila 8, 9 e 10; 30 dias), com a chave nova `on_hold: 0` em `jobs_by_status`.
- `add_job(company="Empresa Exemplo", title="Analytics Engineer", url="https://vagas.example.com/empresa-exemplo/analytics-engineer", track="data", score=8, source="conversation")` → proposta com a empresa nova, a vaga e a candidatura em `suggested`; banco igual; confirmada, vaga 16 com prioridade `high`. O mesmo link com `/` no fim → `duplicate_url` (id 16).
- `log_interaction(contact_id=1, ..., status="in_conversation")` confirmada → `follow_up` da Ana 2026-03-22, `job` 1 com último contato 2026-03-16 e `follow_up` 2026-03-23, `jobs` [1]. `pending_followups` deixou de listar a Ana e a vaga 1.

## Banco da v0.1.0 migrado

**Dados:** banco criado com `tests/fixtures/schema_v1.sql` e os CSV de `tests/fixtures/seed_v1/` (o seed da `v0.1.0`), mais um contato sintético com a empresa `"  banco ÁURORA "` ligado à vaga 1 e uma linha de `job_history` com origem em texto livre. Antes: `user_version` 0, 15 vagas, 9 contatos, 17 textos de empresa diferentes.

**Chamadas:** `list_jobs()` (15 vagas; a vaga 1 com Ana Exemplo e o contato novo no papel `contact`), `list_contacts(company="Banco Aurora")` (os dois, com `company` "Banco Aurora" e `company_id` 1) e `network_list_companies()` (16 empresas).

**Saída de erro do servidor na primeira abertura** (o protocolo segue só na saída padrão):

```text
Migrating the database to schema version 2; copy at <diretório temporário>\v1.db.v1.bak.
Company '  banco ÁURORA ' stored as 'Banco Aurora'.
```

**Depois:** `user_version` 2; tabelas `application`, `application_person`, `application_stage`, `company`, `contact`, `history`, `interaction`, `job` e `proposal` (sem `job_history`); a linha de histórico migrada como `entity = application`, `source_type = user`, `source_ref` "E-mail do recrutador"; sete vínculos `contact` confirmados vindos de `contact.job_id`. A cópia `v1.db.v1.bak` tem `user_version` 0 e as 15 vagas. Uma segunda abertura não migrou de novo nem criou outra cópia.

## Divergências e observações

1. **Parâmetros de `update_job`.** Em `d0af3e5`, o servidor não expunha `resume_track`, `salary_ask` e `contract_type`, previstos no plano. Decisão do Supervisor: o servidor segue o plano. Os parâmetros foram acrescentados e verificados na seção seguinte; a listagem da seção "Conexão" é a de `d0af3e5`.
2. **Datas do histórico.** As linhas de histórico e o `expires_at` usam a data real (2026-10-25), não a data declarada nos pedidos; é o comportamento documentado (o histórico registra quando a mudança foi feita).
3. **Confirmação feita pelo script.** Nada aqui mostra um agente pedindo aprovação: o servidor garante as duas chamadas e a revalidação, não a pergunta à pessoa.
4. Todos os nomes de pessoas e empresas são os sintéticos de `data/seed/` e `tests/fixtures/` ou foram inventados para esta verificação.

## Parâmetros novos de update_job

Reexecução sobre o commit `6503e0a` (branch `docs/16-readme-evidencia-e-versao`: `update_job` com os três parâmetros e versão 0.2.0), no mesmo ambiente virtual reinstalado com `pip install -e .` (`__version__` e metadados do pacote: 0.2.0), banco novo com `--seed` e o mesmo cliente por stdio.

- `update_job`: `params=['job_id', 'source', 'status', 'next_step', 'applied_on', 'last_contact_on', 'resume_track', 'salary_ask', 'contract_type']`, `required=['job_id', 'source']`. As demais 16 ferramentas não mudaram.
- `update_job(job_id=2, source="conversation", resume_track="data", salary_ask="a combinar", contract_type="CLT")` → proposta com três mudanças em `application` 2 (nulo → "data", "a combinar", "CLT"); banco igual.
- `changes_confirm` → vaga 2 (Loja Horizonte, `applied`) com os três valores; `history` com três linhas, `source` "conversation", data 2026-10-25.
- `update_job(job_id=2, source="user", resume_track="dados")` → `{"error": "invalid_input", "detail": "Invalid resume_track 'dados'. Valid values: data, systems, product, ai, other.", "valid_values": [...]}`, sem proposta; banco igual.
- `list_jobs(status="applied")` → vagas 1 (os três nulos) e 2 (os três preenchidos), com `resume_track`, `salary_ask` e `contract_type` como as três últimas chaves.

## Depois da execução

- Os bancos, a pasta de importação e a exportação ficaram no diretório temporário; `git status` no repositório mostrou só os arquivos da tarefa 16.
- A suíte completa (`python tools/scripts/lint_and_tests.py --strict`) passou no mesmo commit: ver a validação da tarefa 16.

## Verificação manual no Claude Code: pendente (responsável humano)

Roteiro, com o servidor configurado como no README, um banco novo com `--seed` e, se quiser, `JOB_SEARCH_CONFIG` apontando para uma cópia de `config.example.toml`. Para cada pedido, conferir a ferramenta chamada, se o agente **mostra a proposta e espera a resposta** antes de `changes_confirm`, e o resultado.

1. **Importar:** no terminal, `job-search-mcp import <pasta com CSV sintéticos>`, ler o relatório, rodar com `--apply`; depois pedir ao agente "Liste minhas empresas e vagas".
2. **Etapa:** "Considere que hoje é 16/03/2026. Fiz a entrevista técnica hoje na Clínica Boreal, foi bem, aguardo retorno." Esperado: `jobs_add_stage` com `status=tech_interview`, proposta mostrada, confirmação só depois do "sim".
3. **Recusa:** "Registra que falei com a Ana Exemplo hoje sobre a indicação." Se o agente propuser `referred` (ou qualquer mudança), responder "não, descarta". Esperado: `changes_discard` e nada gravado.
4. **Empresa:** "Quem eu conheço no Banco Aurora e o que tenho aberto lá?" Esperado: `network_company_overview` com Ana Exemplo e a vaga Data Engineer.
5. **Em espera:** "Não precisa cobrar o Diego Amostra até eu avisar." Esperado: `network_save_person` com `on_hold`, confirmação, e o Diego fora de "Quem eu preciso cobrar em 16/03/2026?".
6. **Funil:** "Como está meu funil em 16/03/2026?" Esperado: `jobs_funnel_metrics` com taxa de entrevista 0,6 (6 de 10), vencidos e a vencer e dias até o prazo (se houver configuração).

Registrar o resultado em um novo arquivo em `docs/evidence/`.
