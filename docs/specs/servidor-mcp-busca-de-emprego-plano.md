# Plano: Servidor MCP para gestão de busca de emprego

## Especificação relacionada

`docs/specs/servidor-mcp-busca-de-emprego.md`

## Decisões técnicas

- **Python 3.12 com o pacote fastmcp, transporte stdio.** É o caminho mais curto para expor ferramentas tipadas a clientes como Claude Code e Claude Desktop. Registrado em `docs/architecture/decisions/0001-python-fastmcp-sqlite.md` (Python, SQLite e stdio) e em `docs/architecture/decisions/0003-usar-pacote-fastmcp.md` (escolha do pacote `fastmcp` no lugar do SDK oficial).
- **SQLite pela biblioteca padrão (`sqlite3`), sem ORM.** Um arquivo local, sem serviço, suficiente para o volume previsto. Mesma decisão 0001.
- **Lógica de domínio separada do servidor.** As regras (status válidos, follow-up, histórico, resumo) ficam em funções Python puras, que recebem a conexão e a data de referência. O módulo do servidor só registra as ferramentas e converte entrada e saída. Isso permite testar tudo sem subir o servidor.
- **Data de referência injetável.** Nenhuma regra chama a data atual por conta própria; a data entra como parâmetro, com padrão "hoje" apenas na borda (a ferramenta).
- **Caminho do banco por variável de ambiente** (`JOB_SEARCH_DB`), com padrão em `data/local/job_search.db`, que está fora do Git.
- **Erros de negócio como respostas estruturadas.** Duplicidade e status inválido devolvem um objeto com `error` e `detail`, em vez de exceção sem contexto, para o agente conseguir explicar ao usuário.

## Componentes afetados

Projeto novo. Estrutura prevista:

```text
pyproject.toml
src/job_search_mcp/
  __init__.py
  db.py          conexão, criação do esquema e carga dos dados sintéticos
  domain.py     constantes (status), regras de follow-up e classificação
  jobs.py       listar, registrar e atualizar vagas, com histórico
  contacts.py    listar contatos e registrar interações
  summary.py      pending_followups e daily_summary
  server.py      registro das ferramentas no FastMCP e ponto de entrada
data/seed/
  jobs.csv       dados sintéticos
  contacts.csv   dados sintéticos
tests/
  conftest.py    banco temporário e data de referência fixa
  test_domain.py
  test_jobs.py
  test_contacts.py
  test_summary.py
  test_server.py
```

## Modelo de dados

**job**

| Campo | Tipo | Observação |
|---|---|---|
| id | inteiro, chave | |
| company | texto, obrigatório | |
| title | texto, obrigatório | |
| url | texto, único, obrigatório | usado para evitar duplicidade |
| track | texto | data, systems, product, ai, other |
| score | real | 0 a 10 |
| status | texto, obrigatório | lista fechada, ver abaixo |
| next_step | texto | |
| applied_on | data | |
| last_contact_on | data | |
| created_at | data e hora | |

**contact**

| Campo | Tipo | Observação |
|---|---|---|
| id | inteiro, chave | |
| name | texto, obrigatório | |
| company | texto | |
| relationship | texto | |
| channel | texto | |
| status | texto, obrigatório | lista fechada, ver abaixo |
| next_step | texto | |
| last_contact_on | data | |
| job_id | inteiro, opcional | referência a vaga |

**interaction**: id, contact_id, date, summary.

**job_history**: id, job_id, date, field, old_value, new_value, source.

**Status de vaga (`job.status`):** suggested, to_apply, blocked, applied, in_review, hr_interview, tech_interview, manager_interview, offer, hired, rejected, withdrawn, closed. Encerram o follow-up: hired, rejected, withdrawn, closed. Não geram follow-up: suggested, to_apply, blocked.

**Status de contato (`contact.status`):** to_contact, awaiting_reply, in_conversation, resume_sent, referred, closed. Não geram follow-up: to_contact, closed.

Sem migrações: o esquema é criado na primeira execução.

## APIs ou interfaces

Ferramentas MCP (contrato público do projeto):

| Ferramenta | Parâmetros | Retorno |
|---|---|---|
| `list_jobs` | `status?`, `track?`, `min_score?` | lista de vagas |
| `add_job` | `company`, `title`, `url`, `track?`, `score?`, `next_step?` | vaga criada no status `suggested`, ou erro de duplicidade com a vaga existente |
| `update_job` | `job_id`, `status?`, `next_step?`, `applied_on?`, `last_contact_on?`, `source` | vaga atualizada e linhas de histórico geradas; ao mudar para `applied` sem data de candidatura (nem gravada nem informada), `applied_on` recebe a data de referência, com a linha de histórico correspondente |
| `list_contacts` | `status?`, `company?` | lista de contatos |
| `log_interaction` | `contact_id`, `summary`, `date?`, `status?`, `next_step?` | contato atualizado, follow-up novo e vaga vinculada, se houver; contato em `to_contact` registrado sem `status` avança para `awaiting_reply` (com `status` informado, vale o informado) |
| `pending_followups` | `reference_date?`, `days_ahead?` (padrão 2) | vagas e contatos, cada um com `follow_up` e `state` (overdue, due_soon) |
| `daily_summary` | `reference_date?`, `deadline?` | contagem de vagas por status, contagem de contatos ativos (os que não estão em `closed`), vencidos, a vencer, fila de candidatura por nota e dias até o prazo (`deadline`), quando informado |

Nenhuma mudança incompatível, por ser a primeira versão. Depois de publicado, renomear ferramenta ou parâmetro passa a ser mudança incompatível.

## Estratégia de testes

- **Unidade (domínio):** cálculo de follow-up de vaga e de contato, classificação por data de referência e validação de status. Cobre os critérios de follow-up e de status inválido.
- **Unidade (vagas e contatos):** duplicidade de link, histórico gerado na atualização e interação que atualiza a vaga vinculada. Banco SQLite temporário por teste.
- **Unidade (resumo):** com os dados sintéticos e data fixa, conferir contagens, vencidos, a vencer e a ordem da fila.
- **Integração (servidor):** listar as ferramentas registradas e chamar uma delas pelo cliente em memória do pacote fastmcp (`from fastmcp import Client`), para confirmar nomes, parâmetros e formato de retorno, incluindo a saída estruturada (decisão 0003).
- **Verificação manual:** conectar o servidor ao Claude Code por stdio e executar os cinco casos de uso da especificação; registrar o resultado em `docs/evidence/`.

## Riscos técnicos

- **API do pacote fastmcp diferente da esperada.** Mitigação: fixar a versão no `pyproject.toml` e consultar a documentação atual do fastmcp antes da tarefa 06; a lógica não depende do pacote. Ver a decisão 0003.
- **Saída estruturada das ferramentas.** Em um teste com o SDK oficial, uma ferramenta com retorno `dict` chegou ao cliente só como texto. Mitigação: verificar na tarefa 06, com o fastmcp, o que o cliente recebe antes de fixar o formato de retorno (decisão 0003).
- **Datas em texto no SQLite.** Mitigação: gravar sempre em ISO 8601 (AAAA-MM-DD) e converter em um único ponto (`db.py`).
- **Banco real criado dentro do repositório por engano.** Mitigação: caminho padrão em `data/local/`, ignorado pelo Git, e teste que falha se o banco de teste não estiver em diretório temporário.
- **Reversão:** projeto novo; reverter é descartar a branch da tarefa.

## Plano de implementação

Cada etapa é uma tarefa em `docs/tasks/`, na ordem:

1. `01-estrutura-do-projeto-python.md` — `pyproject.toml`, pacote vazio, pytest e ruff rodando.
2. `02-banco-e-dados-sinteticos.md` — esquema SQLite, conexão e carga de `data/seed/`.
3. `03-regras-de-dominio-e-vagas.md` — status, follow-up, listar, registrar e atualizar vagas com histórico.
4. `04-contatos-e-interacoes.md` — listar contatos e registrar interações.
5. `05-followups-e-resumo.md` — `pending_followups` e `daily_summary`.
6. `06-servidor-mcp.md` — registro das sete ferramentas no FastMCP e teste de integração.
7. `07-readme-e-evidencia.md` — instruções de uso, configuração no cliente e evidência da verificação manual.
