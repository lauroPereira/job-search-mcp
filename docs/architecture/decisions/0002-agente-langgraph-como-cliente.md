# 0002. Agente em LangGraph como cliente do servidor MCP

## Título

Construir, em uma segunda fase, um agente em LangGraph que consome o servidor MCP, em vez de usar LangChain ou LangGraph dentro do servidor.

## Status

```text
proposta
```

Proposta em 2026-10-10. Depende da confirmação do autor e da conclusão do MVP (tarefas 01 a 07).

## Contexto

O autor quer exercitar LangChain e LangGraph, que são os frameworks mais citados por quem trabalha com aplicações de IA, e aproveitar o projeto como portfólio. O servidor MCP, porém, só expõe ferramentas: ele não chama modelo de linguagem, não mantém conversa e não orquestra passos. LangChain e LangGraph resolvem exatamente esses problemas, que ficam do lado de quem usa as ferramentas (o agente), e não de quem as oferece (o servidor).

## Decisão

O servidor continua como definido na decisão 0001: Python, FastMCP e SQLite, sem LangChain. Em uma segunda fase, o repositório ganha um agente em LangGraph (pacote separado, em `src/job_search_agent/`) que se conecta ao servidor por MCP e executa um fluxo de "briefing diário":

1. coletar o estado (ferramentas `daily_summary` e `pending_followups`);
2. priorizar as ações do dia;
3. redigir as mensagens de follow-up sugeridas;
4. parar para aprovação humana antes de registrar qualquer coisa;
5. registrar as interações aprovadas (ferramenta `log_interaction`).

A conexão usa o adaptador de MCP do ecossistema LangChain, que transforma as ferramentas do servidor em ferramentas do agente. O fluxo terá avaliações automatizadas com os dados sintéticos.

## Alternativas consideradas

- **Escrever o servidor com LangChain.** Descartada: o servidor não chama modelo nem encadeia passos; o framework entraria só como dependência, sem função, e esconderia o protocolo que o projeto quer demonstrar.
- **Não usar LangGraph.** Descartada: o autor perde a oportunidade de praticar orquestração com estado e aprovação humana, que é o que os times de IA mais pedem.
- **Fazer o agente antes do servidor.** Descartada: sem ferramentas prontas e testadas o agente não tem o que orquestrar, e o MVP deixaria de caber em um dia.
- **Agente com outro framework (SDK de agentes de um provedor).** Adiada: pode virar comparação futura; LangGraph é a escolha pela demanda de mercado citada pelo autor.

## Consequências

- O projeto passa a demonstrar os dois lados: construção de ferramentas (MCP) e orquestração de agente (LangGraph), com responsabilidades separadas.
- O MVP do servidor não atrasa nem ganha dependências.
- A segunda fase exige chave de API de um modelo e traz custo por execução; os testes do agente precisam de modelo simulado para rodar sem rede.
- As versões de LangGraph e do adaptador de MCP mudam com frequência; devem ser fixadas e conferidas na documentação oficial antes de começar.

## Data

2026-10-10
