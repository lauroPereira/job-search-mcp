# 0006. Gravação em duas etapas no servidor

## Título

Toda ferramenta de escrita devolve primeiro uma proposta de alteração, e só grava quando a proposta é confirmada.

## Status

```text
aceita
```

Aceita pelo autor em 2026-10-25 (discovery do [modelo de domínios](../../specs/modelo-de-dominios.md), D5 e A2).

## Contexto

Na verificação manual da `v0.1.0` ([evidência](../../evidence/2026-10-25-verificacao-manual-claude-code.md)), o agente escolheu sozinho um status e gravou antes de avisar. No uso real, status e datas foram registrados por suposição nas três sessões de follow-up. A aprovação humana dependia da disciplina de cada cliente.

## Decisão

- Ferramentas de escrita gravam só com confirmação explícita. Sem ela, devolvem a proposta: o registro afetado, cada campo com valor atual e valor proposto, e um identificador da proposta.
- A confirmação aplica exatamente a proposta registrada; se o registro mudou desde a proposta, a confirmação é recusada e uma nova proposta é necessária.
- Propostas não confirmadas expiram e não alteram nada.
- A regra vale para todas as ferramentas de escrita, inclusive as da `v0.1.0`, o que muda o contrato delas (mudança aceita para a série `0.x`, registrada nas notas de versão).

## Alternativas consideradas

- **Aprovação só no cliente** (pausa do grafo no `job-search-agent`). Descartada como única barreira: não protege o uso pelo Claude Code nem por outros clientes.
- **Parâmetro `dry_run` opcional.** Descartada: o padrão continuaria sendo gravar.
- **Manter as ferramentas da `v0.1.0` gravando direto.** Descartada: deixaria uma porta sem a barreira.

## Consequências

- A aprovação humana passa a ser propriedade do servidor, verificável em teste.
- Cada gravação custa duas chamadas; o cliente precisa mostrar a proposta à pessoa.
- Os exemplos do README e os testes das ferramentas de escrita da `v0.1.0` mudam.

## Data

2026-10-25
