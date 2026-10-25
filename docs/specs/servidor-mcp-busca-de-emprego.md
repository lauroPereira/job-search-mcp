# Especificação: Servidor MCP para gestão de busca de emprego

## Problema

Quem está em busca de emprego e usa um agente de IA para acompanhar o processo mantém o controle em planilhas e anotações. O agente não tem acesso estruturado a esse estado: a cada conversa precisa reler arquivos inteiros, recalcular prazos e inferir o que mudou. Isso é lento, gasta contexto e produz respostas inconsistentes entre uma conversa e outra (follow-up calculado de formas diferentes, status desatualizado, contato esquecido).

## Usuário afetado

A pessoa candidata, no momento em que pergunta ao agente "o que eu preciso fazer hoje?", registra uma conversa com um contato ou atualiza o andamento de uma candidatura.

## Resultado desejado

O agente consulta e atualiza o estado da busca por ferramentas MCP com contrato definido. A mesma pergunta devolve a mesma resposta em qualquer conversa, e toda alteração fica registrada com data e origem.

## Escopo

- Cadastro e consulta de vagas, com status, trilha, nota de aderência, próximo passo e datas.
- Cadastro e consulta de contatos de networking, com vínculo opcional a vagas.
- Registro de interações com contatos e de mudanças de status das vagas, com histórico.
- Cálculo de follow-up por regra única e consulta do que está vencido ou a vencer.
- Resumo do dia com números gerais, mudanças recentes e itens que pedem atenção.
- Dados de demonstração sintéticos para testes e para quem quiser experimentar.

## Fora do escopo

- Buscar vagas na internet ou em portais.
- Enviar mensagens, e-mails ou candidaturas em nome do usuário.
- Interface gráfica (prevista para uma fase posterior, só de leitura).
- Autenticação, múltiplos usuários e sincronização em nuvem.
- Importar planilhas existentes (fase posterior).

## Requisitos funcionais

- O sistema deve expor as ferramentas `list_jobs`, `add_job`, `update_job`, `list_contacts`, `log_interaction`, `pending_followups` e `daily_summary`.
- O sistema deve recusar o cadastro de uma vaga cujo link já exista e informar qual é a vaga existente.
- O sistema deve aceitar apenas status de uma lista fechada, para vagas e para contatos, e rejeitar valores fora dela com mensagem que liste os válidos.
- O sistema deve calcular o follow-up de uma vaga como a data do último contato mais 7 dias; sem contato, a data da candidatura mais 7 dias.
- O sistema deve calcular o follow-up de um contato como a data da última interação mais 6 dias.
- O sistema não deve gerar follow-up para vagas e contatos em status encerrado.
- O sistema deve registrar cada mudança de status ou de próximo passo no histórico, com data, valor anterior, valor novo e origem informada.
- O sistema deve classificar cada follow-up como vencido, a vencer em até 2 dias ou em dia, em relação à data de referência.
- O sistema deve aceitar uma data de referência opcional nas consultas de follow-up e de resumo, usando a data atual quando ela não for informada.
- O sistema deve devolver respostas estruturadas (objetos e listas), e não texto livre, para que o agente decida como apresentar.

## Requisitos não funcionais

- **Privacidade:** nenhum dado real é versionado; o banco do usuário fica em caminho local configurável e fora do repositório.
- **Portabilidade:** funciona em Windows, Linux e macOS com Python 3.12, sem serviço externo.
- **Previsibilidade:** as regras de data são determinísticas e testáveis com data de referência fixa.
- **Desempenho:** consultas respondem em menos de 1 segundo com até 1.000 vagas e 1.000 contatos.
- **Segurança:** as ferramentas não executam comandos, não acessam a rede e só leem e escrevem no banco configurado.

## Casos de uso

1. **Resumo da manhã** — o usuário pergunta ao agente o que fazer hoje; o agente chama `daily_summary` e apresenta os itens vencidos, os que vencem em breve e as vagas na fila.
2. **Registrar uma conversa** — o usuário conta que falou com um contato; o agente chama `log_interaction`; o follow-up do contato é recalculado e, se houver vaga vinculada, a data do último contato da vaga é atualizada.
3. **Candidatura feita** — o usuário diz que se candidatou; o agente chama `update_job` com o novo status, a data e o próximo passo; a mudança entra no histórico.
4. **Vaga nova** — o agente recebe um link; chama `add_job`; se o link já existir, informa a duplicidade em vez de criar outra linha.
5. **Cobrança pendente** — o usuário pergunta quem ele precisa cobrar; o agente chama `pending_followups` e lista vagas e contatos por urgência.

## Critérios de aceitação

Situação em 2026-10-10 (tarefa 07). "Evidência" é `docs/evidence/2026-10-10-verificacao-dos-casos-de-uso.md`, feita por um cliente MCP programático via stdio; os testes ficam em `tests/`.

- [x] As sete ferramentas aparecem para um cliente MCP conectado por stdio, com descrição e parâmetros tipados.
  - Comprovação: `test_server.py::test_server_runs_over_stdio_as_a_subprocess`, `test_server_lists_exactly_the_seven_tools` e `test_tool_parameters_match_the_plan`; evidência, seção "Conexão".
- [x] Cadastrar duas vezes o mesmo link devolve erro de duplicidade e não cria a segunda vaga.
  - Comprovação: `test_jobs.py::test_add_job_with_duplicate_url_returns_error_and_creates_nothing` e `test_server.py::test_duplicate_url_arrives_as_a_structured_error`; evidência, caso 4.
- [x] Status inválido é rejeitado com a lista de status válidos.
  - Comprovação: `test_domain.py::test_invalid_status_error_lists_the_valid_statuses` e `test_server.py::test_invalid_status_arrives_as_a_structured_error_with_the_valid_ones`; evidência, caso 3.
- [x] Com data de referência fixa, uma vaga com último contato há 7 dias aparece como vencida e outra com 5 dias aparece como a vencer.
  - Comprovação: `test_summary.py::test_pending_followups_lists_overdue_and_due_soon_from_the_seed` (vagas 1 e 3) e `test_server.py::test_pending_followups_defaults_to_today_and_two_days_ahead`; evidência, caso 1.
- [x] Vaga em status encerrado não aparece em `pending_followups`.
  - Comprovação: `test_summary.py::test_closed_and_not_started_jobs_and_contacts_are_left_out` e `test_job_that_gets_closed_leaves_the_pending_followups`.
- [x] `log_interaction` em contato vinculado a uma vaga atualiza a data do último contato da vaga.
  - Comprovação: `test_contacts.py::test_log_interaction_updates_last_contact_of_linked_job_with_history` e `test_server.py::test_log_interaction_updates_the_contact_and_the_linked_job`; evidência, caso 2.
- [x] Toda chamada de `update_job` que muda o status gera uma linha de histórico com valor anterior e novo.
  - Comprovação: `test_jobs.py::test_update_job_status_generates_history_with_old_and_new_value` e `test_server.py::test_update_job_writes_history_dated_today`; evidência, caso 3.
- [x] `daily_summary` devolve contagem por status, itens vencidos, itens a vencer e fila de candidatura ordenada por nota.
  - Comprovação: `test_summary.py::test_daily_summary_counts_match_the_seed` e `test_application_queue_is_ordered_by_score_from_highest_to_lowest`; `test_server.py::test_daily_summary_uses_today_and_returns_the_expected_object`; evidência, caso 1.
- [x] A suíte de testes roda sem acesso à rede e sem tocar em banco fora do diretório temporário de teste.
  - Comprovação: `test_db.py::test_test_database_lives_in_temporary_directory` e `test_server.py::test_nothing_is_written_outside_the_temporary_directory`. Sem rede: a suíte foi executada com as conexões de saída e a resolução de nomes bloqueadas no processo do pytest (só o endereço local liberado) e passou sem nenhuma tentativa bloqueada; o registro está na Validação da tarefa 07. Limite: o bloqueio não alcança o subprocesso do teste por stdio, e não há teste permanente que impeça o uso de rede.
- [x] O repositório não contém dados reais de pessoas nem de processos seletivos; os dados em `data/seed/` são de demonstração.
  - Comprovação: por inspeção. Os nomes do seed são fictícios (por exemplo, "Ana Exemplo", "Banco Aurora") e os links usam `example.com`; `git status` e `git diff --staged` foram conferidos antes de cada commit, e uma busca nos arquivos versionados por e-mails, telefones, CPF, valores em reais e caminhos de máquina não encontrou nada. A confirmação final de que nada ali é real cabe ao autor.

**Pendente:** a verificação manual dos cinco casos de uso em uma conversa com um agente, no Claude Code e no Claude Desktop, prevista na estratégia de testes do plano. Os critérios acima foram comprovados por testes automatizados e por um cliente MCP programático, e não por essa conversa. Os passos estão em "Pendências para o responsável humano", na evidência.

## Riscos

- **Vazamento de dados reais no repositório público.** Impacto alto. Mitigação: `.gitignore` para bancos e planilhas, dados sintéticos e conferência antes de cada commit.
- **Contrato das ferramentas mudar depois de publicado.** Impacto médio para quem já usa. Mitigação: fechar nomes e parâmetros no plano antes de implementar.
- **Regra de follow-up divergir do que o usuário espera.** Impacto médio. Mitigação: regra única, documentada e coberta por testes com data fixa.
- **Dependência do SDK de MCP mudar de API.** Impacto baixo. Mitigação: fixar a versão e isolar o registro das ferramentas da lógica de domínio.

## Questões em aberto

Nenhuma que bloqueie o MVP. Decididas pelo autor em 2026-10-10: licença MIT; nomes de ferramentas, parâmetros, tabelas, campos e valores de status em inglês; documentação em português.
