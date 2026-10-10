# Tarefa: Estrutura do projeto Python

## Objetivo

Criar o esqueleto do pacote, com pytest e ruff rodando em um projeto ainda sem funcionalidades.

## Especificação relacionada

`docs/specs/servidor-mcp-busca-de-emprego-plano.md` (etapa 1).

## Pré-condições

- Decisão 0001 aceita pelo autor (feito em 2026-10-10).
- Python 3.12 disponível.

## Arquivos prováveis

- `pyproject.toml`
- `src/job_search_mcp/__init__.py`
- `tests/test_smoke.py`

## Passos

1. Criar `pyproject.toml` com o pacote `job_search_mcp` em `src/`, Python 3.12 ou superior, a dependência do SDK de MCP com versão fixada e o grupo de desenvolvimento com pytest e ruff.
2. Criar `src/job_search_mcp/__init__.py` com a versão do pacote.
3. Criar um teste mínimo que importa o pacote e confere a versão.
4. Configurar ruff no `pyproject.toml` (tamanho de linha 100, regras padrão mais ordenação de imports).
5. Rodar `python tools/scripts/lint_and_tests.py --strict` e corrigir o que falhar.

## Critérios de conclusão

- [x] O projeto instala em um ambiente limpo, em modo editável, com as dependências de desenvolvimento.
- [x] `pytest` passa com 1 teste.
- [x] `ruff check .` não aponta erros.
- [x] `python tools/scripts/lint_and_tests.py --strict` termina com código 0.

## Validação

Executada em 2026-10-10, no Windows 11, com Python 3.12.7 em um ambiente virtual novo (`.venv`).

| Comando | Resultado observado |
|---|---|
| `python -m venv .venv` e `python -m pip install -e ".[dev]"` | instalação concluída sem erro; `job-search-mcp 0.1.0` (editável), `mcp 2.3.0`, `pytest 9.1.1`, `ruff 0.17.0` |
| `python -m pytest` | `1 passed in 0.03s` (código 0) |
| `python -m ruff check .` | `All checks passed!` (código 0) |
| `python tools/scripts/lint_and_tests.py --strict` | pytest `1 passed`, ruff `All checks passed!`, `Skills válidas.`, `Validação estrita concluída sem falhas.` (código 0) |

Observações:

- A versão do SDK de MCP foi consultada com `pip index versions mcp`; a mais recente era a 2.3.0, fixada como `mcp==2.3.0`.
- **Ponto de atenção para a tarefa 06:** na série 2.x do SDK, `FastMCP` foi renomeado para `MCPServer` (`from mcp.server.mcpserver import MCPServer`); `import mcp.server.fastmcp` falha na 2.3.0 com uma mensagem que aponta o guia de migração. A decisão 0001 e o plano citam "FastMCP". Esta tarefa não usa o SDK, então nada foi alterado; cabe ao responsável decidir, antes da tarefa 06, entre usar `MCPServer` na 2.x ou fixar `mcp<2`.
- As dependências de desenvolvimento ficaram em `[project.optional-dependencies] dev`, instaladas com `pip install -e ".[dev]"`.
- Foi acrescentado `*.egg-info/` ao `.gitignore`, porque a instalação editável gera `src/job_search_mcp.egg-info/`.

## Status

```text
concluída
```
