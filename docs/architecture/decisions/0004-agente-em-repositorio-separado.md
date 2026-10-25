# 0004. Agente em repositório separado

## Título

Construir o agente cliente (chat, dashboards, RAG, avaliação e observabilidade) no repositório `job-search-agent`, e não dentro deste.

## Status

```text
aceita
```

Aceita pelo autor em 2026-10-25. Substitui, na [decisão 0002](0002-agente-langgraph-como-cliente.md), só o local do agente (`src/job_search_agent/` neste repositório). O restante da 0002 continua valendo: o agente é cliente do servidor por MCP e o servidor não usa LangChain.

## Contexto

A fase 2 junta interface, agentes, busca semântica, avaliação e rastreamento. No mesmo repositório do servidor, o projeto ficaria grande demais para ser entendido e apresentado em poucos minutos, e as dependências do agente (modelo, LangChain, Streamlit) se misturariam às do servidor, que não chama modelo.

## Decisão

- Este repositório continua sendo só o servidor MCP: ferramentas, dados e regras, sem modelo de linguagem.
- O agente fica em `job-search-agent`, criado a partir do ai-dev-template, e consome o servidor por MCP a partir de uma versão publicada (tag).
- Cada repositório tem sua especificação, suas decisões e suas versões.

## Alternativas consideradas

- **Agente neste repositório (decisão 0002 original).** Descartada: mistura dependências e dificulta explicar cada parte.
- **Monorepo com dois pacotes.** Descartada: separa as dependências, mas mantém um único projeto grande para apresentar e versionar.

## Consequências

- Cada projeto é um case curto: aqui, o contrato MCP testado e sem custo de tokens; lá, o agente com aprovação humana, RAG, avaliação e custo medido.
- Mudanças de contrato do servidor precisam de versão publicada antes de o agente usá-las.
- O roteiro do README deste repositório passa a apontar para o `job-search-agent`.

## Data

2026-10-25
