# Tarefa: Servidor MCP

## Objetivo

Expor as sete operações como ferramentas MCP por stdio.

## Especificação relacionada

`docs/specs/servidor-mcp-busca-de-emprego-plano.md` (seção "APIs ou interfaces").

## Pré-condições

- Tarefa 05 concluída.
- Documentação atual do SDK de MCP para Python consultada, para confirmar a forma de registrar ferramentas e de testá-las.

## Arquivos prováveis

- `src/job_search_mcp/server.py`
- `tests/test_server.py`
- `pyproject.toml` (ponto de entrada de linha de comando)

## Passos

1. Criar o servidor FastMCP com o nome `job-search`.
2. Registrar as sete ferramentas com os nomes e parâmetros do plano, com tipos e descrições claras em cada parâmetro (o agente decide o que chamar a partir delas).
3. Em cada ferramenta, abrir a conexão no caminho configurado, criar o esquema se o banco for novo, aplicar o padrão "hoje" para a data de referência e delegar à função de domínio.
4. Adicionar um ponto de entrada `job-search-mcp` que sobe o servidor em stdio e uma opção para carregar o seed em um banco novo.
5. Testar a listagem das ferramentas e uma chamada de ponta a ponta pelo cliente em memória do SDK.

## Critérios de conclusão

- [ ] O cliente de teste lista exatamente as sete ferramentas do plano.
- [ ] Uma chamada a `resumo_do_dia` com data fixa devolve o objeto esperado.
- [ ] O servidor sobe por `job-search-mcp` sem erro e sem escrever fora do caminho do banco.
- [ ] Erros de negócio chegam ao cliente como resposta estruturada.

## Validação

A preencher na execução.

## Status

```text
pendente
```
