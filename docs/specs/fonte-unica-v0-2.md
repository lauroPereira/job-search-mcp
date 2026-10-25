# Especificação: fonte única (v0.2)

Status: **aceita para planejamento** em 2026-10-25 (decisão D2 do [modelo de domínios](modelo-de-dominios.md)). Plano: [`fonte-unica-v0-2-plano.md`](fonte-unica-v0-2-plano.md). Evolui o [servidor MCP](servidor-mcp-busca-de-emprego.md) da `v0.1.0`.

## Problema

O uso real mostrou que o servidor da `v0.1.0` ainda não substitui as planilhas:

- **Empresa é só texto.** Vagas e contatos repetem o nome; não há prioridade de alvo nem lista de quem eu conheço em cada empresa.
- **Vaga e candidatura são a mesma coisa.** Não há onde registrar etapas (triagem, teste, RH, técnica, gestor), datas, resultado e feedback, nem a pretensão e o currículo enviados.
- **Pessoa e vaga se ligam por um campo só.** Quem indicou, quem recruta e quem é o gestor ficam em texto livre.
- **O agente grava sem confirmação** e nem todas as alterações têm histórico.
- **Prazos e metas estão fixos no código** e não há "em espera" para quem não deve ser cobrado.
- **Os dados atuais estão em planilhas** e não há como trazê-los para o servidor.

## Usuário afetado

A pessoa candidata, que hoje mantém duas planilhas em paralelo ao servidor; e o agente cliente, que precisa de um único lugar confiável para ler e gravar.

## Resultado desejado

A pessoa importa os dados atuais uma vez e passa a usar só o servidor: empresas, pessoas, vagas, candidaturas e etapas ligadas entre si, com toda alteração proposta, confirmada e registrada com origem. As métricas do funil saem de consulta.

## Escopo

- Empresa como entidade, com prioridade A, B, C, referenciada por vagas e pessoas.
- Candidatura separada da vaga, com etapas datadas.
- Vínculo pessoa ↔ candidatura com papel.
- Status `on_hold` para vagas, candidaturas e pessoas.
- Gravação em duas etapas ([decisão 0006](../architecture/decisions/0006-gravacao-em-duas-etapas.md)).
- Histórico único com origem ([decisão 0007](../architecture/decisions/0007-historico-unico-com-origem.md)).
- Parâmetros em configuração local ([decisão 0008](../architecture/decisions/0008-parametros-em-configuracao-local.md)).
- Importação e exportação em CSV documentado ([decisão 0005](../architecture/decisions/0005-banco-como-fonte-unica.md)).
- Métricas do funil por consulta.
- Migração automática de um banco da `v0.1.0`.
- Dados sintéticos novos para empresas, candidaturas, etapas e vínculos.

## Fora do escopo

- Perfil, requisitos de vaga, aderência e remuneração (`v0.3.0`).
- Desenvolvimento e Conteúdo (`v0.4.0` e depois).
- Converter as planilhas pessoais para o CSV de importação (feito localmente, fora do repositório).
- Qualquer chamada a modelo de linguagem, envio de mensagens ou acesso à rede.

## Requisitos funcionais

### Empresas e pessoas
- O sistema deve cadastrar, alterar e listar empresas com nome, setor, prioridade (A, B, C), plataforma de vagas e notas.
- A prioridade A deve ser sugerida quando a empresa tem pessoa ativa ou candidatura ativa; a decisão final é da pessoa.
- Vagas e pessoas devem apontar para uma empresa; o texto de empresa da `v0.1.0` é migrado para empresas, unindo nomes iguais.

### Vagas e candidaturas
- Uma vaga deve ter no máximo uma candidatura ativa; a candidatura guarda data, trilha do currículo enviado, pretensão enviada e regime, status e próximo passo.
- O sistema deve registrar etapas da candidatura com tipo (triagem, teste, fit cultural, RH, técnica, gestor, proposta), data, resultado e feedback.
- O sistema deve ligar pessoas a candidaturas com papel (indicou, recrutador, gestor, contato responsável) e indicar se o vínculo foi confirmado.
- `on_hold` deve suspender o follow-up sem encerrar o registro.
- A prioridade de vaga deve ser derivada da nota e da existência de indicação, com a regra documentada.

### Gravação e histórico
- Toda ferramenta de escrita deve devolver uma proposta (registro, campos, valor atual, valor proposto, identificador) e só gravar com confirmação; inclui as ferramentas de escrita da `v0.1.0`.
- A confirmação deve ser recusada se o registro mudou desde a proposta.
- Propostas não confirmadas devem expirar sem efeito.
- Toda alteração deve gerar histórico com valor anterior, valor novo, data e origem (tipo e referência); escrita sem origem deve ser recusada.
- O histórico de vagas da `v0.1.0` deve ser migrado.

### Parâmetros
- Dias de follow-up por domínio, prazo-âncora e metas devem vir de um arquivo de configuração local, com padrões genéricos quando ele não existir.

### Importação, exportação e métricas
- O sistema deve importar CSV de empresas, pessoas, vagas, candidaturas e interações em formato documentado, mostrar o que seria importado antes de gravar e ignorar duplicatas (link da vaga; pessoa e empresa).
- O sistema deve exportar os mesmos CSV.
- O sistema deve devolver as métricas do funil: candidaturas ativas por status, em entrevista, taxa de entrevista, candidaturas por semana, com indicação e sem indicação, follow-ups vencidos e a vencer, dias até o prazo-âncora.

## Requisitos não funcionais

- **Privacidade:** repositório público, só dados sintéticos; banco, configuração e CSV reais ficam fora do Git.
- **Compatibilidade:** um banco da `v0.1.0` abre na `v0.2.0` sem perda; as ferramentas de leitura da `v0.1.0` mantêm o contrato; as de escrita mudam só pela gravação em duas etapas, registrada nas notas de versão.
- **Custo:** nenhuma chamada a modelo de linguagem.

## Casos de uso

1. **Importar o controle atual** — a pessoa roda a importação dos CSV convertidos localmente: vê o relatório (quantos registros novos, duplicados, com erro), confirma e passa a usar o servidor.
2. **Registrar uma etapa** — "fiz a entrevista técnica hoje, foi bem, aguardo retorno": o agente propõe a etapa e o novo status da candidatura; a pessoa confirma; grava com origem "conversa".
3. **Recusa da proposta** — o agente propõe `referred` para um contato; a pessoa recusa; nada muda no banco.
4. **Quem eu conheço na empresa** — o agente lista a empresa com as pessoas ligadas e as candidaturas ativas.
5. **Em espera** — a pessoa pede para não cobrar um contato até nova ordem: status `on_hold`, fora dos follow-ups.
6. **Funil da semana** — o agente pede as métricas: candidaturas por status, taxa de entrevista, vencidos e dias até o prazo.

## Critérios de aceitação

- [ ] Os seis casos de uso funcionam com os dados sintéticos, com evidência em `docs/evidence/`. Verificação por cliente MCP programático feita ([evidência](../evidence/2026-10-25-verificacao-v0-2.md), todos os seis casos conferem); falta a verificação em conversa real no Claude Code, a cargo do responsável humano (roteiro na mesma evidência).
- [x] Teste automatizado: nenhuma ferramenta de escrita altera o banco sem confirmação. `tests/test_proposals.py::test_a_proposal_changes_nothing_and_its_confirmation_applies_it` e `tests/test_server.py::test_write_tools_only_propose_and_changes_confirm_applies` (retrato do banco para as sete ferramentas de escrita); também na evidência, casos 2, 3 e 5.
- [x] Teste automatizado: confirmação de proposta desatualizada é recusada. `tests/test_proposals.py` (`test_a_proposal_on_a_record_changed_since_then_is_stale` e seguintes) e `tests/test_server.py::test_changes_confirm_refuses_stale_expired_and_unknown_proposals`; também na evidência (extra do caso 2).
- [x] Teste automatizado: toda escrita gera histórico com origem; escrita sem origem é recusada. `tests/test_proposals.py` (confirmação com histórico e `source_type`; `test_validation_errors_come_back_at_once_without_a_proposal`), `tests/test_history.py` e `tests/test_server.py::test_add_job_refuses_an_empty_source_and_records_the_given_one`.
- [x] Teste automatizado: um banco da `v0.1.0` com o seed atual migra sem perda, com empresas unidas por nome. `tests/test_migration.py` (15 testes, com o seed da `v0.1.0` em `tests/fixtures/seed_v1/`); também na evidência, seção "Banco da v0.1.0 migrado".
- [x] Teste automatizado: importar o mesmo CSV duas vezes não duplica registros. `tests/test_transfer.py::test_second_import_finds_only_duplicates` e `test_import_command_with_apply_writes_and_a_second_run_finds_duplicates`; também na evidência, caso 1.
- [x] As métricas do funil batem com contagem feita à mão sobre os dados sintéticos. `tests/test_summary.py::test_funnel_metrics_match_the_hand_count_over_the_seed` (contagem anotada no teste); também na evidência, caso 6.
- [x] O servidor funciona sem arquivo de configuração, com os padrões genéricos. `tests/test_config.py` (`test_without_the_variable_the_defaults_apply`, `test_a_missing_file_gives_the_defaults`) e a suíte inteira, que roda sem `JOB_SEARCH_CONFIG`; a evidência também rodou sem configuração, exceto uma chamada do caso 6.
- [x] Busca nos arquivos versionados não encontra dado real. Busca da tarefa 16, registrada em `docs/tasks/16-readme-evidencia-e-versao.md` (Validação).

## Riscos

- **Mudança de contrato das ferramentas de escrita** quebra clientes que gravam direto. Mitigação: notas de versão, exemplos no README e a série `0.x`.
- **Migração do esquema** com perda ou duplicação de empresas por grafia diferente. Mitigação: união por nome normalizado e relatório da migração.
- **Conversão das planilhas pessoais** com colunas em texto livre (contato, indicação). Mitigação: o CSV aceita esses campos vazios; vínculos são criados depois, pelo agente, com confirmação.
- **Escopo:** a fatia já é a maior das três; o que não serve à troca das planilhas fica para a `v0.3.0`.

## Questões em aberto

- **Q1.** Tempo de expiração das propostas não confirmadas. Proposta no plano.
- **Q2.** Formato do arquivo de configuração local (por exemplo, TOML). Proposta no plano.
