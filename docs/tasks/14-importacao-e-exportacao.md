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

- [ ] Importar a mesma pasta duas vezes não duplica registros (teste).
- [ ] Sem `--apply`, o banco não muda (teste).
- [ ] O seed carrega pelo importador e os dados sintéticos cobrem empresas, etapas e vínculos.
- [ ] Busca nos arquivos versionados não encontra dado real.
- [ ] `python tools/scripts/lint_and_tests.py --strict` sem falhas.

## Validação

Pendente.

## Status

```text
pendente
```
