# Tarefa: Etapas e vínculos

## Objetivo

Registrar etapas datadas da candidatura e vínculos pessoa ↔ candidatura com papel, e calcular a prioridade da vaga.

## Especificação relacionada

`docs/specs/fonte-unica-v0-2-plano.md` ("APIs ou interfaces" e etapa 5); caso de uso 2 de `docs/specs/fonte-unica-v0-2.md`.

## Pré-condições

- Tarefa 12 concluída.

## Arquivos prováveis

- `src/job_search_mcp/jobs.py`, `src/job_search_mcp/contacts.py`, `src/job_search_mcp/domain.py`, `src/job_search_mcp/server.py`
- `tests/test_jobs.py`, `tests/test_contacts.py`, `tests/test_server.py`

## Passos

1. Cálculo das mudanças de `jobs_add_stage`:
   - valida tipo, resultado e data (não futura);
   - inclui o novo status da candidatura quando informado;
   - atualiza `last_contact_on` da candidatura quando a data é mais recente.
2. Cálculo das mudanças de `jobs_link_person`:
   - valida papel;
   - recusa vínculo repetido;
   - permite confirmar um vínculo existente.
3. Prioridade derivada da vaga na leitura, conforme o plano: `high`, `medium` ou `low`.
4. Leitura da vaga com `stages` (ordenadas por data) e `people` (com papel e confirmação).
5. `log_interaction` atualiza `last_contact_on` de todas as candidaturas ativas ligadas à pessoa. Na resposta:
   - `job` continua presente: é a vaga quando há uma única candidatura ligada, ou nulo;
   - `jobs` é nova e traz a lista.
6. Registrar `jobs_add_stage` e `jobs_link_person` com propostas.
7. Testes:
   - etapa com e sem status;
   - data futura recusada;
   - vínculo repetido;
   - prioridade derivada (nota e indicação confirmada);
   - interação com pessoa ligada a duas candidaturas.

## Critérios de conclusão

- [ ] Caso de uso 2 (registrar uma etapa) funciona com o seed, por proposta e confirmação.
- [ ] Caso de uso 3 (recusa da proposta) comprovado em teste.
- [ ] A saída de `log_interaction` mantém as chaves da `v0.1.0` no resultado confirmado.
- [ ] `python tools/scripts/lint_and_tests.py --strict` sem falhas.

## Validação

Pendente.

## Status

```text
pendente
```
