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

- [ ] O cliente de teste lista exatamente as sete ferramentas do plano.
- [ ] Uma chamada a `daily_summary` com data fixa devolve o objeto esperado.
- [ ] O servidor sobe por `job-search-mcp` sem erro e sem escrever fora do caminho do banco.
- [ ] Erros de negócio chegam ao cliente como resposta estruturada.

## Validação

A preencher na execução.

## Status

```text
pendente
```
