# Tarefa: Banco SQLite e dados sintéticos

## Objetivo

Criar o esquema do banco, a conexão e a carga de dados de demonstração sintéticos.

## Especificação relacionada

`docs/specs/servidor-mcp-busca-de-emprego-plano.md` (etapa 2, seção "Modelo de dados").

## Pré-condições

- Tarefa 01 concluída.

## Arquivos prováveis

- `src/job_search_mcp/db.py`
- `data/seed/jobs.csv`, `data/seed/contacts.csv`
- `tests/conftest.py`, `tests/test_db.py`

## Passos

1. Em `db.py`, criar `connect(path)` que abre o SQLite com chaves estrangeiras ligadas e linhas acessíveis por nome.
2. Criar `create_schema(connection)` com as tabelas `job`, `contact`, `interaction` e `job_history` do plano, incluindo a restrição de unicidade em `job.url`.
3. Resolver o caminho padrão do banco pela variável `JOB_SEARCH_DB`, com padrão `data/local/job_search.db`.
4. Escrever `data/seed/jobs.csv` (cerca de 12 vagas) e `data/seed/contacts.csv` (cerca de 8 contatos) com dados fictícios: empresas inventadas (por exemplo, "Banco Aurora" e "Loja Horizonte") e nomes genéricos. Cobrir todos os status e datas que gerem itens vencidos, a vencer e em dia para uma data de referência fixa.
5. Criar `load_seed(connection)` que lê os CSV e insere os registros.
6. Em `tests/conftest.py`, criar uma fixture com banco em diretório temporário, esquema criado e seed carregado, e outra com a data de referência fixa.
7. Testar: esquema criado, seed carregado com as contagens esperadas e link duplicado rejeitado pelo banco.

## Critérios de conclusão

- [ ] O banco é criado do zero por `create_schema` sem erro.
- [ ] A carga do seed resulta nas contagens documentadas no teste.
- [ ] Inserir um link repetido levanta erro de integridade.
- [ ] Nenhum arquivo de banco aparece em `git status` depois dos testes.
- [ ] Os CSV não contêm nomes de pessoas ou de empresas reais.

## Validação

A preencher na execução.

## Status

```text
pendente
```
