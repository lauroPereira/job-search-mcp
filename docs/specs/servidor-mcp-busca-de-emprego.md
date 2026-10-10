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

- O sistema deve expor as ferramentas `listar_vagas`, `registrar_vaga`, `atualizar_vaga`, `listar_contatos`, `registrar_interacao`, `followups_pendentes` e `resumo_do_dia`.
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

1. **Resumo da manhã** — o usuário pergunta ao agente o que fazer hoje; o agente chama `resumo_do_dia` e apresenta os itens vencidos, os que vencem em breve e as vagas na fila.
2. **Registrar uma conversa** — o usuário conta que falou com um contato; o agente chama `registrar_interacao`; o follow-up do contato é recalculado e, se houver vaga vinculada, a data do último contato da vaga é atualizada.
3. **Candidatura feita** — o usuário diz que se candidatou; o agente chama `atualizar_vaga` com o novo status, a data e o próximo passo; a mudança entra no histórico.
4. **Vaga nova** — o agente recebe um link; chama `registrar_vaga`; se o link já existir, informa a duplicidade em vez de criar outra linha.
5. **Cobrança pendente** — o usuário pergunta quem ele precisa cobrar; o agente chama `followups_pendentes` e lista vagas e contatos por urgência.

## Critérios de aceitação

- [ ] As sete ferramentas aparecem para um cliente MCP conectado por stdio, com descrição e parâmetros tipados.
- [ ] Cadastrar duas vezes o mesmo link devolve erro de duplicidade e não cria a segunda vaga.
- [ ] Status inválido é rejeitado com a lista de status válidos.
- [ ] Com data de referência fixa, uma vaga com último contato há 7 dias aparece como vencida e outra com 5 dias aparece como a vencer.
- [ ] Vaga em status encerrado não aparece em `followups_pendentes`.
- [ ] `registrar_interacao` em contato vinculado a uma vaga atualiza a data do último contato da vaga.
- [ ] Toda chamada de `atualizar_vaga` que muda o status gera uma linha de histórico com valor anterior e novo.
- [ ] `resumo_do_dia` devolve contagem por status, itens vencidos, itens a vencer e fila de candidatura ordenada por nota.
- [ ] A suíte de testes roda sem acesso à rede e sem tocar em banco fora do diretório temporário de teste.
- [ ] O repositório não contém nomes de pessoas, empresas em negociação nem valores reais; os dados em `data/seed/` são identificáveis como fictícios.

## Riscos

- **Vazamento de dados reais no repositório público.** Impacto alto. Mitigação: `.gitignore` para bancos e planilhas, dados sintéticos e conferência antes de cada commit.
- **Contrato das ferramentas mudar depois de publicado.** Impacto médio para quem já usa. Mitigação: fechar nomes e parâmetros no plano antes de implementar.
- **Regra de follow-up divergir do que o usuário espera.** Impacto médio. Mitigação: regra única, documentada e coberta por testes com data fixa.
- **Dependência do SDK de MCP mudar de API.** Impacto baixo. Mitigação: fixar a versão e isolar o registro das ferramentas da lógica de domínio.

## Questões em aberto

- Licença do projeto (decisão do autor; não bloqueia a implementação).
- Idioma dos nomes das ferramentas: português, como está, ou inglês para alcance maior (decisão do autor; resolver antes da tarefa 03, porque muda o contrato público).
