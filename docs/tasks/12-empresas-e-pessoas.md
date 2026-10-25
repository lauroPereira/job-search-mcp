# Tarefa: Empresas e pessoas

## Objetivo

Expor empresas e pessoas do domínio Network: listar, ver a empresa com pessoas e candidaturas, e cadastrar ou alterar empresa e pessoa por proposta.

## Especificação relacionada

`docs/specs/fonte-unica-v0-2-plano.md` ("APIs ou interfaces" e etapa 4); casos de uso 4 e 5 de `docs/specs/fonte-unica-v0-2.md`.

## Pré-condições

- Tarefa 11 concluída.

## Arquivos prováveis

- `src/job_search_mcp/companies.py` (novo), `src/job_search_mcp/contacts.py`, `src/job_search_mcp/domain.py`, `src/job_search_mcp/server.py`
- `tests/test_companies.py` (novo), `tests/test_contacts.py`, `tests/test_server.py`

## Passos

1. `companies.py`:
   - listar empresas com filtro de prioridade e com `suggested_priority`: `A` quando há pessoa ativa ou candidatura ativa;
   - visão da empresa: dados, pessoas e candidaturas ativas;
   - cálculo das mudanças para criar ou alterar uma empresa, com nome normalizado único.
2. Em `contacts.py`, o cálculo das mudanças para criar ou alterar uma pessoa. Uma empresa informada por nome é resolvida pelo nome normalizado; se não existir, a proposta inclui criá-la.
3. Registrar `network_list_companies`, `network_company_overview`, `network_save_company` e `network_save_person`. As duas de escrita usam as propostas da tarefa 11.
4. Testes:
   - prioridade sugerida;
   - visão da empresa;
   - nome duplicado recusado;
   - pessoa com empresa nova gera proposta com as duas criações;
   - `on_hold` pela ferramenta.

## Critérios de conclusão

- [ ] Caso de uso 4 (quem eu conheço na empresa) funciona com o seed.
- [ ] Caso de uso 5 (em espera) funciona e a pessoa sai dos follow-ups.
- [ ] Escritas só por proposta.
- [ ] `python tools/scripts/lint_and_tests.py --strict` sem falhas.

## Validação

Pendente.

## Status

```text
pendente
```
