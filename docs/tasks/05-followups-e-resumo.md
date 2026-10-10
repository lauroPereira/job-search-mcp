# Tarefa: Follow-ups pendentes e resumo do dia

## Objetivo

Implementar as consultas que respondem "o que pede atenção" e "o que fazer hoje".

## Especificação relacionada

`docs/specs/servidor-mcp-busca-de-emprego.md` (casos de uso "Resumo da manhã" e "Cobrança pendente") e o plano.

## Pré-condições

- Tarefa 04 concluída.

## Arquivos prováveis

- `src/job_search_mcp/resumo.py`
- `tests/test_resumo.py`

## Passos

1. Implementar `followups_pendentes(conexao, data_referencia, dias_a_vencer=2)`, devolvendo vagas e contatos com situação vencido ou a_vencer, ordenados por data de follow-up.
2. Excluir vagas e contatos em status que não geram follow-up.
3. Implementar `resumo_do_dia(conexao, data_referencia, prazo=None)`: contagem de vagas por status, contagem de contatos ativos, itens vencidos, itens a vencer, fila de candidatura (sugerida e a_candidatar) ordenada por nota decrescente e, se houver prazo, os dias restantes.
4. Testar com o seed e a data fixa, conferindo números e ordem.

## Critérios de conclusão

- [ ] Vaga encerrada não aparece em `followups_pendentes`.
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
