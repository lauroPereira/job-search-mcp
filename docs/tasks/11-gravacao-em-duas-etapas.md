# Tarefa: Gravação em duas etapas

## Objetivo

Fazer toda ferramenta de escrita devolver uma proposta e só gravar com `changes_confirm`, recusando propostas desatualizadas ou vencidas.

## Especificação relacionada

`docs/specs/fonte-unica-v0-2-plano.md` (decisões técnicas, "APIs ou interfaces" e etapa 3); decisão `docs/architecture/decisions/0006-gravacao-em-duas-etapas.md`.

## Pré-condições

- Tarefa 10 concluída.

## Arquivos prováveis

- `src/job_search_mcp/proposals.py` (novo), `src/job_search_mcp/db.py` (tabela `proposal`)
- `src/job_search_mcp/jobs.py`, `src/job_search_mcp/contacts.py`, `src/job_search_mcp/server.py`
- `tests/test_proposals.py` (novo), `tests/test_server.py`, `tests/test_jobs.py`, `tests/test_contacts.py`

## Passos

1. Separar, em `add_job`, `update_job` e `log_interaction`, o cálculo das mudanças (puro, sem gravar) da aplicação. A mesma função de cálculo serve à prévia e à confirmação.
2. Criar `proposals.py`:
   - `create`: grava argumentos, prévia, versões lidas e expiração (`proposals.ttl_hours` da configuração);
   - `confirm`: recalcula e compara versões e prévia; aplica numa transação; marca `applied`;
   - `discard`;
   - `list_pending`: marca as vencidas como `expired`.
3. Erros novos: `stale_proposal`, `expired_proposal` e `not_found` para propostas.
4. No servidor:
   - as três ferramentas de escrita passam a devolver `{"proposal": {"id", "tool", "changes", "expires_at"}}`;
   - registrar `changes_confirm`, `changes_discard` e `changes_list_pending`.
5. `source` aceita os tipos de origem do plano; texto livre continua aceito como `user`, com o texto em `source_ref`; vazio é recusado.
6. Testes:
   - para cada ferramenta de escrita, retrato do banco igual antes e depois da proposta;
   - confirmação aplica e grava histórico;
   - proposta desatualizada e proposta vencida são recusadas;
   - descarte não altera nada.

## Critérios de conclusão

- [ ] Nenhuma ferramenta de escrita altera o banco sem `changes_confirm` (teste).
- [ ] Confirmação de proposta desatualizada devolve `stale_proposal` (teste).
- [ ] Proposta vencida devolve `expired_proposal` (teste).
- [ ] Escrita sem origem é recusada (teste).
- [ ] `python tools/scripts/lint_and_tests.py --strict` sem falhas.

## Validação

Pendente.

## Status

```text
pendente
```
