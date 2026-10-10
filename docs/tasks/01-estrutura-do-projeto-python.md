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

1. Criar `pyproject.toml` com o pacote `job_search_mcp` em `src/`, Python 3.12 ou superior, a dependência da biblioteca de MCP (pacote `fastmcp`) com versão fixada e o grupo de desenvolvimento com pytest e ruff.
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

Executada em 2026-10-10, no Windows 11, com Python 3.12.7 em um ambiente virtual novo (`.venv`). A tabela abaixo é da reexecução feita depois da revisão do pull request, com o ambiente virtual recriado do zero.

| Comando | Resultado observado |
|---|---|
| `python -m venv .venv` e `python -m pip install -e ".[dev]"` | instalação concluída sem erro (código 0); `job-search-mcp 0.1.0` (editável), `fastmcp 4.1.0`, `pytest 9.1.1`, `ruff 0.17.0` |
| `python -c "from fastmcp import FastMCP; from fastmcp import Client"` | importa sem erro; `fastmcp.__version__` igual a `4.1.0` |
| `python -m pytest` | `1 passed in 0.02s` (código 0) |
| `python -m ruff check .` | `All checks passed!` (código 0) |
| `python tools/scripts/lint_and_tests.py --strict` | pytest `1 passed`, ruff `All checks passed!`, `Skills válidas.`, `Validação estrita concluída sem falhas.` (código 0) |
| `git check-ignore -v job.db src/t.sqlite` | os dois caminhos são ignorados pelas regras `*.db` e `*.sqlite` |
| `git check-ignore -v data/seed/jobs.csv` | casa com a exceção `!data/seed/*.csv`, ou seja, o arquivo não é ignorado |

Observações:

- **Troca de biblioteca (depois da revisão).** A primeira versão desta tarefa fixou o SDK oficial, `mcp==2.3.0`. Na série 2.x desse SDK a classe `FastMCP` embutida foi renomeada para `MCPServer`, e `import mcp.server.fastmcp` falha na 2.3.0. O responsável decidiu usar o pacote independente `fastmcp` (`from fastmcp import FastMCP`; cliente de teste `from fastmcp import Client`). A versão foi consultada com `pip index versions fastmcp`; a mais recente estável era a 4.1.0, fixada como `fastmcp==4.1.0`. A decisão fica registrada em `docs/architecture/decisions/0003-usar-pacote-fastmcp.md`, em pull request próprio.
- O `fastmcp 4.1.0` instala o SDK oficial `mcp 2.3.0` como dependência transitiva; o projeto não o importa diretamente.
- A licença passou a ser declarada na forma atual, `license = "MIT"` (expressão SPDX), e o requisito do `build-system` subiu para `setuptools>=77`, a primeira série que aceita essa forma.
- No `.gitignore`, as regras de banco deixaram de valer só para `data/` e passaram a ser globais (`*.db`, `*.sqlite`, `*.sqlite3`); foram acrescentadas `*.xls`, `*.xlsm` e `*.ods`. Continuam valendo `*.xlsx`, `*.csv` e a exceção `!data/seed/*.csv`.
- As dependências de desenvolvimento ficaram em `[project.optional-dependencies] dev`, instaladas com `pip install -e ".[dev]"`.
- Foi acrescentado `*.egg-info/` ao `.gitignore`, porque a instalação editável gera `src/job_search_mcp.egg-info/`.

## Status

```text
concluída
```
