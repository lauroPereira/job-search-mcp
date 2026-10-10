# Tarefa: Servidor MCP

## Objetivo

Expor as sete operações como ferramentas MCP por stdio.

## Especificação relacionada

`docs/specs/servidor-mcp-busca-de-emprego-plano.md` (seção "APIs ou interfaces").

## Pré-condições

- Tarefa 05 concluída.
- Documentação atual do pacote fastmcp conferida, na versão fixada no `pyproject.toml`, para confirmar a forma de registrar ferramentas e de testá-las (decisão `docs/architecture/decisions/0003-usar-pacote-fastmcp.md`).

## Arquivos prováveis

- `src/job_search_mcp/server.py`
- `tests/test_server.py`
- `pyproject.toml` (ponto de entrada de linha de comando)

## Passos

1. Criar o servidor com o pacote fastmcp (`from fastmcp import FastMCP`), com o nome `job-search`.
2. Registrar as sete ferramentas com os nomes e parâmetros do plano, com tipos e descrições claras em cada parâmetro (o agente decide o que chamar a partir delas).
3. Em cada ferramenta, abrir a conexão no caminho configurado, criar o esquema se o banco for novo, aplicar o padrão "hoje" para a data de referência e delegar à função de domínio.
4. Adicionar um ponto de entrada `job-search-mcp` que sobe o servidor em stdio e uma opção para carregar o seed em um banco novo.
5. Testar a listagem das ferramentas e uma chamada de ponta a ponta pelo cliente em memória do pacote fastmcp (`from fastmcp import Client`).
6. Validar as entradas na borda, antes de delegar ao domínio (pontos levantados na revisão das tarefas 03 a 05):
   - recusar datas futuras (posteriores à data atual) em `log_interaction` (`date`) e em `update_job` (`applied_on` e `last_contact_on`), com erro estruturado;
   - tipar `days_ahead` como inteiro e recusar valor negativo (inteiro >= 0);
   - não expor `reference_date` como parâmetro de `update_job`: a ferramenta passa a data atual ao domínio;
   - converter as datas recebidas como texto (ISO 8601, AAAA-MM-DD) antes de usá-las, devolvendo `invalid_date` quando o texto for inválido.
7. Verificar a saída estruturada: conferir o que o cliente recebe de uma ferramenta com retorno `dict` (dado estruturado ou só texto) e ajustar o retorno das ferramentas para que resultados e erros de negócio cheguem estruturados. Registrar o que foi observado na Validação.

## Critérios de conclusão

- [x] O cliente de teste lista exatamente as sete ferramentas do plano.
- [x] Uma chamada a `daily_summary` com data fixa devolve o objeto esperado.
- [x] O servidor sobe por `job-search-mcp` sem erro e sem escrever fora do caminho do banco.
- [x] Erros de negócio chegam ao cliente como resposta estruturada.

## Validação

Executada em 2026-10-10, no Windows 11, com Python 3.12.7 no ambiente virtual `.venv`, sobre `develop` com as tarefas 01 a 05 integradas. Pacotes instalados: `fastmcp` 4.1.0, `mcp` 2.3.0 (transitivo), `pydantic` 2.14.0, `pytest` 9.1.1, `ruff` 0.17.0.

### O que foi confirmado sobre a API do fastmcp 4.1.0, e como

Método: inspeção do pacote instalado no `.venv` (`inspect.signature` e `inspect.getdoc` de `FastMCP.__init__`, `FastMCP.tool`, `FastMCP.run`, `Client.__init__`, `Client.call_tool` e `StdioTransport.__init__`), um script descartável (não versionado) com um servidor de sonda chamado pelo cliente em memória, e leitura da documentação oficial em `https://gofastmcp.com/servers/tools` e `https://gofastmcp.com/development/tests` em 2026-10-10.

| Ponto | Observado |
|---|---|
| Registro de ferramenta | `@mcp.tool` ou `@mcp.tool(annotations=...)` sobre uma função com tipos. A docstring vira a descrição da ferramenta. |
| Descrição e tipo de parâmetro | `Annotated[tipo, Field(description=...)]` (pydantic) gera `description`, `type` e `default` no esquema de entrada; parâmetro sem padrão entra em `required`. |
| Subir em stdio | `mcp.run(transport="stdio", show_banner=False)`; é síncrono. O log vai para a saída de erro, e a saída padrão fica só com o protocolo. |
| Cliente em memória | `async with Client(mcp) as client:` com `await client.list_tools()` e `await client.call_tool(nome, argumentos, raise_on_error=False)`. |
| Cliente por stdio | `Client(StdioTransport(command=..., args=[...], env={...}, keep_alive=False))`, de `fastmcp.client.transports`. |
| Resultado da chamada | `CallToolResult` com `content`, `structured_content`, `data`, `meta` e `is_error`. |
| Retorno `dict` | Chega estruturado: `structured_content` é o próprio objeto, e `content` traz o mesmo JSON como texto. Esquema de saída: `{"type": "object", "additionalProperties": true}`. O problema visto com o SDK oficial (decisão 0003) não ocorre. |
| Retorno `list[dict]` | Também chega estruturado, mas embrulhado pelo pacote: `structured_content` é `{"result": [...]}` e o esquema de saída recebe `x-fastmcp-wrap-result`. |
| Argumento que não passa na validação de tipo (texto onde se espera inteiro, ou restrição `ge=0`) | O pacote recusa antes de chamar a função: `is_error` verdadeiro, `structured_content` nulo e o erro do pydantic como texto. |
| Exceção dentro da ferramenta | `is_error` verdadeiro, `structured_content` nulo e o texto `Error calling tool '<nome>': <mensagem>`. |
| Nomes de campos no cliente | `tool.input_schema` e `tool.output_schema`; os nomes antigos (`inputSchema`, `outputSchema`) emitem aviso de descontinuação. |

### Decisões que saíram dessa verificação

- Todas as ferramentas devolvem um objeto (`dict`), e por isso o resultado e o erro de negócio chegam sempre no mesmo lugar (`structured_content`), com `is_error` falso. Erro de negócio é o objeto `{"error": código, "detail": mensagem, ...}` que o domínio já devolvia.
- `list_jobs` e `list_contacts` devolvem `{"jobs": [...]}` e `{"contacts": [...]}`, e não a lista pura. Com a lista pura, o pacote embrulharia o resultado em `{"result": [...]}` e um erro de status inválido chegaria em `{"result": {"error": ...}}`, em lugar diferente do das outras ferramentas. O plano foi ajustado nessas duas linhas da tabela de ferramentas (era "lista de vagas" e "lista de contatos"). **É uma escolha de formato do contrato público e deve ser conferida na revisão.**
- Status e datas são recebidos como texto, e não como `Literal` ou `date`: assim o valor inválido volta como erro estruturado com a lista de status válidos (`invalid_status`) ou com o formato esperado (`invalid_date`), em vez de virar erro de validação em texto. Os valores válidos estão na descrição de cada parâmetro.
- `days_ahead` é tipado como inteiro; o valor negativo é recusado dentro da ferramenta com o erro estruturado `invalid_input`. Não foi usada a restrição `ge=0` no esquema, porque ela devolveria erro em texto.
- Limite conhecido: argumento de tipo errado (por exemplo `job_id="abc"`) ou parâmetro desconhecido é recusado pelo pacote como erro de protocolo em texto (`is_error` verdadeiro), e não como erro de negócio. O teste `test_update_job_does_not_expose_reference_date` usa esse comportamento.
- Data futura usa o código `invalid_date` já existente, com a mensagem `it cannot be after today`; não foi criado código novo.
- "Hoje" vem de uma única função, `server.today()`, que os testes substituem. `update_job` não recebe `reference_date`: passa `today()` ao domínio. `log_interaction` sem `date` usa `today()`.
- Cada ferramenta abre a conexão por `open_database()`, que cria o esquema e fecha a conexão no `finally`.
- `job-search-mcp --seed` carrega os dados de demonstração e encerra, sem subir o servidor; se alguma tabela já tiver linhas, recusa com mensagem na saída de erro e código 1. Sem a opção, sobe o servidor em stdio. `python -m job_search_mcp.server` faz o mesmo.
- As quatro ferramentas de consulta levam a anotação `readOnlyHint`.
- Testes assíncronos: os testes chamam o cliente com `asyncio.run` dentro de testes síncronos. Nenhuma dependência de desenvolvimento nova (nem `pytest-asyncio` nem configuração de `anyio`), e o CI não precisou mudar.

### Comandos e resultados

| Comando | Resultado observado |
|---|---|
| `python -m pytest` | `121 passed in 12.61s` (101 anteriores e 20 em `tests/test_server.py`; código 0) |
| `python -m ruff check .` | `All checks passed!` (código 0) |
| `python tools/scripts/lint_and_tests.py --strict` | pytest `121 passed`, ruff `All checks passed!`, `Skills válidas.`, `Validação estrita concluída sem falhas.` (código 0) |
| `job-search-mcp --seed`, com `JOB_SEARCH_DB` em um diretório temporário | `Demo data loaded into <diretório temporário>/demo.db.` (código 0) |
| `job-search-mcp --seed` de novo, no mesmo banco | `Refused: the database at <diretório temporário>/demo.db already has data. The demo data only goes into a new database; point JOB_SEARCH_DB to another file.` (código 1) |
| `git status --short -uall` e `find . -name "*.db" -o -name "*.sqlite*"` (fora de `.venv`) depois dos testes e da verificação por stdio | só os arquivos da tarefa; nenhum arquivo de banco; `data/local/` não foi criado |

### Verificação real por stdio

Um script descartável (não versionado) subiu o executável `job-search-mcp` do `.venv` como subprocesso, com `JOB_SEARCH_DB` apontando para o banco de demonstração criado acima em diretório temporário, e conectou `Client(StdioTransport(...))`. Saída observada:

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
--> daily_summary {"reference_date": "2026-03-16"} | is_error=False | structured=yes | content_blocks=1
--> pending_followups {"reference_date": "2026-03-16"} | is_error=False | structured=yes | content_blocks=1
```

(Na saída real cada linha `tool` traz também a primeira linha da descrição, omitida aqui.) Saída de erro do subprocesso: só a linha de log `Starting MCP server 'job-search' with transport 'stdio'`.

Conteúdo estruturado devolvido (resumo; os itens vêm completos, com todos os campos da vaga ou do contato):

| Chamada | Retorno |
|---|---|
| `daily_summary(reference_date="2026-03-16")` | `jobs_by_status`: suggested 1, to_apply 2, blocked 1, applied 2, in_review 1, hr_interview 1, tech_interview 1, manager_interview 1, offer 1, hired 1, rejected 1, withdrawn 1, closed 1; `active_contacts` 7; `overdue`: vagas 5 e 1, contatos 1 e 4; `due_soon`: vagas 7, 2 e 3, contatos 2 e 7; `application_queue`: vagas 8 (9.5), 9 (7.8) e 10 (5.5); `deadline` e `days_to_deadline` nulos |
| `pending_followups(reference_date="2026-03-16")` | `days_ahead` 2; vagas 5 (2026-03-11, overdue), 1 (2026-03-16, overdue), 7 (2026-03-17, due_soon), 2 e 3 (2026-03-18, due_soon); contatos 1 (2026-03-14, overdue), 4 (2026-03-16, overdue), 2 (2026-03-17, due_soon), 7 (2026-03-18, due_soon) |

São os mesmos valores da tabela da tarefa 05. A suíte também tem um teste que sobe o servidor como subprocesso (`test_server_runs_over_stdio_as_a_subprocess`, com `python -m job_search_mcp.server`).

### Como cada critério foi comprovado

- Sete ferramentas: `test_server_lists_exactly_the_seven_tools` (nomes, descrição de cada ferramenta e de cada parâmetro, esquema de saída do tipo objeto) e `test_tool_parameters_match_the_plan` (parâmetros e obrigatórios de cada uma); e a verificação por stdio acima.
- `daily_summary` com data fixa: `test_daily_summary_uses_today_and_returns_the_expected_object` ("hoje" fixado em 2026-03-16; o conteúdo estruturado é igual ao retorno da função de domínio e aos números do seed) e `test_daily_summary_accepts_reference_date_and_deadline_as_iso_text`.
- Sobe por `job-search-mcp` sem escrever fora do banco: verificação por stdio acima, `test_server_runs_over_stdio_as_a_subprocess`, `test_nothing_is_written_outside_the_temporary_directory` (seis chamadas, todas as conexões no arquivo do diretório temporário, que fica só com esse arquivo) e `test_seed_option_loads_a_new_database_and_refuses_one_with_data`.
- Erros de negócio estruturados: `test_duplicate_url_arrives_as_a_structured_error`, `test_invalid_status_arrives_as_a_structured_error_with_the_valid_ones`, `test_update_job_rejects_future_and_invalid_dates`, `test_log_interaction_rejects_future_and_invalid_dates` e `test_pending_followups_rejects_negative_days_ahead_and_invalid_date`.
- Demais regras da borda: `test_update_job_writes_history_dated_today`, `test_update_job_does_not_expose_reference_date`, `test_pending_followups_defaults_to_today_and_two_days_ahead`, `test_log_interaction_updates_the_contact_and_the_linked_job`, `test_add_job_then_list_jobs`, `test_list_contacts_filters_by_status_and_company`, `test_tools_create_the_schema_in_a_new_database` e `test_tools_close_the_connection_even_when_the_domain_fails`.

### CI do pull request

Pull request #8 (commit `3bcfac0`): `gh pr checks 8` devolveu `validate pass 27s`.

### Limitações

- A verificação por stdio foi feita por um cliente MCP programático (o `Client` do fastmcp), e não por uma pessoa usando o Claude Code ou o Claude Desktop.
- O caminho padrão do banco (`data/local/job_search.db`) é calculado a partir do diretório do código, o que pressupõe instalação em modo editável a partir do clone (`pip install -e .`). Com outra forma de instalação, defina `JOB_SEARCH_DB`. É comportamento da tarefa 02, não alterado aqui.

## Status

```text
concluída
```
