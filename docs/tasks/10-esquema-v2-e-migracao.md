# Tarefa: Esquema versão 2 e migração

## Objetivo

Criar o esquema da `v0.2.0` (empresa, candidatura, etapas, vínculos, histórico único, `on_hold`) e migrar sem perda um banco da `v0.1.0`, mantendo o contrato das sete ferramentas.

## Especificação relacionada

`docs/specs/fonte-unica-v0-2-plano.md` (seção "Modelo de dados" e etapa 2); decisão `docs/architecture/decisions/0007-historico-unico-com-origem.md`.

## Pré-condições

- Tarefa 09 concluída.

## Arquivos prováveis

- `src/job_search_mcp/db.py`, `src/job_search_mcp/history.py` (novo)
- `src/job_search_mcp/domain.py`, `src/job_search_mcp/jobs.py`, `src/job_search_mcp/contacts.py`, `src/job_search_mcp/summary.py`
- `tests/test_migration.py` (novo), `tests/fixtures/schema_v1.sql` (novo), testes existentes

## Passos

1. Escrever o esquema versão 2 do plano, com `version` nas tabelas alteráveis, e gravar `PRAGMA user_version = 2` em banco novo.
2. Criar `history.py` com uma função única que compara valores, grava as mudanças e as linhas de `history` (entidade, registro, campo, antes, depois, data, `source_type`, `source_ref`). Vagas e contatos passam a usá-la.
3. Escrever a migração da versão 0 para a 2, aplicada ao abrir o banco:
   - copiar o arquivo do banco para `<nome>.v1.bak` antes de começar;
   - empresas criadas a partir dos textos de `job.company` e `contact.company`, unidas por nome normalizado;
   - recriar `job` (sem os campos de andamento) e criar `application` com eles;
   - recriar `contact` com `company_id` e `role_title`;
   - mover `contact.job_id` para `application_person` com papel `contact` e `confirmed` verdadeiro;
   - mover `job_history` para `history`: `source` livre vira `source_type = user`, com o texto em `source_ref`;
   - tudo numa transação.
4. Ajustar as leituras para juntar vaga, candidatura e empresa, e manter as chaves de saída da `v0.1.0` (`company` continua sendo o nome da empresa). Acrescentar `company_id`.
5. Acrescentar `on_hold` aos status de candidatura e de pessoa, sem follow-up.
6. Ajustar o seed atual para carregar no esquema novo (o formato novo do seed fica para a tarefa 14).
7. Teste de migração: fixture com o SQL da `v0.1.0` mais o seed; conferir contagens, empresas unidas, histórico e vínculos migrados, e a cópia de segurança criada.

## Critérios de conclusão

- [ ] Banco da `v0.1.0` migra sem perda e o teste de migração passa.
- [ ] As sete ferramentas devolvem as mesmas chaves da `v0.1.0`, mais as aditivas.
- [ ] `on_hold` aceito para candidatura e pessoa e fora dos follow-ups.
- [ ] Toda alteração de vaga ou pessoa grava em `history`.
- [ ] `python tools/scripts/lint_and_tests.py --strict` sem falhas.

## Validação

Pendente.

## Status

```text
pendente
```
