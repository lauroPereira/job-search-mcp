# Verificação manual da v0.2.0 em uma conversa no Claude Code

## O que este documento é

Registro da verificação feita pelo responsável humano em 2026-10-25: o servidor `v0.2.0` configurado no Claude Code e usado em uma conversa real, em linguagem natural. Complementa a [verificação por cliente programático](2026-10-25-verificacao-v0-2.md).

## Método

- **Versão:** `develop` @ `a5377b1` (`job_search_mcp.__version__ = "0.2.0"`), instalação editável no checkout principal.
- **Ambiente:** Windows 11, Claude Code, `claude mcp add` com o executável do ambiente virtual e `JOB_SEARCH_DB` apontando para um banco novo preenchido com `job-search-mcp --seed`. `/mcp` mostrou o servidor conectado.
- **Data de referência declarada:** 2026-03-16. Sem arquivo de configuração local.
- **Ordem:** os pedidos abaixo, na mesma conversa e no mesmo banco.

## Resultados

| # | Pedido (resumido) | Ferramentas chamadas | Resultado observado | Confere |
|---|---|---|---|---|
| 1 | "Considere hoje 16/03/2026. Como está meu funil?" | `daily_summary`, `jobs_funnel_metrics` | 11 ativas (7 em andamento, 1 com indicação; 4 na fila), 3 em entrevista, taxa de entrevista 60% (6 de 10), semanas 1, 2, 1 e 0 (atual parcial), 2+2 vencidos e 3+2 a vencer, sem metas | sim |
| 2 | "Quem eu conheço no Banco Aurora?" | `list_contacts` (antes, também `network_company_overview`) | Ana Exemplo, ex-colega, aguardando resposta sobre a indicação, follow-up vencido em 14/03 | sim (ver observação 1) |
| 3 | "Fiz hoje (16/03/2026) a entrevista técnica da vaga 4, foi bem." | `jobs_add_stage` (proposta) | O agente mostrou a proposta (etapa técnica, resultado pendente, último contato 13/03 → 16/03) e **perguntou antes de gravar** | sim |
| 4 | "Pode confirmar." | `changes_confirm` | Etapa gravada; follow-up da vaga em 23/03 | sim |
| 5 | "Marque o Diego Amostra como em espera" e, depois da proposta, "Não, cancela." | `network_save_person`, `changes_discard` | Proposta `referred` → `on_hold` descartada; contato inalterado | sim |
| 6 | "Agora sim, coloque o Diego em espera. Confirme." | `network_save_person`, `changes_confirm` | Diego em `on_hold`, sem follow-up | sim (ver observação 2) |
| 7 | Guardar a vaga com `https://vagas.example.com/x`, confirmar; repetir com `.../x/` | `add_job`, `changes_confirm`, `add_job` | Vaga criada (id 16, `suggested`); a segunda devolveu `duplicate_url` (link normalizado igual) | sim |

Em todas as escritas, nada foi gravado antes de `changes_confirm`, e o agente só confirmou quando a pessoa pediu.

## Observações

1. **Empresa (pedido 2):** o agente respondeu pela lista de contatos. Não citou o papel de indicação confirmada nem a prioridade da vaga, que `network_company_overview` traz. Os dados estão corretos, mas a resposta foi mais curta do que a ferramenta permite.
2. **Em espera (pedido 6):** o agente confirmou que o Diego ficou sem follow-up, mas não repetiu a consulta de cobrança pedida no roteiro. O retorno `follow_up: null` é equivalente.
3. **Etapa sem status (pedido 3):** o agente não mudou o status da candidatura para `tech_interview`, porque a pessoa não disse isso. Ele perguntou em vez de supor, que é o comportamento desejado depois da verificação da `v0.1.0`.
4. **Importação (caso de uso 1 da especificação):** verificada pela linha de comando na [verificação programática](2026-10-25-verificacao-v0-2.md), não nesta conversa.

## Conclusão

Os casos de uso 2 a 6 da especificação funcionam em conversa real no Claude Code. A gravação em duas etapas funcionou como desenhada: proposta mostrada, confirmação só a pedido e recusa sem efeito. O caso 1 (importação) foi verificado pela linha de comando. Continuam não verificados: Claude Desktop e macOS.
