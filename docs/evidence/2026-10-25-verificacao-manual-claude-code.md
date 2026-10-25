# Verificação manual em uma conversa no Claude Code

## O que este documento é

Registro da verificação feita pelo responsável humano em 2026-10-25: o servidor foi configurado no Claude Code seguindo o README e usado em uma conversa real, em linguagem natural, com os pedidos dos exemplos do README. Complementa a [verificação por cliente programático](2026-10-10-verificacao-dos-casos-de-uso.md), que comprovou o protocolo mas não a escolha das ferramentas por um agente.

## Método

- **Versão:** `develop` @ `3fbb10a` (tarefas 01 a 08).
- **Ambiente:** Windows 11, Claude Code, executável `job-search-mcp.exe` do ambiente virtual do clone (instalação editável, como no README).
- **Configuração:** o comando `claude mcp add --env JOB_SEARCH_DB=<caminho absoluto> --transport stdio job-search -- <caminho absoluto>\.venv\Scripts\job-search-mcp.exe` da seção "Configuração no cliente" do README, com caminhos do Windows.
- **Banco:** arquivo novo em `data/local/` (ignorado pelo Git), preenchido com `job-search-mcp --seed` (`Demo data loaded into ...`, código 0). Só dados sintéticos.
- **Data de referência declarada nos pedidos:** 2026-03-16. A data real da máquina era 2026-10-25.
- **Ordem:** os quatro pedidos abaixo, em sequência, na mesma conversa e no mesmo banco.

## Resultados

| Pedido (resumido) | Ferramenta chamada | Resultado observado | Confere com o README |
|---|---|---|---|
| "Considere que hoje é 16/03/2026. O que eu preciso fazer hoje? Quero estar empregado até 15/04." | `job-search` (resumo do dia) | 30 dias até o prazo; Transportadora Pampa vencida desde 11/03; Banco Aurora e Diego Amostra vencendo hoje; Financeira Colibri (9,5) no topo da fila; a vencer: Bruno Modelo, Loja Horizonte, Seguradora Vértice, Gabriela Ensaio | sim |
| "Falei hoje (16/03/2026) com a Ana Exemplo, do Banco Aurora; a indicação foi encaminhada ao RH." | `job-search` (registro de interação) | follow-up da Ana em 22/03; vaga vinculada do Banco Aurora com último contato 16/03 e follow-up em 23/03 | sim (ver divergência 2) |
| "Guarda esta vaga: Analytics Engineer na Empresa Exemplo, <link example.com>, trilha data, nota 8." | `job-search` (cadastro de vaga) | vaga id 16, status `suggested`, trilha `data`, nota 8 | sim |
| Mesmo cadastro repetido | `add_job` | erro `duplicate_url` com a vaga existente (id 16); nada criado | sim |
| "Quem eu preciso cobrar em 16/03/2026?" | `job-search` (follow-ups pendentes) | vencidos: Transportadora Pampa e Diego Amostra; Banco Aurora e Ana fora da lista por causa do registro anterior | sim |

O cadastro repetido foi feito pela ferramenta `add_job` do mesmo servidor, a partir de outra sessão do Claude Code, e não digitado na conversa.

## Divergências observadas

1. **`created_at` com a data real.** A vaga id 16 ficou com `created_at` 2026-10-25, e não com a data declarada 16/03. É o comportamento documentado: `add_job` não recebe data e o SQLite grava a data do relógio. O próprio agente apontou a diferença.
2. **Status escolhido pelo agente.** Ao registrar a conversa com a Ana, o agente gravou o status `referred` por iniciativa própria (o exemplo do README usa `in_conversation`) e só avisou depois. O servidor fez o que foi pedido; a decisão foi do agente. É um argumento para a fase 2 (aprovação humana antes de gravar, decisão 0002).
3. **Redação e prioridade.** O resumo do dia colocou em primeiro lugar a oferta da Usina Solaris (prazo 17/03), que o exemplo ilustrativo do README não cita. Os dados são os mesmos; muda a redação, como o README avisa.
4. **Data de hoje.** O agente percebeu que a data real era 2026-10-25 e usou a data declarada 16/03, como pedido.

## Conclusão

A configuração do README funciona no Claude Code no Windows (`claude mcp add` incluído), e o agente escolheu a ferramenta certa nos quatro pedidos em linguagem natural. Continuam não verificados: o Claude Desktop, os comandos de Linux e macOS (só a suíte roda no Ubuntu, pelo CI) e a renderização do diagrama Mermaid.
