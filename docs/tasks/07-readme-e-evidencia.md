# Tarefa: README de uso e evidência

## Objetivo

Documentar instalação, configuração no cliente e uso, e registrar a verificação manual dos casos de uso.

## Especificação relacionada

`docs/specs/servidor-mcp-busca-de-emprego.md` (casos de uso e critérios de aceitação).

## Pré-condições

- Tarefa 06 concluída.

## Arquivos prováveis

- `README.md`
- `docs/evidence/<data>-verificacao-manual.md`

## Passos

1. Atualizar o README: instalação, como carregar os dados de demonstração, configuração do servidor no Claude Code e no Claude Desktop e um exemplo de conversa para cada caso de uso.
2. Acrescentar um diagrama simples da arquitetura (cliente MCP, servidor, domínio, SQLite).
3. Conectar o servidor a um cliente MCP e executar os cinco casos de uso com o banco de demonstração.
4. Registrar em `docs/evidence/` o que foi pedido ao agente, as ferramentas chamadas e o resultado, sem dados reais.
5. Marcar os critérios de aceitação da especificação e mudar o estado do README de "em especificação" para o estado real.

## Critérios de conclusão

- [ ] Uma pessoa sem contexto consegue instalar e rodar a demonstração seguindo o README.
  - Parcial. Os passos de instalação e de carga da demonstração do README foram seguidos em um ambiente virtual novo e funcionaram (ver Validação). Não foi verificado: a leitura por uma pessoa sem contexto e a configuração no Claude Code e no Claude Desktop. Fica para o responsável humano.
- [x] Os cinco casos de uso têm evidência registrada.
  - Com a ressalva de que a evidência é de um cliente MCP programático via stdio, e não de uma conversa com um agente.
- [x] Todos os critérios de aceitação da especificação estão marcados ou têm pendência explicada.
- [x] O repositório continua sem dados reais.

## Validação

Executada em 2026-10-10, no Windows 11, com Python 3.12.7, na branch `feat/07-readme-e-evidencia`, criada a partir de `feat/06-servidor-mcp` (commit `3bcfac0`, pull request #8, ainda não integrado em `develop`). Esta tarefa só altera documentação.

### O que foi feito

- `README.md`: estado real do projeto; diagrama da arquitetura em Mermaid; tabela das ferramentas com parâmetros e retorno; instalação; dados de demonstração (`job-search-mcp --seed`); configuração no Claude Code (`claude mcp add` e `.mcp.json`) e no Claude Desktop (`claude_desktop_config.json`), com caminhos de exemplo genéricos; um exemplo de conversa para cada caso de uso; como rodar os testes. As seções de privacidade, forma de desenvolvimento, roteiro e licença foram mantidas. A seção "Como validar" passou a se chamar "Como rodar os testes".
- `docs/evidence/2026-10-10-verificacao-dos-casos-de-uso.md`: os cinco casos de uso executados contra o servidor real por stdio.
- `docs/specs/servidor-mcp-busca-de-emprego.md`: critérios de aceitação marcados, cada um com o teste ou a evidência que o comprova, e a pendência da verificação manual.

### Comandos e resultados

| Comando | Resultado observado |
|---|---|
| `python -m pytest` | `121 passed` (código 0) |
| `python -m ruff check .` | `All checks passed!` (código 0) |
| `python tools/scripts/lint_and_tests.py --strict` | pytest `121 passed`, ruff `All checks passed!`, `Skills válidas.`, `Validação estrita concluída sem falhas.` (código 0) |
| Ambiente virtual novo, `pip install -e .` (passos do README, sem as dependências de desenvolvimento) | instalou `fastmcp` 4.1.0 e criou o executável `job-search-mcp` |
| `job-search-mcp --seed` nesse ambiente, com `JOB_SEARCH_DB` em diretório temporário | `Demo data loaded into <diretório temporário>/demo.db.` (código 0) |
| Script descartável com `Client(StdioTransport(...))` contra esse executável: os cinco casos de uso, 11 chamadas | 7 ferramentas listadas; todas as chamadas com `is_error=False` e conteúdo estruturado; retornos registrados na evidência |
| A mesma execução com o ambiente de desenvolvimento, em outro banco novo | saída idêntica, exceto o horário de criação da vaga do caso 4 |
| `python -m pytest` com as conexões de saída e a resolução de nomes bloqueadas no processo (só o endereço local liberado), por um script descartável | `121 passed`; nenhuma tentativa de conexão bloqueada |
| Busca nos arquivos versionados por e-mails, telefones, CPF, valores em reais e caminhos de máquina | nenhuma ocorrência |
| `git status --short -uall` e busca por `*.db` e `*.sqlite*` (fora de `.venv`) depois das execuções | só os arquivos da tarefa; nenhum arquivo de banco; `data/local/` não foi criado |

### Formatos de configuração dos clientes

Conferidos na documentação em 2026-10-10:

- Claude Code, em `https://code.claude.com/docs/en/mcp`: `claude mcp add [opções] <nome> -- <comando> [argumentos]`, com `--env CHAVE=valor` e `--transport stdio` antes do nome; e o arquivo `.mcp.json` com `mcpServers`, `type`, `command`, `args` e `env`.
- Claude Desktop, em `https://modelcontextprotocol.io/docs/develop/connect-local-servers`: arquivo `claude_desktop_config.json` (aberto em Settings, Developer, Edit Config), com `mcpServers`, `command`, `args` e `env`, e reinício do aplicativo.

**Não foi verificado:** os blocos de configuração do README não foram executados em nenhum dos dois aplicativos. O formato vem da documentação; o comando e a variável vêm da verificação por stdio.

### CI do pull request

Pull request #9 (commit `9e2f7e8`): `gh pr checks 9` devolveu `validate pass 24s`. O commit que registra esta linha dispara uma nova execução, conferida no relatório de passagem.

### Limitações e pendências

- **A verificação dos casos de uso foi feita por um cliente MCP programático via stdio, e não por uma pessoa conversando com um agente no Claude Code ou no Claude Desktop.** O objetivo da tarefa fala em "verificação manual"; essa parte fica pendente para o responsável humano, com os passos na evidência. Por isso o arquivo de evidência se chama `verificacao-dos-casos-de-uso`, e não `verificacao-manual`.
- As falas dos exemplos de conversa do README são ilustrativas; só as chamadas e os retornos foram observados.
- Linux e macOS: as instruções do README para esses sistemas não foram executadas à mão; o CI roda a suíte em Ubuntu.
- O caminho padrão do banco pressupõe instalação em modo editável a partir do clone (ver a tarefa 06); o README instrui essa forma de instalação e o uso de `JOB_SEARCH_DB`.

## Status

```text
concluída, com pendência para o responsável humano (verificação manual nos clientes de conversa)
```
