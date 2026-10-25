# Verificação dos casos de uso por cliente MCP via stdio

## O que este documento é, e o que não é

Registro da execução dos cinco casos de uso da especificação (`docs/specs/servidor-mcp-busca-de-emprego.md`) contra o servidor real, em 2026-10-10.

**A verificação foi feita por um cliente MCP programático, por stdio, e não por uma pessoa conversando com um agente no Claude Code ou no Claude Desktop.** Um script chamou as ferramentas diretamente, com os argumentos que um agente passaria. Portanto este documento comprova que o servidor sobe, expõe as ferramentas e devolve os resultados esperados pelo protocolo. Ele **não** comprova que um agente escolhe a ferramenta certa a partir de uma frase do usuário, nem que a configuração descrita no README funciona naqueles aplicativos. Essa verificação manual continua **pendente**, a cargo do responsável humano (ver "Pendências").

Os pedidos em linguagem natural abaixo descrevem a situação de cada caso de uso; nenhum deles foi digitado para um agente.

## Método

- **Versão:** branch `feat/07-readme-e-evidencia`, sobre o commit `f697f95` da tarefa 06 (`feat/06-servidor-mcp`). A tarefa 07 não altera código.
- **Reexecução depois da revisão:** os cinco casos foram executados de novo, do mesmo modo e em banco novo, sobre o commit `b95a48c` da tarefa 06 (com as correções da revisão: validação de `track` e `score` em `add_job`, tratamento de erro do `--seed`). Todos os retornos registrados abaixo se repetiram, exceto o horário de criação da vaga do caso 4; nenhum retorno citado mudou com a validação nova. Nessa reexecução foi lida, direto no banco, a linha de histórico do caso 2, e foram feitas as duas chamadas de validação acrescentadas ao caso 4.
- **Sobre os SHAs:** Os SHAs acima são os atuais: o histórico de `develop` foi reescrito em 2026-10-10 para corrigir o e-mail de autor dos commits de merge, sem alterar o conteúdo, e os SHAs originais deixaram de existir em `develop` (correspondência em `docs/tasks/08-ajustes-da-revisao-06-07.md`).
- **Ambiente:** Windows 11, Python 3.12.7. Ambiente virtual novo, criado só para esta verificação, com `pip install -e .` (sem as dependências de desenvolvimento), como descrito no README: `fastmcp` 4.1.0 e `mcp` 2.3.0.
- **Banco:** arquivo novo em diretório temporário, fora do repositório, indicado por `JOB_SEARCH_DB` e preenchido com `job-search-mcp --seed` (15 vagas e 8 contatos sintéticos de `data/seed/`). O comando respondeu `Demo data loaded into <diretório temporário>/demo.db.` (código 0).
- **Servidor:** o executável `job-search-mcp` do ambiente virtual, iniciado como subprocesso pelo cliente.
- **Cliente:** `Client(StdioTransport(command=<job-search-mcp>, args=[], env={..., "JOB_SEARCH_DB": <banco>}, keep_alive=False))`, do pacote fastmcp, em um script descartável, não versionado. As chamadas usaram `call_tool(nome, argumentos, raise_on_error=False)`.
- **Data de referência declarada: 2026-03-16**, a data em torno da qual o seed foi desenhado. Ela foi passada explicitamente em `reference_date` e nas datas dos registros. A data real da execução, que o servidor usa como "hoje", foi 2026-10-10: ela aparece na data das linhas de histórico do caso 3 e na mensagem de data futura do caso 2.
- **Ordem:** os casos rodaram em sequência, no mesmo banco, de 1 a 5. Os registros dos casos 2, 3 e 4 afetam o resultado do caso 5.
- A execução foi feita duas vezes, em bancos novos (uma com o ambiente de desenvolvimento, outra com o ambiente novo); as saídas foram idênticas, exceto o horário de criação da vaga do caso 4.

Em todas as chamadas o cliente recebeu `is_error=False`, conteúdo estruturado (`structured_content`) e um bloco de texto com o mesmo JSON. Os retornos abaixo estão resumidos: as vagas e os contatos vêm com todos os campos, e aqui aparecem só os relevantes.

## Conexão

```text
server: job-search | protocol: 2026-07-28
tool list_jobs: params=['status', 'track', 'min_score'] required=[]
tool add_job: params=['company', 'title', 'url', 'track', 'score', 'next_step'] required=['company', 'title', 'url']
tool update_job: params=['job_id', 'source', 'status', 'next_step', 'applied_on', 'last_contact_on'] required=['job_id', 'source']
tool list_contacts: params=['status', 'company'] required=[]
tool log_interaction: params=['contact_id', 'summary', 'date', 'status', 'next_step'] required=['contact_id', 'summary']
tool pending_followups: params=['reference_date', 'days_ahead'] required=[]
tool daily_summary: params=['reference_date', 'deadline'] required=[]
tool_count: 7
```

Cada ferramenta veio com descrição. Saída de erro do servidor: só a linha de log `Starting MCP server 'job-search' with transport 'stdio'`.

## Caso 1: resumo da manhã

**Pedido:** "Considere que hoje é 16/03/2026. O que eu preciso fazer hoje? Quero estar empregado até 15/04."

**Chamada:** `daily_summary(reference_date="2026-03-16", deadline="2026-04-15")`

**Retorno:**

| Campo | Valor |
|---|---|
| `reference_date` | 2026-03-16 |
| `jobs_by_status` | suggested 1, to_apply 2, blocked 1, applied 2, in_review 1, hr_interview 1, tech_interview 1, manager_interview 1, offer 1, hired 1, rejected 1, withdrawn 1, closed 1 |
| `active_contacts` | 7 |
| `overdue.jobs` | 5 Transportadora Pampa, Machine Learning Engineer (follow-up 2026-03-11); 1 Banco Aurora, Data Engineer (2026-03-16) |
| `overdue.contacts` | 1 Ana Exemplo (2026-03-14); 4 Diego Amostra (2026-03-16) |
| `due_soon.jobs` | 7 Usina Solaris, AI Engineer (2026-03-17); 2 Loja Horizonte, Analytics Engineer (2026-03-18); 3 Seguradora Vértice, Backend Developer (2026-03-18) |
| `due_soon.contacts` | 2 Bruno Modelo (2026-03-17); 7 Gabriela Ensaio (2026-03-18) |
| `application_queue` | 8 Financeira Colibri, Data Scientist (9.5, to_apply); 9 Mercado Jatobá, Software Engineer (7.8, to_apply); 10 Escola Mirante, Product Manager (5.5, suggested) |
| `deadline`, `days_to_deadline` | 2026-04-15, 30 |

**Conferência:** a vaga 1 teve o último contato em 2026-03-09, 7 dias antes da referência, e aparece como vencida; a vaga 3 teve o último contato em 2026-03-11, 5 dias antes, e aparece como a vencer. Nenhuma vaga encerrada (12 a 15) aparece. A fila está em ordem de nota.

## Caso 2: registrar uma conversa

**Pedido:** "Falei hoje com a Ana Exemplo, do Banco Aurora. Ela disse que a indicação foi encaminhada ao RH. Vou agradecer e acompanhar."

**Chamada 1:** `list_contacts(company="Banco Aurora")`

**Retorno:** um contato: id 1, Ana Exemplo, `status` awaiting_reply, `last_contact_on` 2026-03-08, `follow_up` 2026-03-14, `job_id` 1.

**Chamada 2:** `log_interaction(contact_id=1, summary="Respondeu que a indicação foi encaminhada ao RH", date="2026-03-16", status="in_conversation", next_step="Agradecer e acompanhar o RH")`

**Retorno:**

| Campo | Valor |
|---|---|
| `contact` | id 1, `status` in_conversation, `next_step` "Agradecer e acompanhar o RH", `last_contact_on` 2026-03-16, `follow_up` 2026-03-22 |
| `follow_up` | 2026-03-22 |
| `job` | id 1, Banco Aurora, Data Engineer, `last_contact_on` 2026-03-16 (era 2026-03-09), `follow_up` 2026-03-23 |

**Histórico da vaga vinculada:** a ferramenta não devolve a linha de histórico no retorno; ela foi lida direto no banco depois da chamada (`SELECT * FROM job_history`). A interação criou uma linha, a única da tabela nesse momento:

| `job_id` | `date` | `field` | `old_value` | `new_value` | `source` |
|---|---|---|---|---|---|
| 1 | 2026-03-16 | last_contact_on | 2026-03-09 | 2026-03-16 | contact_interaction |

A data da linha é a data da interação (2026-03-16), e não a data real da execução. A tabela `interaction` ficou com uma linha: contato 1, 2026-03-16, "Respondeu que a indicação foi encaminhada ao RH".

**Conferência:** o follow-up do contato foi recalculado (data da interação mais 6 dias), a data do último contato da vaga vinculada foi atualizada (follow-up da vaga: mais 7 dias) e a mudança na vaga ficou no histórico, com valor anterior, valor novo e a origem `contact_interaction`.

**Chamada 3 (erro):** `log_interaction(contact_id=1, summary="Conversa marcada", date="2999-01-01")`

**Retorno:** `{"error": "invalid_date", "detail": "Invalid date '2999-01-01': it cannot be after today (2026-10-10)."}`. Nada foi gravado: as tabelas `interaction` e `job_history` continuaram com uma linha cada.

## Caso 3: candidatura feita

**Pedido:** "Me candidatei hoje à vaga de Data Scientist da Financeira Colibri. Agora é aguardar a triagem."

**Chamada 1:** `update_job(job_id=8, source="user", status="applied", applied_on="2026-03-16", next_step="Aguardar triagem")`

**Retorno:**

- `job`: id 8, Financeira Colibri, Data Scientist, `status` applied, `next_step` "Aguardar triagem", `applied_on` 2026-03-16, `follow_up` 2026-03-23.
- `history`, três linhas, todas com `job_id` 8, `source` "user" e `date` 2026-10-10 (a data real da execução):

| `field` | `old_value` | `new_value` |
|---|---|---|
| status | to_apply | applied |
| next_step | Adaptar o currículo e enviar | Aguardar triagem |
| applied_on | nulo | 2026-03-16 |

**Chamada 2 (erro):** `update_job(job_id=8, source="user", status="candidatada")`

**Retorno:** `error` invalid_status; `detail` "Invalid status 'candidatada'. Valid statuses: suggested, to_apply, blocked, applied, in_review, hr_interview, tech_interview, manager_interview, offer, hired, rejected, withdrawn, closed."; `valid_statuses` com os mesmos 13 valores em lista.

## Caso 4: vaga nova

**Pedido:** "Guarda esta vaga: Analytics Engineer na Empresa Exemplo, https://vagas.example.com/empresa-exemplo/analytics-engineer. Trilha de dados, nota 8."

**Chamada 1:** `add_job(company="Empresa Exemplo", title="Analytics Engineer", url="https://vagas.example.com/empresa-exemplo/analytics-engineer", track="data", score=8.0, next_step="Avaliar aderência")`

**Retorno:** a vaga criada: `id` 16, `status` suggested, `track` data, `score` 8.0, `next_step` "Avaliar aderência", `applied_on`, `last_contact_on` e `follow_up` nulos.

**Chamada 2 (o mesmo link de novo):** `add_job(company="Empresa Exemplo", title="Analytics Engineer", url="https://vagas.example.com/empresa-exemplo/analytics-engineer")`

**Retorno:** `error` duplicate_url; `detail` "A job with this URL already exists (id 16)."; `job` com a vaga 16 completa.

**Chamada 3:** `list_jobs(status="suggested")`

**Retorno:** `jobs` com duas vagas: 10 (Escola Mirante, Product Manager) e 16 (Empresa Exemplo, Analytics Engineer).

**Chamada 4:** `list_jobs()`

**Retorno:** `jobs` com 16 vagas: as 15 do seed e a nova. A segunda chamada não criou outra linha.

**Chamadas 5 e 6 (validação de trilha e nota, feitas na reexecução, depois do caso 5):** `add_job(company="Empresa Exemplo", title="X", url="https://vagas.example.com/empresa-exemplo/analytics-engineer/2", track="dados")` e a mesma chamada com `score=11` no lugar de `track`.

**Retornos:** `{"error": "invalid_input", "detail": "Invalid track 'dados'. Valid tracks: data, systems, product, ai, other.", "valid_tracks": ["data", "systems", "product", "ai", "other"]}` e `{"error": "invalid_input", "detail": "Invalid score '11.0'. Use a number from 0 to 10."}`. Nenhuma vaga foi criada: o banco terminou com 16 vagas.

## Caso 5: cobrança pendente

**Pedido:** "Quem eu preciso cobrar?"

**Chamada:** `pending_followups(reference_date="2026-03-16")`

**Retorno:** `reference_date` 2026-03-16, `days_ahead` 2.

| Tipo | Id | Quem | Status | `follow_up` | `state` |
|---|---|---|---|---|---|
| vaga | 5 | Transportadora Pampa, Machine Learning Engineer | tech_interview | 2026-03-11 | overdue |
| vaga | 7 | Usina Solaris, AI Engineer | offer | 2026-03-17 | due_soon |
| vaga | 2 | Loja Horizonte, Analytics Engineer | applied | 2026-03-18 | due_soon |
| vaga | 3 | Seguradora Vértice, Backend Developer | in_review | 2026-03-18 | due_soon |
| contato | 4 | Diego Amostra, Hospital Arvoredo | referred | 2026-03-16 | overdue |
| contato | 2 | Bruno Modelo, Loja Horizonte | in_conversation | 2026-03-17 | due_soon |
| contato | 7 | Gabriela Ensaio, Consultoria Tangará | in_conversation | 2026-03-18 | due_soon |

**Conferência:** em relação ao caso 1, saíram da lista o contato 1 (Ana Exemplo) e a vaga 1 (Banco Aurora), por causa da conversa registrada no caso 2: os follow-ups foram para 2026-03-22 e 2026-03-23. A vaga 8, candidatada no caso 3, tem follow-up em 2026-03-23 e também não entra. A vaga 16, em `suggested`, não gera follow-up. A ordem é do follow-up mais antigo para o mais recente.

## Depois da execução

- O diretório temporário ficou só com o arquivo do banco.
- `git status --short -uall` no repositório: nenhum arquivo além dos da tarefa; nenhum arquivo de banco; `data/local/` não foi criado.
- Todos os nomes de pessoas e empresas acima são os dados sintéticos de `data/seed/` ou foram inventados para o exemplo ("Empresa Exemplo").

## Limitações

- Cliente programático, e não um agente: ver o início deste documento.
- Executado em uma máquina, com Windows 11. Linux e macOS não foram verificados à mão; o CI roda a suíte em Ubuntu, incluindo os testes que sobem o servidor por stdio.
- O script da verificação não foi versionado; os mesmos passos podem ser refeitos com qualquer cliente MCP, a partir das chamadas listadas aqui.

## Pendências para o responsável humano

1. Configurar o servidor no Claude Code e no Claude Desktop seguindo o README, com o banco de demonstração, e confirmar que as sete ferramentas aparecem.
2. Repetir os cinco casos de uso em conversa, com os pedidos acima, e conferir se o agente chama as ferramentas esperadas e apresenta os resultados corretamente.
3. Registrar o resultado em um novo arquivo em `docs/evidence/`.
