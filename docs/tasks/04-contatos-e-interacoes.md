# Tarefa: Contatos e interações

## Objetivo

Implementar a listagem de contatos e o registro de interações, com atualização do follow-up e da vaga vinculada.

## Especificação relacionada

`docs/specs/servidor-mcp-busca-de-emprego.md` (caso de uso "Registrar uma conversa") e o plano.

## Pré-condições

- Tarefa 03 concluída.

## Arquivos prováveis

- `src/job_search_mcp/contacts.py`
- `tests/test_contacts.py`

## Passos

1. Implementar `list_contacts` com filtros de status e empresa, devolvendo também o follow-up calculado.
2. Implementar `log_interaction(contact_id, summary, date, status=None, next_step=None)`: grava a interação, atualiza a data do último contato do contato e, se informados, o status e o próximo passo.
3. Quando o contato tiver `job_id`, atualizar a data do último contato da vaga e gravar a mudança no histórico da vaga, com origem "interação com contato".
4. Devolver o contato atualizado, o novo follow-up e a vaga vinculada, quando houver.
5. Testar: interação simples, interação com vaga vinculada, contato inexistente e status inválido.

## Critérios de conclusão

- [ ] Registrar uma interação move o follow-up do contato para a data da interação mais 6 dias.
- [ ] Contato vinculado a uma vaga atualiza a data do último contato da vaga.
- [ ] Contato inexistente devolve erro estruturado.
- [ ] Contato em status closed ou to_contact não tem follow-up.

## Validação

A preencher na execução.

## Status

```text
pendente
```
