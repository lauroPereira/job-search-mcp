# Tarefa: Configuração local

## Objetivo

Ler os parâmetros pessoais (dias de follow-up, prazo-âncora, metas, expiração de propostas) de um arquivo TOML local, com padrões genéricos quando ele não existir.

## Especificação relacionada

`docs/specs/fonte-unica-v0-2-plano.md` (decisões técnicas e etapa 1); decisão `docs/architecture/decisions/0008-parametros-em-configuracao-local.md`.

## Pré-condições

- `develop` com a especificação e o plano da `v0.2.0` integrados.

## Arquivos prováveis

- `src/job_search_mcp/config.py` (novo)
- `src/job_search_mcp/domain.py`, `src/job_search_mcp/summary.py`, `src/job_search_mcp/server.py`
- `config.example.toml` (novo), `.gitignore`
- `tests/test_config.py` (novo)

## Passos

1. Criar `config.py` com uma função que lê o arquivo de `JOB_SEARCH_CONFIG` por `tomllib` e devolve um objeto imutável com: `follow_up.job_days` (7), `follow_up.contact_days` (6), `goals.deadline` (nenhum), `goals.applications_per_week` (nenhuma), `goals.interview_rate` (nenhuma), `proposals.ttl_hours` (24).
2. Arquivo ausente: padrões. Arquivo inválido ou chave com tipo errado: erro claro na inicialização do servidor, sem traceback.
3. Trocar as constantes de dias de follow-up do domínio por valores recebidos da configuração (o domínio continua sem ler arquivo: recebe os valores como parâmetro).
4. `daily_summary` usa `goals.deadline` quando `deadline` não for informado.
5. Criar `config.example.toml` com valores fictícios e comentários; ignorar `config.toml` no `.gitignore`.
6. Testes: sem arquivo, com o exemplo, com arquivo inválido, e follow-up recalculado com dias diferentes.

## Critérios de conclusão

- [ ] O servidor funciona sem arquivo de configuração, com os mesmos resultados da `v0.1.0`.
- [ ] Com `job_days = 10`, o follow-up de vaga muda de acordo.
- [ ] Nenhum valor pessoal no repositório; `config.toml` ignorado.
- [ ] `python tools/scripts/lint_and_tests.py --strict` sem falhas.

## Validação

Pendente.

## Status

```text
pendente
```
