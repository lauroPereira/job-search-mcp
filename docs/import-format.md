# Formato de importação e exportação (CSV)

Este é o formato que `job-search-mcp import` lê e `job-search-mcp export` escreve. Ele é a porta de entrada dos dados que já existem (decisão [0005](architecture/decisions/0005-banco-como-fonte-unica.md)): a conversão de uma planilha pessoal para estes arquivos é feita localmente, fora do repositório. O seed de demonstração (`data/seed/`) usa o mesmo formato e o mesmo importador.

## Linha de comando

```bash
job-search-mcp import <pasta>            # só mostra o relatório; nada é gravado
job-search-mcp import <pasta> --apply    # grava as linhas novas
job-search-mcp export <pasta>            # escreve os seis arquivos na pasta
```

- O banco é o de `JOB_SEARCH_DB`, como no servidor.
- O relatório sai na saída padrão (os subcomandos não servem o protocolo MCP). Problemas que impedem o comando (pasta inexistente, banco inacessível, arquivo que não é UTF-8) saem na saída de erro, com código 1.
- Linhas com erro aparecem no relatório e **não** mudam o código de saída: o comando termina com 0 e, com `--apply`, grava as demais linhas.
- Sem `--apply`, a importação roda inteira numa transação que é desfeita no fim: o relatório é exatamente o que `--apply` faria, e os dados do banco não mudam. Se o arquivo do banco ainda não existir, ele é criado vazio, só com o esquema, como na primeira chamada do servidor.
- Com `--apply`, tudo é gravado numa transação única. Cada registro criado ganha linhas no histórico com `source_type = import` e, em `source_ref`, o arquivo e a linha de origem (por exemplo, `jobs.csv:3`).
- `export` **recusa** a pasta se qualquer um dos seis arquivos já existir nela, sem escrever nada. Use uma pasta nova ou vazia; ela é criada quando não existe.

## Regras gerais

- Codificação **UTF-8**, com ou sem BOM (o Excel grava com BOM).
- Separador **vírgula**; campos com vírgula, aspas ou quebra de linha vão entre aspas duplas, como no padrão CSV.
- A primeira linha é o cabeçalho, com os nomes das colunas abaixo. A ordem das colunas é livre e as opcionais podem faltar.
- Um arquivo com coluna desconhecida ou sem uma coluna obrigatória é recusado inteiro (aparece no relatório como erro na linha 1).
- Espaços nas pontas das células são removidos; célula vazia é valor ausente.
- Datas no formato ISO **`AAAA-MM-DD`**. `created_at` aceita também `AAAA-MM-DD HH:MM:SS`.
- Números com **ponto** decimal (`8.5`).
- **Todos os arquivos são opcionais**: a pasta pode ter só alguns. Eles são lidos nesta ordem, e um arquivo só cita registros dos anteriores ou do banco: `companies.csv`, `people.csv`, `jobs.csv`, `interactions.csv`, `stages.csv`, `links.csv`.
- A importação **só cria** registros. Uma linha duplicada (pela chave de cada arquivo) é pulada e listada como duplicada, mesmo que as outras colunas sejam diferentes; a duplicidade vale contra o banco e contra as linhas anteriores do mesmo arquivo.
- **Nome normalizado:** minúsculas, sem acentos, sem espaços nas pontas e com espaços internos repetidos reduzidos a um (`"  Clínica  BOREAL "` → `clinica boreal`).
- **Link normalizado:** sem espaços nas pontas, esquema e domínio em minúsculas, sem fragmento (`#...`) e sem `/` no fim do caminho. A consulta (`?...`) é mantida.

## Como os arquivos se referenciam

Nenhum arquivo usa os ids internos do banco:

| Quem cita | Cita o quê | Como |
|---|---|---|
| `people.csv`, `jobs.csv` | empresa | pelo nome (`company`), comparado pelo nome normalizado |
| `interactions.csv`, `links.csv` | pessoa | pelo nome (`person`) e pela empresa da pessoa (`person_company`), ambos normalizados; pessoa sem empresa: `person_company` vazio |
| `stages.csv`, `links.csv` | vaga | pelo link (`job_url`), comparado pelo link normalizado |

Uma empresa citada por `people.csv` ou `jobs.csv` que não existe é **criada** só com o nome, e o relatório lista essas empresas. Uma pessoa ou vaga citada que não existe é **erro** naquela linha.

## companies.csv — empresas

| Coluna | Obrigatória | Valores |
|---|---|---|
| `name` | sim | texto |
| `sector` | não | texto |
| `priority` | não | `A`, `B` ou `C` |
| `job_platform` | não | texto (onde a empresa publica as vagas) |
| `notes` | não | texto |

**Chave de deduplicação:** nome normalizado.

## people.csv — pessoas

| Coluna | Obrigatória | Valores |
|---|---|---|
| `name` | sim | texto |
| `company` | não | nome da empresa |
| `role_title` | não | cargo da pessoa |
| `relationship` | não | texto (ex-colega, recrutador...) |
| `channel` | não | texto (linkedin, email, whatsapp...) |
| `status` | não | `to_contact` (padrão), `awaiting_reply`, `in_conversation`, `resume_sent`, `referred`, `on_hold`, `closed` |
| `next_step` | não | texto |
| `last_contact_on` | não | data |

**Chave de deduplicação:** nome normalizado da pessoa + empresa (a mesma pessoa em empresas diferentes são duas pessoas).

## jobs.csv — vagas e candidaturas

Cada linha cria a vaga e a sua candidatura (1:1).

| Coluna | Obrigatória | Valores |
|---|---|---|
| `url` | sim | link da vaga |
| `company` | sim | nome da empresa |
| `title` | sim | texto |
| `track` | não | `data`, `systems`, `product`, `ai`, `other` |
| `score` | não | número de 0 a 10 |
| `created_at` | não | data, ou data e hora; vazio: o momento da importação |
| `status` | não | `suggested` (padrão), `to_apply`, `blocked`, `applied`, `in_review`, `hr_interview`, `tech_interview`, `manager_interview`, `offer`, `on_hold`, `hired`, `rejected`, `withdrawn`, `closed` |
| `applied_on` | não | data |
| `last_contact_on` | não | data |
| `next_step` | não | texto |
| `resume_track` | não | texto (versão do currículo enviada) |
| `salary_ask` | não | texto (pretensão enviada) |
| `contract_type` | não | texto (CLT, PJ...) |

**Chave de deduplicação:** link normalizado.

## interactions.csv — interações com pessoas

| Coluna | Obrigatória | Valores |
|---|---|---|
| `person` | sim | nome da pessoa |
| `person_company` | não | empresa da pessoa |
| `date` | sim | data |
| `summary` | sim | texto |
| `channel` | não | texto |
| `source_type` | não | `conversation`, `print`, `audio`, `email`, `meeting`, `import` (padrão), `user` |

**Chave de deduplicação:** pessoa + data + resumo.

A interação importada não altera a pessoa nem as candidaturas (o `last_contact_on` vem dos próprios arquivos). Como no servidor, a interação não gera linhas de histórico: a própria linha é o registro.

## stages.csv — etapas das candidaturas

| Coluna | Obrigatória | Valores |
|---|---|---|
| `job_url` | sim | link da vaga |
| `kind` | sim | `screening`, `test`, `culture_fit`, `hr`, `technical`, `manager`, `offer` |
| `date` | sim | data |
| `result` | não | `pending` (padrão), `passed`, `failed`, `cancelled` |
| `feedback` | não | texto |

**Chave de deduplicação:** vaga + tipo + data (a mesma regra de `jobs_add_stage`). A etapa importada não altera o status nem as datas da candidatura.

## links.csv — pessoas ligadas às candidaturas

| Coluna | Obrigatória | Valores |
|---|---|---|
| `job_url` | sim | link da vaga |
| `person` | sim | nome da pessoa |
| `person_company` | não | empresa da pessoa |
| `role` | sim | `referrer`, `recruiter`, `hiring_manager`, `contact` |
| `confirmed` | não | `true`/`false` (aceita também `1`/`0`, `yes`/`no`, `sim`/`não`); padrão `false` |

**Chave de deduplicação:** vaga + pessoa + papel. Uma indicação (`referrer`) confirmada deixa a vaga com prioridade alta.

## Exportação

`export` escreve os seis arquivos com todas as colunas acima, na ordem das tabelas acima e dos registros por id. Exportar e importar num banco novo reproduz empresas, pessoas, vagas e candidaturas, interações, etapas e vínculos. Importar a exportação no mesmo banco lista tudo como duplicado.

Limites conhecidos:

- O histórico e as propostas não são exportados; a cópia importada começa um histórico novo, com origem `import`.
- Interação sem origem gravada (vinda da `v0.1.0`) volta como `import`.
- Duas pessoas com o mesmo nome normalizado na mesma empresa viram uma só na importação.
- A exportação existe para análise e cópia de segurança, não para edição paralela (decisão 0005).

## Exemplo mínimo

`companies.csv`:

```csv
name,sector,priority
Banco Aurora,Bancos,A
```

`jobs.csv`:

```csv
url,company,title,track,score,status,applied_on
https://vagas.example.com/banco-aurora/data-engineer,Banco Aurora,Data Engineer,data,8.5,applied,2026-03-02
```

`links.csv`:

```csv
job_url,person,person_company,role,confirmed
https://vagas.example.com/banco-aurora/data-engineer,Ana Exemplo,Banco Aurora,referrer,true
```

Com só esses três arquivos, a linha de `links.csv` é um erro (a pessoa não existe): seria preciso um `people.csv` com `Ana Exemplo,Banco Aurora`.
