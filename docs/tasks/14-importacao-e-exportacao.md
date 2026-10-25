# Tarefa: Importação e exportação

## Objetivo

Importar e exportar CSV em formato documentado pela linha de comando, com relatório antes de gravar e sem duplicar registros, e passar o seed para o mesmo formato.

## Especificação relacionada

`docs/specs/fonte-unica-v0-2-plano.md` (decisões técnicas e etapa 6); decisão `docs/architecture/decisions/0005-banco-como-fonte-unica.md`; caso de uso 1 de `docs/specs/fonte-unica-v0-2.md`.

## Pré-condições

- Tarefa 13 concluída.

## Arquivos prováveis

- `src/job_search_mcp/transfer.py` (novo), `src/job_search_mcp/server.py`, `src/job_search_mcp/db.py`
- `docs/import-format.md` (novo)
- `data/seed/*.csv`
- `tests/test_transfer.py` (novo), `tests/test_server.py`

## Passos

1. Definir e documentar em `docs/import-format.md` os arquivos:
   - `companies.csv`, `people.csv`, `jobs.csv` (vaga e candidatura), `interactions.csv`, `stages.csv` e `links.csv`;
   - para cada arquivo: colunas, obrigatórias, valores aceitos, formato de data e chaves de deduplicação (link da vaga; nome normalizado da empresa; nome da pessoa na empresa).
2. `transfer.py`:
   - leitura e validação, com relatório por arquivo: novos, duplicados e com erro, com a linha e o motivo;
   - aplicação numa transação, com histórico `source_type = import`;
   - exportação dos mesmos arquivos.
3. Subcomandos `job-search-mcp import <pasta> [--apply]` e `job-search-mcp export <pasta>`. Sem `--apply`, nada é gravado.
4. Reescrever `data/seed/` no formato novo, com dados sintéticos de empresas (prioridades A, B e C), etapas e vínculos (indicação confirmada e não confirmada). `--seed` passa a usar o importador.
5. Testes:
   - relatório sem gravar;
   - aplicação;
   - segunda importação não duplica;
   - linha inválida aparece no relatório e não interrompe as demais;
   - exportação seguida de importação em banco novo reproduz os dados.

## Critérios de conclusão

- [x] Importar a mesma pasta duas vezes não duplica registros (teste).
- [x] Sem `--apply`, o banco não muda (teste).
- [x] O seed carrega pelo importador e os dados sintéticos cobrem empresas, etapas e vínculos.
- [x] Busca nos arquivos versionados não encontra dado real.
- [x] `python tools/scripts/lint_and_tests.py --strict` sem falhas.

## Validação

Data: 2026-10-25. Ambiente: Windows 11, Python 3.12.7, ruff 0.17.2, no `.venv` do worktree, instalado com `pip install -e ".[dev]"`. Somente dados sintéticos.

- `.venv\Scripts\python.exe tools/scripts/lint_and_tests.py --strict`: estrutura e skills válidas, `322 passed` (305 em `develop` + 17), `ruff check` sem achados (`All checks passed!`); `.venv\Scripts\python.exe -m ruff format --check src tests`: `27 files already formatted`. Nenhuma linha escrita nesta tarefa passa de 100 colunas.
- `tests/test_transfer.py` (16 novos): relatório sem `--apply` com retrato do banco igual antes e depois (todas as tabelas); aplicação dos seis arquivos com histórico `source_type = import`, `source_ref` `arquivo:linha` e data de referência, prioridade `high` pela indicação confirmada e empresa criada por citação; segunda importação só com duplicados e banco igual; linhas inválidas (obrigatório vazio, prioridade, nota, data, status, células a mais, vaga e pessoa desconhecidas) no relatório com linha e motivo, sem interromper as demais; arquivo com coluna desconhecida ou sem coluna obrigatória recusado inteiro; deduplicação dentro do mesmo arquivo (empresa, pessoa, link normalizado, etapa) e pessoa homônima em outra empresa como pessoa nova; BOM e células em branco; pasta inexistente; exportação do seed (mais uma interação) e importação em banco novo reproduzindo `list_jobs`, `list_contacts`, empresas e interações, e reimportação no mesmo banco só com duplicados; exportação recusada sem sobrescrever; CLI `import` sem e com `--apply` (e segunda vez só com duplicados), pasta inexistente com código 1 e sem criar banco, `export` e recusa na segunda vez; `--seed` pelo importador.
- `tests/test_db.py`: contagens e vínculos do seed novo (inclusive `referrer` confirmado e não confirmado); cobertura de prioridades A, B, C e nula, de resultados de etapa e de indicações; segunda carga do seed só com duplicados; seed com erro não grava nada.
- `tests/test_migration.py`: a fixture da `v0.1.0` passou a usar os CSV antigos preservados em `tests/fixtures/seed_v1/`, e o banco novo de comparação é a importação desses dados, convertidos no próprio teste para o formato novo.
- Ajustes por causa do seed novo: `test_companies.py` (filtro por prioridade B), `test_jobs.py` e `test_server.py` (id da primeira etapa criada passa a ser 10, contagens de etapa filtradas pela candidatura, empresas de prioridade A, arquivo citado na mensagem de seed ausente).
- Verificação manual pela linha de comando, com `JOB_SEARCH_DB` em diretório temporário: `job-search-mcp --seed` (código 0); `export <pasta>` (16 empresas, 8 pessoas, 15 vagas, 0 interações, 9 etapas, 8 vínculos; código 0); `export` de novo na mesma pasta (`Refused: ... already has companies.csv, ...`, código 1); `import <pasta>` no mesmo banco (tudo duplicado, `Nothing was written`, código 0); `import <pasta>` em banco novo (16, 8, 15, 0, 9 e 8 novos) e depois com `--apply` (`Applied`, código 0); `import` de pasta inexistente (`Could not import ...: Folder not found`, código 1).
- Busca por dado real nos arquivos versionados: `git grep` por e-mails, telefones e domínios de sites de vagas em `data/`, `tests/fixtures/`, `src/`, `tests/` e `docs/import-format.md` não encontrou nada; os únicos links em `data/` e `tests/fixtures/` são de `vagas.example.com`; os nomes de pessoas e empresas são os fictícios já usados ("Banco Aurora", "Ana Exemplo"...).

Decisões de desenho:

- **Formato** documentado em `docs/import-format.md`: seis arquivos opcionais, UTF-8 com ou sem BOM, vírgula, datas ISO, sem ids internos. Pessoas e vagas citam a empresa pelo nome; interações e vínculos citam a pessoa por `person` + `person_company`; etapas e vínculos citam a vaga por `job_url`. Empresa citada que não existe é criada (como em `add_job`) e listada no relatório; pessoa ou vaga citada que não existe é erro na linha.
- **Chaves de deduplicação:** empresa pelo nome normalizado (`db.normalize_name`); pessoa pelo nome normalizado + empresa; vaga pelo link normalizado (`transfer.normalize_url`: esquema e domínio em minúsculas, sem fragmento e sem `/` final; o link é gravado como veio); interação por pessoa + data + resumo; etapa por vaga + tipo + data (a regra de `duplicate_stage`); vínculo por vaga + pessoa + papel. A importação só cria: duplicado é pulado mesmo com outras colunas diferentes.
- **Relatório = aplicação.** A importação roda sempre numa transação e, sem `--apply`, é desfeita no fim (`rollback`). Assim o relatório é exatamente o que a gravação faria, inclusive a deduplicação dentro do arquivo, sem uma segunda implementação de simulação. Arquivo com coluna desconhecida ou sem coluna obrigatória é recusado inteiro (erro na linha 1); linha com erro não grava nada e não para as demais. Linhas com erro não mudam o código de saída (0); problemas do comando (pasta, banco, codificação) dão código 1 na saída de erro.
- **Histórico** com `source_type = import`, `source_ref` `arquivo:linha` e a data do dia (`server.today`). Interação não gera histórico, como no servidor; vínculo grava a linha `link` com `jobs.link_value`. A data entra como parâmetro: `transfer.py` não lê o relógio (`test_domain_modules_do_not_read_the_current_date` cobre o módulo).
- **Seed pelo importador, sem histórico.** `transfer.load_seed` importa `data/seed/` com `record_history=False`: o seed é um estado inicial de demonstração, não uma mudança da pessoa, e a `v0.1.0` também o carregava sem histórico (os testes que contam linhas de histórico continuam valendo). Se o seed tiver qualquer erro, nada é gravado (`ValueError`). `db.load_seed`, `db._read_csv` e as colunas do formato antigo saíram de `db.py`; `--seed` continua recusando banco com dados.
- **Seed novo** em `data/seed/` (`companies.csv`, `people.csv`, `jobs.csv`, `stages.csv`, `links.csv`): as mesmas 15 vagas, 8 pessoas e datas em torno de 2026-03-16, na mesma ordem (os ids continuam os mesmos); 16 empresas com setor e prioridades A (3), B (3), C (4) e sem prioridade (6); 9 etapas nas vagas 6, 7 e 13 (resultados `passed`, `pending` e `failed`); os 6 vínculos `contact` antigos, mais Ana Exemplo como `referrer` confirmada na vaga 1 (nota 8,5, já `high`) e Diego Amostra como `referrer` não confirmado na vaga 11. Sem `interactions.csv`, para preservar as contagens de interação dos testes. As vagas 3, 4 e 5, as pessoas 7 e 8 e as prioridades de Banco Aurora e Seguradora Vértice ficaram sem etapas, vínculos ou prioridade novos porque os testes as usam como ponto de partida.
- **CSV antigos** preservados em `tests/fixtures/seed_v1/` só para o teste de migração (o `.gitignore` ignora `*.csv` fora de `data/seed/`, mas os arquivos foram movidos com `git mv` e continuam versionados).
- **Exportação** escreve os seis arquivos com todas as colunas, por id, e **recusa** a pasta se qualquer um deles já existir (nada é escrito); a pasta é criada quando falta. Histórico e propostas não são exportados.
- **Linha de comando:** subcomandos `import <pasta> [--apply]` e `export <pasta>` com `argparse`; relatório na saída padrão (os subcomandos não servem MCP; o modo servidor continua só com o protocolo em stdout), com `errors="replace"` para não falhar em console sem a codificação. A pasta do `import` é conferida antes de abrir o banco, para não criar banco com pasta errada. Sem `--apply`, um banco que ainda não existe é criado vazio (só o esquema), como na primeira chamada do servidor.

Pendências: README (dados de demonstração e comandos `import`/`export`) fica para a tarefa 16, com as notas da versão; as métricas do funil sobre o seed novo são da tarefa 15.

## Status

```text
concluída
```
