# Tarefa: Follow-ups pendentes e resumo do dia

## Objetivo

Implementar as consultas que respondem "o que pede atenção" e "o que fazer hoje".

## Especificação relacionada

`docs/specs/servidor-mcp-busca-de-emprego.md` (casos de uso "Resumo da manhã" e "Cobrança pendente") e o plano.

## Pré-condições

- Tarefa 04 concluída.

## Arquivos prováveis

- `src/job_search_mcp/summary.py`
- `tests/test_summary.py`

## Passos

1. Implementar `pending_followups(connection, reference_date, days_ahead=2)`, devolvendo vagas e contatos com situação overdue ou due_soon, ordenados por data de follow-up.
2. Excluir vagas e contatos em status que não geram follow-up.
3. Implementar `daily_summary(connection, reference_date, deadline=None)`: contagem de vagas por status, contagem de contatos ativos, itens vencidos, itens a vencer, fila de candidatura (suggested e to_apply) ordenada por nota decrescente e, se houver prazo, os dias restantes.
4. Testar com o seed e a data fixa, conferindo números e ordem.

## Critérios de conclusão

- [ ] Vaga encerrada não aparece em `pending_followups`.
- [ ] Os itens vêm ordenados do follow-up mais antigo para o mais recente.
- [ ] A fila de candidatura vem ordenada por nota, da maior para a menor.
- [ ] As contagens do resumo batem com o seed para a data fixa.
- [ ] Com prazo informado, o resumo devolve os dias restantes.

## Validação

A preencher na execução.

## Status

```text
pendente
```
