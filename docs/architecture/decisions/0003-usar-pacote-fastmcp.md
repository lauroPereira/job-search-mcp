# 0003. Usar o pacote fastmcp

## Título

Usar o pacote independente `fastmcp`, e não o SDK oficial `mcp`, para registrar e testar as ferramentas do servidor.

## Status

```text
aceita
```

Aceita pelo autor em 2026-10-10. Substitui apenas a escolha da biblioteca de MCP feita na decisão 0001; o restante da 0001 continua valendo.

## Contexto

A decisão 0001 definiu a biblioteca como "SDK oficial de MCP (FastMCP)". Essa expressão junta dois pacotes diferentes:

- o SDK oficial, publicado como `mcp`, que nas séries anteriores trazia uma classe `FastMCP` embutida (`mcp.server.fastmcp`);
- o pacote independente `fastmcp`, mantido por terceiros, de onde essa interface se originou e que seguiu evoluindo por conta própria.

Na tarefa 01 foi fixado `mcp==2.3.0`. Na série 2.x do SDK oficial a classe `FastMCP` embutida foi renomeada para `MCPServer`, e o import antigo (`mcp.server.fastmcp`) falha; isso foi verificado na versão 2.3.0. A decisão 0001, o plano e a tarefa 06 citam "FastMCP", então era preciso escolher explicitamente qual pacote o projeto usa antes de escrever o servidor.

## Decisão

O projeto usa o pacote independente `fastmcp`, com a versão fixada em `fastmcp==4.1.0` no `pyproject.toml`.

- Servidor: `from fastmcp import FastMCP`.
- Cliente de teste em memória: `from fastmcp import Client`.

Esta decisão substitui somente a parte da biblioteca da decisão 0001. Continuam valendo: Python 3.12, SQLite pela biblioteca padrão sem ORM, transporte stdio e a separação entre a lógica de domínio e o módulo do servidor.

## Alternativas consideradas

- **SDK oficial `mcp` 2.x com `MCPServer`.** É a linha oficial do protocolo. Descartada por preferência do autor pela interface e pela documentação do `fastmcp`.
- **SDK oficial `mcp<2`, com a classe `FastMCP` embutida.** Descartada: é uma API descontinuada, substituída na série 2.x.

## Consequências

- O projeto passa a depender de um pacote de terceiro, e não da linha oficial do protocolo. A versão fica fixada (`==`), e cada atualização é uma mudança explícita e revisada.
- O `fastmcp` instala o SDK oficial `mcp` como dependência transitiva; o projeto não o importa diretamente.
- A lógica de domínio continua sem depender da biblioteca: ela só aparece em `server.py` e no teste de integração, o que limita o custo de uma troca futura.
- **A verificar na tarefa 06:** como devolver saída estruturada. Em um teste com o SDK oficial, uma ferramenta com retorno `dict` chegou ao cliente só como texto. O plano prevê erros de negócio e resultados como respostas estruturadas, então a tarefa 06 deve conferir, com o `fastmcp` e a versão fixada, o que o cliente recebe, antes de fixar o formato de retorno das ferramentas.
- Antes da tarefa 06, a documentação atual do `fastmcp` deve ser consultada, porque a forma de registrar e de testar ferramentas pode ter mudado entre versões.

## Data

2026-10-10
