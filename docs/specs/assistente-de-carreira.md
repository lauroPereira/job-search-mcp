# Especificação: Assistente de carreira (fase 2)

Status: **rascunho**, aguardando o [discovery dos domínios](assistente-de-carreira-discovery.md). Sucede o MVP do [servidor MCP](servidor-mcp-busca-de-emprego.md) (`v0.1.0`) e detalha a fase 2 prevista na [decisão 0002](../architecture/decisions/0002-agente-langgraph-como-cliente.md).

## Problema

O MVP dá ao agente ferramentas para vagas e contatos, mas a gestão da recolocação continua espalhada:

- **O currículo não é dado.** Ele vive em arquivos, e por isso não dá para perguntar "onde eu comprovo esta habilidade?" nem comparar automaticamente o que uma vaga pede com o que eu tenho. A nota de aderência é dada à mão, sem explicação.
- **Empresa é só texto.** Não dá para ver o funil por empresa-alvo nem quem eu conheço na empresa de uma vaga.
- **O conhecimento acumulado não é consultável.** Descrições de vagas, notas de entrevistas, pesquisas sobre empresas e a estratégia de carreira ficam em documentos e conversas; o agente relê ou esquece.
- **Não há visão do todo.** Para saber como está o funil, é preciso perguntar ao agente, gastando tokens com algo que é uma consulta fixa.
- **O agente grava sem pedir.** Na verificação manual da `v0.1.0`, ele escolheu sozinho um status para um contato e só avisou depois ([evidência](../evidence/2026-10-25-verificacao-manual-claude-code.md)).
- **Não há medida de qualidade nem de custo** das respostas do agente: não sei quanto custa cada conversa nem se uma mudança de prompt piorou as respostas.

## Usuário afetado

A pessoa candidata (o autor, no uso diário), ao planejar o dia, registrar conversas, avaliar uma vaga, adaptar o currículo e acompanhar o funil. Secundariamente, quem avalia o projeto como portfólio e quer ver o funcionamento e as métricas.

## Resultado desejado

Uma aplicação local com **dashboards de leitura** e um **chat**. Toda criação e alteração de dados acontece pelo chat: um agente interpreta o pedido, propõe a alteração, a pessoa aprova e o agente grava pelo servidor MCP. Os dashboards refletem o banco na hora. O agente responde com base no currículo estruturado, na rede, nas vagas e numa base de conhecimento consultável, citando a fonte. Cada conversa tem custo e passos registrados, e a qualidade do agente é medida por um conjunto de avaliação versionado.

## Escopo

- Domínios **Currículo**, **Network** e **Vagas**, com a estrutura definida no discovery.
- Novas ferramentas MCP por domínio, mantendo as sete da `v0.1.0` enquanto houver uso.
- Agentes com orquestração (supervisor e especialistas) consumindo o servidor por MCP.
- Base de conhecimento com busca semântica (RAG) sobre documentos da busca de emprego.
- Interface com dashboards e chat.
- Aprovação humana antes de qualquer gravação.
- Conjunto de avaliação (agente e RAG) e execução automatizada.
- Rastreamento de cada conversa (passos, ferramentas, tokens, custo) e relatório semanal.
- Dados sintéticos de demonstração para todos os domínios.

## Fora do escopo

- Enviar mensagens, e-mails, candidaturas ou posts em nome do usuário.
- Agente editorial para LinkedIn (depois da v1).
- Buscar vagas na internet ou raspar portais.
- Uso multiusuário, autenticação e hospedagem em nuvem.
- Carga dos dados reais a partir da sessão de estratégia de carreira (acontece depois da v1, só na máquina do usuário, fora do Git).
- Exportar o currículo em PDF ou DOCX com layout final (pode entrar depois; a v1 gera o texto da versão).

## Requisitos funcionais

### Domínios e MCP
- O sistema deve manter o currículo como perfil estruturado (resumo, experiências, hard e soft skills com evidências, formação, projetos, idiomas, preferências) e gerar versões por trilha ou por vaga.
- O sistema deve manter empresas como entidade própria, referenciada por vagas e por pessoas.
- O sistema deve registrar, para cada vaga, os requisitos (nível, habilidades exigidas e desejáveis, formação, faixa salarial, modelo de trabalho, local).
- O sistema deve calcular a aderência de uma vaga ao currículo, com a lista do que é atendido, do que falta e da compatibilidade de nível e de faixa salarial.
- O sistema deve mostrar, para uma vaga, as pessoas da rede ligadas à empresa.
- Toda alteração de dados deve ficar no histórico, com valor anterior, valor novo, data e origem.

### Agentes e chat
- O chat deve aceitar pedidos em linguagem natural para consultar, criar e alterar dados dos três domínios.
- Cada agente especialista deve ter acesso apenas às ferramentas do próprio domínio e à busca no conhecimento.
- Antes de qualquer gravação, o sistema deve mostrar a alteração proposta (o quê, onde, valores) e só gravar depois da aprovação explícita; a recusa não grava nada.
- O agente não deve inventar status, datas ou valores que o usuário não informou: quando faltar dado, pergunta.

### Conhecimento (RAG)
- O sistema deve indexar documentos da busca (descrições de vagas, notas de empresas e entrevistas, currículo, estratégia) e responder com trechos recuperados, citando a fonte.
- Quando a busca não encontrar base suficiente, a resposta deve dizer isso, em vez de completar com suposição.

### Interface e relatórios
- Os dashboards devem mostrar pelo menos: funil de vagas por status, follow-ups vencidos e a vencer, empresas-alvo com vagas e contatos, aderência das vagas abertas e custo do agente no período.
- Os dashboards e o relatório semanal devem ser calculados por consulta ao banco, sem chamar modelo de linguagem.
- O chat deve mostrar, por resposta, os tokens e o custo estimado.

### Avaliação e observabilidade
- O projeto deve ter um conjunto versionado de casos de avaliação: pedido, ferramentas e argumentos esperados, resposta esperada ou critério.
- O RAG deve ter casos com o trecho que deveria ser recuperado, para medir recuperação e fidelidade à fonte.
- A avaliação deve rodar no CI sem rede e sem custo (modelo simulado) e, sob demanda, com o modelo real, registrando o resultado.
- Cada conversa deve gerar rastro com os passos do grafo, as ferramentas chamadas, os tokens e o custo.

## Requisitos não funcionais

- **Privacidade:** o repositório é público e só contém dados sintéticos. Banco, base vetorial, rastros e documentos reais ficam em `data/local/` (fora do Git). Os logs mascaram dados pessoais (e-mail, telefone).
- **Custo:** limite configurável de tokens por turno e por dia; modelo menor para roteamento e classificação, maior só onde a qualidade exigir. O custo acumulado aparece no dashboard.
- **Provedor:** API da OpenAI (créditos já disponíveis), isolada atrás de uma interface para permitir troca.
- **Execução local:** a aplicação roda na máquina do usuário com um comando; o rastreamento roda localmente.
- **Testes:** a suíte e a avaliação simulada rodam no CI sem chave de API.
- **Compatibilidade:** as sete ferramentas da `v0.1.0` continuam com o mesmo contrato enquanto existirem.

## Casos de uso

1. **Briefing do dia** — a pessoa abre a aplicação: o dashboard mostra vencidos, a vencer e o funil; no chat, "o que faço hoje?" devolve a lista priorizada, sem gravar nada.
2. **Registrar conversa com aprovação** — "falei com a Ana, a indicação foi ao RH": o agente de network propõe a interação, o novo status e o próximo passo; a pessoa aprova ou corrige; só então grava.
3. **Avaliar uma vaga** — a pessoa cola uma descrição: o agente de vagas extrai os requisitos, propõe o cadastro com a empresa, calcula a aderência ao currículo, lista lacunas e mostra quem da rede está na empresa.
4. **Adaptar o currículo** — "monte uma versão do currículo para esta vaga": o agente de currículo seleciona experiências e habilidades com evidência para os requisitos e mostra o texto proposto, sem inventar experiência.
5. **Perguntar ao conhecimento** — "o que eu anotei sobre a cultura da empresa X?": a resposta cita as notas recuperadas ou diz que não há registro.
6. **Relatório semanal** — a pessoa abre o relatório: candidaturas, respostas, conversas, follow-ups cumpridos e custo do agente na semana.

## Critérios de aceitação

- [ ] Os seis casos de uso funcionam com os dados sintéticos, com evidência registrada em `docs/evidence/`.
- [ ] Nenhuma gravação acontece sem aprovação: há teste automatizado que recusa a proposta e confirma que o banco não mudou.
- [ ] Cada agente especialista tem teste que comprova que ferramentas de outro domínio não estão disponíveis para ele.
- [ ] O conjunto de avaliação roda no CI sem chave de API e tem um resultado de referência com o modelo real registrado.
- [ ] A avaliação do RAG reporta acerto na recuperação e fidelidade à fonte, com o número registrado.
- [ ] Toda resposta do chat mostra tokens e custo, e o rastro da conversa pode ser aberto localmente.
- [ ] Dashboards e relatório semanal não chamam modelo de linguagem (verificável no rastro).
- [ ] As sete ferramentas da `v0.1.0` passam nos testes existentes.
- [ ] Busca nos arquivos versionados não encontra dado real (e-mails, telefones, valores de salário reais, nomes reais).

## Riscos

- **Escopo grande para portfólio:** multiagente, RAG, avaliação e interface juntos podem atrasar a v1. Mitigação: tarefas pequenas, cada uma entregável, com a aprovação humana e o rastreamento primeiro.
- **Dados pessoais enviados ao provedor:** currículo, contatos e notas reais passam pela API da OpenAI no uso real. Mitigação: conferir a política de retenção da API, mascarar o que não for necessário e decidir se os embeddings são locais (questão Q2).
- **Custo do modelo:** conversas longas e busca semântica gastam tokens. Mitigação: limites por turno e por dia, relatórios sem modelo, custo visível.
- **Avaliação frágil:** respostas de modelo variam. Mitigação: avaliar principalmente a escolha de ferramentas e os argumentos (determinísticos) e usar critério de texto só onde precisar.
- **Mudança de versão das bibliotecas** (LangChain, LangGraph, adaptador de MCP, Streamlit): fixar versões e conferir a documentação antes de cada tarefa.
- **Migração do banco da `v0.1.0`:** os novos domínios mudam o esquema. Mitigação: migração versionada e testada sobre o seed atual.

## Questões em aberto

- **Q1. Domínios e agentes:** as questões D1 a D9 do [discovery](assistente-de-carreira-discovery.md). Bloqueia o plano. Responsável: autor.
- **Q2. Embeddings:** gerar pela API da OpenAI (simples, envia o texto ao provedor) ou com modelo local (dados não saem da máquina, mais dependências). Responsável: autor.
- **Q3. Rastreamento:** Langfuse local exige Docker. Alternativa mais leve: gravar os rastros em SQLite e mostrá-los no próprio Streamlit. Responsável: autor.
- **Q4. Modelos:** quais modelos da OpenAI para roteamento e para redação, conferidos no catálogo e nos preços atuais no momento do plano. Responsável: plano técnico.
