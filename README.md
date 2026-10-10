# job-search-mcp

Servidor [MCP](https://modelcontextprotocol.io) que dá a um agente de IA as ferramentas para gerir uma busca de emprego: vagas, contatos de networking, follow-ups e um resumo do que fazer hoje.

> **Estado:** em especificação. O código ainda não foi escrito; a especificação, o plano e as tarefas estão em `docs/`.

## Por que este projeto existe

Durante uma recolocação profissional, usei agentes de IA todos os dias para acompanhar vagas e contatos. O controle vivia em planilhas e em scripts soltos, e o agente precisava reler tudo a cada conversa para responder perguntas simples como "o que vence hoje?".

Este servidor transforma aquele controle em ferramentas que qualquer cliente MCP (Claude Code, Claude Desktop e outros) consegue chamar: o agente consulta e atualiza o estado em vez de reinterpretar planilhas.

## O que ele vai fazer (MVP)

| Ferramenta | O que faz |
|---|---|
| `listar_vagas` | Lista vagas, com filtro por status, trilha e nota mínima |
| `registrar_vaga` | Inclui uma vaga nova, sem duplicar o link |
| `atualizar_vaga` | Muda status, próximo passo e data do último contato, com histórico |
| `listar_contatos` | Lista contatos de networking, com filtro por status e empresa |
| `registrar_interacao` | Registra uma conversa com um contato e recalcula o follow-up |
| `followups_pendentes` | Devolve vagas e contatos com follow-up vencido ou a vencer |
| `resumo_do_dia` | Monta o resumo: números gerais, o que mudou e o que pede atenção |

Detalhes em [`docs/specs/servidor-mcp-busca-de-emprego.md`](docs/specs/servidor-mcp-busca-de-emprego.md).

## Tecnologia

- Python 3.12
- SDK oficial de MCP para Python (FastMCP), transporte stdio
- SQLite pela biblioteca padrão
- pytest e ruff

As razões estão em [`docs/architecture/decisions/`](docs/architecture/decisions/).

## Dados e privacidade

O repositório é público e **não contém dados reais**. Os dados de demonstração em `data/seed/` são sintéticos. O banco de quem usa o servidor fica na própria máquina, fora do Git.

## Como o projeto é desenvolvido

O projeto nasceu do [ai-dev-template](https://github.com/lauroPereira/ai-dev-template) e segue desenvolvimento guiado por especificação (SDD), com agentes de IA em papéis definidos (Supervisor, Developer, Reviewer e QA):

```text
especificação → plano → tarefas → implementação → validação
```

- Especificação e plano: [`docs/specs/`](docs/specs/)
- Tarefas, na ordem de execução: [`docs/tasks/`](docs/tasks/)
- Instruções para agentes: [`AGENTS.md`](AGENTS.md) e [`CLAUDE.md`](CLAUDE.md)
- Origem e versão do template: [`docs/wiki/origem-template.md`](docs/wiki/origem-template.md)

## Como validar

```bash
python tools/scripts/lint_and_tests.py
```

No modo padrão o script valida a estrutura do projeto. Com `--strict`, também roda ruff e pytest (depois que houver código).

## Roteiro

1. **MVP:** as sete ferramentas acima, com testes e dados sintéticos.
2. **Importação:** carregar um controle existente a partir de CSV.
3. **Painel:** uma tela de leitura em Streamlit sobre o mesmo banco.

## Licença

A definir.
