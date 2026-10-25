# 0004. Fase 2 com Streamlit, LangGraph e modelos da OpenAI

## Título

Construir a fase 2 como uma aplicação Streamlit (dashboards e chat) com agentes em LangGraph e LangChain, base vetorial local e modelos da API da OpenAI.

## Status

```text
aceita
```

Aceita pelo autor em 2026-10-25. Complementa a [decisão 0002](0002-agente-langgraph-como-cliente.md), que já previa o agente em LangGraph como cliente do servidor MCP e uma tela de leitura em Streamlit.

## Contexto

A fase 2 ([especificação](../../specs/assistente-de-carreira.md)) precisa de uma interface com dashboards e chat, de agentes que consomem o servidor MCP com aprovação humana, de busca semântica sobre documentos da busca de emprego e de um provedor de modelo. O autor tem créditos na API da OpenAI e quer exercitar LangChain e LangGraph, citados com frequência pelos times de IA.

## Decisão

- **Interface:** Streamlit, com dashboards só de leitura e um chat. Toda gravação passa pelo chat, pelo agente e pelo servidor MCP.
- **Agentes:** LangGraph para o grafo (supervisor, especialistas e pausa para aprovação humana); LangChain para a integração com o modelo, a busca semântica e o adaptador de MCP.
- **Modelos:** API da OpenAI, isolada atrás de uma interface do projeto. Modelo menor para roteamento e classificação; modelo maior só onde a qualidade exigir (redação, síntese). Os nomes dos modelos são escolhidos no plano, conferindo catálogo e preços do momento.
- **Base vetorial:** local, em arquivo dentro de `data/local/`, sem serviço externo. A biblioteca é escolhida no plano.
- **Servidor MCP:** continua sem LangChain e sem chamar modelo (decisões 0001 e 0002).

## Alternativas consideradas

- **API da Anthropic (Claude).** Adiada: o autor já tem créditos na OpenAI. A interface do projeto em volta do provedor mantém a troca possível.
- **Modelo local (Ollama ou similar).** Descartada para a v1: qualidade menor na escolha de ferramentas e mais configuração na máquina. Pode voltar para embeddings (questão Q2 da especificação).
- **Interface web própria (React ou similar).** Descartada: mais código sem ganho para o objetivo, que é demonstrar agentes, RAG, avaliação e observabilidade.
- **Base vetorial gerenciada (serviço na nuvem).** Descartada: dados pessoais sairiam da máquina e haveria custo fixo sem necessidade.

## Consequências

- O projeto passa a ter dois pacotes: o servidor MCP (sem modelo) e a aplicação (agentes e interface), com dependências separadas.
- O uso real tem custo por chamada e envia ao provedor os textos necessários para cada resposta; limites de tokens e mascaramento de dados pessoais são obrigatórios.
- Os testes e a avaliação no CI usam modelo simulado, sem chave de API.
- LangChain, LangGraph, o adaptador de MCP e o Streamlit mudam com frequência; as versões devem ser fixadas e conferidas na documentação oficial antes de cada tarefa.

## Data

2026-10-25
