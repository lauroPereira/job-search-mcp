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

- [ ] O projeto instala em um ambiente limpo, em modo editável, com as dependências de desenvolvimento.
- [ ] `pytest` passa com 1 teste.
- [ ] `ruff check .` não aponta erros.
- [ ] `python tools/scripts/lint_and_tests.py --strict` termina com código 0.

## Validação

A preencher na execução: comandos rodados e saída observada.

## Status

```text
pendente
```
