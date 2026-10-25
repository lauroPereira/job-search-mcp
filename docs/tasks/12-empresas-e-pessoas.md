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

- [x] Caso de uso 4 (quem eu conheço na empresa) funciona com o seed.
- [x] Caso de uso 5 (em espera) funciona e a pessoa sai dos follow-ups.
- [x] Escritas só por proposta.
- [x] `python tools/scripts/lint_and_tests.py --strict` sem falhas.

## Validação

Data: 2026-10-25. Ambiente: Windows 11, Python 3.12.7, pytest 9.1.1, no `.venv` do worktree, instalado com `pip install -e ".[dev]"`. Somente dados sintéticos (seed e nomes fictícios nos testes).

- `.venv\Scripts\python.exe tools/scripts/lint_and_tests.py --strict`: estrutura e skills válidas, `265 passed` (231 em `develop` + 34 novos), `ruff check` sem achados (`All checks passed!`); `.venv\Scripts\python.exe -m ruff format --check src tests`: `25 files already formatted`.
- `tests/test_companies.py` (16): `suggested_priority` sobre o seed (A com pessoa ativa e vaga ativa, só pessoa ativa, só candidatura ativa; null com pessoa `closed` e vaga `rejected`, e com vagas `hired`, `withdrawn`, `closed`), pessoa `on_hold` conta como ativa; filtro por prioridade gravada e prioridade inválida; visão da empresa (pessoas com follow-up, só candidaturas ativas com a vaga, `not_found`); criação com histórico e `normalized_name`; nome duplicado recusado (`duplicate_company` com a empresa existente) na criação e no renome, com variações de caixa, acento e espaços; alteração parcial (campos não informados não mudam, `version` sobe uma vez, `base_versions`); renome atualiza `normalized_name` e libera o nome antigo; erros de validação.
- `tests/test_contacts.py` (6 novos): pessoa com empresa nova gera prévia com as duas criações e, aplicada, cria empresa e pessoa com histórico; empresa resolvida pelo nome normalizado; alteração parcial (o restante do contato fica igual); troca de empresa registrada por nome no histórico; `on_hold` tira a pessoa de `pending_followups`; erros de validação.
- `tests/test_proposals.py` (5 novos): as duas ferramentas novas entram no teste parametrizado de retrato do banco igual após a proposta e confirmação que aplica com histórico; `stale_proposal` quando outra confirmação muda a empresa ou a pessoa; pessoa com empresa nova fica desatualizada se outra proposta cria a empresa antes, e criar a mesma empresa de novo dá `duplicate_company`.
- `tests/test_server.py` (7 novos, mais as listas de ferramentas, parâmetros, obrigatórios e `readOnlyHint` com as quatro novas): caso de uso 4 pelo cliente MCP (`network_list_companies` → `network_company_overview` do Banco Aurora: Ana Exemplo e a vaga Data Engineer); caso de uso 5 (`network_save_person` com `on_hold`, confirmado, sai dos follow-ups, histórico com origem `conversation`); duplicado recusado sem alterar o banco; empresa e pessoa novas criadas juntas; nenhuma gravação sem `changes_confirm` (retrato) para criar empresa, criar pessoa com empresa nova e pôr pessoa em espera.

Decisões de desenho:

- **Planejadores e propostas.** `companies.plan_save_company` e `contacts.plan_save_person` seguem o padrão da tarefa 11 (validam, devolvem `domain.Plan` ou erro estruturado) e foram registrados em `proposals.PLANNERS` como `network_save_company` e `network_save_person`. Criação não tem `base_versions` (uma empresa criada no meio-tempo muda a prévia ou faz a operação falhar, e a proposta fica `stale`); alteração depende da `version` do registro. Ao confirmar, devolvem `{"company": ...}` e `{"contact": ...}` (pessoa no formato de `list_contacts`).
- **`suggested_priority` em SQL**, na mesma consulta da empresa: `A` com pessoa de status diferente de `closed` (`on_hold` conta como ativa, conforme a regra pedida) ou candidatura fora de `domain.JOB_CLOSED_STATUSES`; senão null. A prioridade gravada é só `A`, `B`, `C` ou null (`domain.COMPANY_PRIORITIES`; outro valor é `invalid_input` com `valid_priorities`).
- **Nome único.** `duplicate_company` (novo código em `domain.error`) quando outra empresa tem o mesmo nome normalizado, na criação e no renome; renomear a própria empresa só mudando caixa ou acento é permitido. O renome atualiza `normalized_name` junto, sem linha de histórico própria (é derivado de `name`).
- **Empresa da pessoa por nome.** A prévia e o histórico registram o campo `company` da pessoa pelo nome (como `add_job` faz com a vaga). Para isso `history.record_changes` ganhou `references` e `history.REFERENCE_FIELDS` (`("contact", "company") → company_id`): compara e grava a linha pelo nome e põe o id na coluna, com um único incremento de `version`. Empresa inexistente entra na prévia como criação (`entity: company`, `record_id: null`) e é criada na confirmação com seu histórico.
- **Campos alteráveis.** `history.UPDATABLE_FIELDS` passou a incluir `company` (`name`, `sector`, `priority`, `job_platform`, `notes`) e, em `contact`, `name`, `company`, `role_title`, `relationship`, `channel`. `test_history.py` usava `name` como campo proibido de `contact`; passou a usar `job_id`.
- **Alteração parcial.** Campo `None` ou só espaços não é tocado (`domain.optional_text`); por isso esta versão não limpa campos (não há como voltar `sector` a null). `name` é obrigatório só na criação (sem `company_id`/`contact_id`); na alteração é opcional, e informar o nome atual não gera mudança (ver achado 3). Pessoa nova sem status começa em `to_contact`.
- **`jobs._changed_on` virou `jobs.parse_reference_date`**, pública, para ser reutilizada pelos planejadores novos.
- **Contrato das ferramentas existentes inalterado**; só as `instructions` do servidor e a descrição de `changes_confirm` citam as ferramentas novas.

Achados da revisão (PR 21, parecer apto, só achados baixos), tratados na mesma branch:

| # | Severidade | Achado | Decisão |
|---|---|---|---|
| 1 | Baixa | O comentário de `history.UPDATABLE_FIELDS` dizia que os campos são as colunas, mas `contact.company` é gravado em `company_id`. | Corrigido: o comentário cita `REFERENCE_FIELDS` e o mapeamento `contact.company` → `company_id`. |
| 2 | Baixa | O ramo `references` de `history.record_changes` só era testado indiretamente. | Corrigido: dois testes em `test_history.py`, um com `ValueError` sem o id (nada gravado, `version` inalterada) e outro com o nome no histórico, o id na coluna e um único incremento de `version`. |
| 3 | Baixa | `name` obrigatório na alteração obrigava a reenviar o nome para, por exemplo, pôr a pessoa em `on_hold` (caso de uso 5). | Corrigido: em `network_save_company` e `network_save_person`, `name` é obrigatório só na criação; a falta dele na criação é `invalid_input`. Os parâmetros obrigatórios das duas ferramentas passam a ser só `source`. As descrições e os testes (caso de uso 5 sem nome, alterações parciais sem nome, criação sem nome recusada) foram atualizados. São ferramentas novas, ainda não publicadas, sem impacto de contrato. |

Depois das correções: `.venv\Scripts\python.exe tools/scripts/lint_and_tests.py --strict` com `268 passed`, `All checks passed!` e `ruff format --check src tests` sem diferenças.

Pendências: limpar um campo opcional (voltar a null) não é possível pelas ferramentas novas; README e `docs/case.md` ficam para a tarefa 16, com as notas da versão.

## Status

```text
concluída
```
