# Plano: Servidor MCP para gestão de busca de emprego

## Especificação relacionada

`docs/specs/servidor-mcp-busca-de-emprego.md`

## Decisões técnicas

- **Python 3.12 com o SDK oficial de MCP (FastMCP), transporte stdio.** É o caminho mais curto para expor ferramentas tipadas a clientes como Claude Code e Claude Desktop. Registrado em `docs/architecture/decisions/0001-python-fastmcp-sqlite.md`.
- **SQLite pela biblioteca padrão (`sqlite3`), sem ORM.** Um arquivo local, sem serviço, suficiente para o volume previsto. Mesma decisão 0001.
- **Lógica de domínio separada do servidor.** As regras (status válidos, follow-up, histórico, resumo) ficam em funções Python puras, que recebem a conexão e a data de referência. O módulo do servidor só registra as ferramentas e converte entrada e saída. Isso permite testar tudo sem subir o servidor.
- **Data de referência injetável.** Nenhuma regra chama a data atual por conta própria; a data entra como parâmetro, com padrão "hoje" apenas na borda (a ferramenta).
- **Caminho do banco por variável de ambiente** (`JOB_SEARCH_DB`), com padrão em `data/local/job_search.db`, que está fora do Git.
- **Erros de negócio como respostas estruturadas.** Duplicidade e status inválido devolvem um objeto com `erro` e `detalhe`, em vez de exceção sem contexto, para o agente conseguir explicar ao usuário.

## Componentes afetados

Projeto novo. Estrutura prevista:

```text
pyproject.toml
src/job_search_mcp/
  __init__.py
  db.py          conexão, criação do esquema e carga dos dados sintéticos
  dominio.py     constantes (status), regras de follow-up e classificação
  vagas.py       listar, registrar e atualizar vagas, com histórico
  contatos.py    listar contatos e registrar interações
  resumo.py      followups_pendentes e resumo_do_dia
  server.py      registro das ferramentas no FastMCP e ponto de entrada
data/seed/
  vagas.csv      dados sintéticos
  contatos.csv   dados sintéticos
tests/
  conftest.py    banco temporário e data de referência fixa
  test_dominio.py
  test_vagas.py
  test_contatos.py
  test_resumo.py
  test_server.py
```

## Modelo de dados

**vaga**

| Campo | Tipo | Observação |
|---|---|---|
| id | inteiro, chave | |
| empresa | texto, obrigatório | |
| titulo | texto, obrigatório | |
| link | texto, único | usado para evitar duplicidade |
| trilha | texto | dados, sistemas, produto, ia, outra |
| nota | real | 0 a 10 |
| status | texto, obrigatório | lista fechada, ver abaixo |
| proximo_passo | texto | |
| data_candidatura | data | |
| data_ultimo_contato | data | |
| criado_em | data e hora | |

**contato**

| Campo | Tipo | Observação |
|---|---|---|
| id | inteiro, chave | |
| nome | texto, obrigatório | |
| empresa | texto | |
| relacao | texto | |
| canal | texto | |
| status | texto, obrigatório | lista fechada, ver abaixo |
| proximo_passo | texto | |
| data_ultimo_contato | data | |
| vaga_id | inteiro, opcional | referência a vaga |

**interacao**: id, contato_id, data, resumo.

**historico_vaga**: id, vaga_id, data, campo, valor_anterior, valor_novo, origem.

**Status de vaga:** sugerida, a_candidatar, bloqueada, candidatado, em_analise, entrevista_rh, entrevista_tecnica, entrevista_gestor, proposta, aprovado, reprovado, desisti, encerrada. Encerram o follow-up: aprovado, reprovado, desisti, encerrada. Não geram follow-up: sugerida, a_candidatar, bloqueada.

**Status de contato:** a_contatar, aguardando_resposta, em_conversa, curriculo_enviado, indicado, encerrado. Não geram follow-up: a_contatar, encerrado.

Sem migrações: o esquema é criado na primeira execução.

## APIs ou interfaces

Ferramentas MCP (contrato público do projeto):

| Ferramenta | Parâmetros | Retorno |
|---|---|---|
| `listar_vagas` | `status?`, `trilha?`, `nota_minima?` | lista de vagas |
| `registrar_vaga` | `empresa`, `titulo`, `link`, `trilha?`, `nota?`, `proximo_passo?` | vaga criada, ou erro de duplicidade com a vaga existente |
| `atualizar_vaga` | `vaga_id`, `status?`, `proximo_passo?`, `data_candidatura?`, `data_ultimo_contato?`, `origem` | vaga atualizada e linhas de histórico geradas |
| `listar_contatos` | `status?`, `empresa?` | lista de contatos |
| `registrar_interacao` | `contato_id`, `resumo`, `data?`, `status?`, `proximo_passo?` | contato atualizado, follow-up novo e vaga vinculada, se houver |
| `followups_pendentes` | `data_referencia?`, `dias_a_vencer?` (padrão 2) | vagas e contatos, cada um com `follow_up` e `situacao` (vencido, a_vencer) |
| `resumo_do_dia` | `data_referencia?` | contagem por status, vencidos, a vencer, fila de candidatura por nota e dias até um prazo opcional |

Nenhuma mudança incompatível, por ser a primeira versão. Depois de publicado, renomear ferramenta ou parâmetro passa a ser mudança incompatível.

## Estratégia de testes

- **Unidade (domínio):** cálculo de follow-up de vaga e de contato, classificação por data de referência e validação de status. Cobre os critérios de follow-up e de status inválido.
- **Unidade (vagas e contatos):** duplicidade de link, histórico gerado na atualização e interação que atualiza a vaga vinculada. Banco SQLite temporário por teste.
- **Unidade (resumo):** com os dados sintéticos e data fixa, conferir contagens, vencidos, a vencer e a ordem da fila.
- **Integração (servidor):** listar as ferramentas registradas e chamar uma delas pelo cliente em memória do SDK, para confirmar nomes, parâmetros e formato de retorno.
- **Verificação manual:** conectar o servidor ao Claude Code por stdio e executar os cinco casos de uso da especificação; registrar o resultado em `docs/evidence/`.
- **Privacidade:** um teste confere que os arquivos de `data/seed/` só usam empresas e nomes de uma lista fictícia.

## Riscos técnicos

- **API do SDK de MCP diferente da esperada.** Mitigação: fixar a versão no `pyproject.toml` e consultar a documentação oficial antes da tarefa 05; a lógica não depende do SDK.
- **Datas em texto no SQLite.** Mitigação: gravar sempre em ISO 8601 (AAAA-MM-DD) e converter em um único ponto (`db.py`).
- **Banco real criado dentro do repositório por engano.** Mitigação: caminho padrão em `data/local/`, ignorado pelo Git, e teste que falha se o banco de teste não estiver em diretório temporário.
- **Reversão:** projeto novo; reverter é descartar a branch da tarefa.

## Plano de implementação

Cada etapa é uma tarefa em `docs/tasks/`, na ordem:

1. `01-estrutura-do-projeto-python.md` — `pyproject.toml`, pacote vazio, pytest e ruff rodando.
2. `02-banco-e-dados-sinteticos.md` — esquema SQLite, conexão e carga de `data/seed/`.
3. `03-regras-de-dominio-e-vagas.md` — status, follow-up, listar, registrar e atualizar vagas com histórico.
4. `04-contatos-e-interacoes.md` — listar contatos e registrar interações.
5. `05-followups-e-resumo.md` — `followups_pendentes` e `resumo_do_dia`.
6. `06-servidor-mcp.md` — registro das sete ferramentas no FastMCP e teste de integração.
7. `07-readme-e-evidencia.md` — instruções de uso, configuração no cliente e evidência da verificação manual.
