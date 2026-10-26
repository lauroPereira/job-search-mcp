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

- [x] O servidor funciona sem arquivo de configuração, com os mesmos resultados da `v0.1.0`.
- [x] Com `job_days = 10`, o follow-up de vaga muda de acordo.
- [x] Nenhum valor pessoal no repositório; `config.toml` ignorado.
- [x] `python tools/scripts/lint_and_tests.py --strict` sem falhas.

## Validação

Data: 2026-10-25. Ambiente: Windows 11, Python 3.12.7 no `.venv` do worktree, instalado com `pip install -e ".[dev]"`.

- `.venv\Scripts\python.exe tools/scripts/lint_and_tests.py --strict`: estrutura e skills válidas, `178 passed`, `ruff check` sem achados (`All checks passed!`).
- `.venv\Scripts\python.exe -m pytest tests/test_config.py`: `26 passed`. Cobre: sem `JOB_SEARCH_CONFIG` e com arquivo ausente (padrões), leitura do `config.example.toml`, imutabilidade, arquivo parcial com prazo em texto ISO, catorze casos de arquivo inválido (TOML quebrado, tipo errado, valor fora da faixa, inclusive acima dos limites, chave e seção desconhecidas), limites superiores aceitos, arquivo fora de UTF-8, follow-up recalculado com `job_days = 10` e `contact_days = 9` (vaga 1 passa de 2026-03-16 para 2026-03-19 e sai das pendências), prazo-âncora no `daily_summary`, ferramentas MCP lendo o arquivo e `main()` saindo com código 1 e uma linha em stderr, sem traceback.
- Os 152 testes anteriores continuam passando sem alteração (`pytest --co --ignore=tests/test_config.py`: 152 coletados), o que confirma os mesmos resultados da `v0.1.0` sem arquivo de configuração. O `conftest.py` remove `JOB_SEARCH_CONFIG` do ambiente em todos os testes.
- `git check-ignore -v config.toml`: ignorado por `.gitignore:10`. O exemplo usa só valores fictícios (prazo 2099-12-31).

Decisões de desenho:

- `Settings` é uma dataclass imutável; `load_settings(path=None)` lê `JOB_SEARCH_CONFIG`. Sem a variável ou com o arquivo ausente, valem os padrões; não há caminho padrão implícito (o `config.toml` ignorado é só o nome sugerido).
- Seções e chaves desconhecidas são recusadas com `ConfigError`, para que um erro de digitação não seja ignorado em silêncio. Dias exigem inteiro de 1 a 365, `ttl_hours` de 1 a 720 e `applications_per_week` de 1 a 1000; `interview_rate`, número de 0 a 1; `deadline`, data TOML ou texto ISO.
- O domínio recebe os dias por parâmetro (`days`, padrão 7 e 6). `jobs`, `contacts` e `summary` recebem `settings` opcional (None: padrões). O servidor lê a configuração a cada chamada de ferramenta e `main()` a valida ao iniciar, também com `--seed`.
- O contrato das sete ferramentas não muda: mesmos parâmetros e chaves; só a descrição de `deadline` em `daily_summary` cita o padrão vindo da configuração.

Achados da revisão (PR 18), corrigidos na mesma branch:

| Severidade | Achado | Correção |
|---|---|---|
| Média | Arquivo de configuração fora de UTF-8 (por exemplo, salvo em cp1252 com acentos) fazia o `tomllib` lançar `UnicodeDecodeError`, que escapava do `ConfigError` e derrubava `main()` com traceback. | `load_settings` captura `UnicodeDecodeError` e levanta `ConfigError` pedindo UTF-8. Teste com bytes cp1252, inclusive por `main()` (código 1, sem traceback). |
| Baixa | Valores enormes (`job_days = 99999999`) passavam e geravam `OverflowError` no cálculo de data do domínio. | Limite superior: 365 para dias de follow-up, 720 para `ttl_hours` e 1000 para `applications_per_week`. Casos novos no teste parametrizado e teste dos limites aceitos. |
| Baixa | Docstring do módulo `server.py` com quebra de linha estranha. | Parágrafo reformatado. |

Depois das correções: `lint_and_tests.py --strict` com `178 passed` e `All checks passed!`.

Pendência: o `README.md` ainda não documenta `JOB_SEARCH_CONFIG`; fica para a atualização de documentação da `v0.2.0`.

## Status

```text
concluída
```
