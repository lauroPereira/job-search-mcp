# O que construí com IA: job-search-mcp

Desenvolvido por Lauro Pereira, com apoio do Claude Code na implementação, na revisão e na documentação. As decisões de escopo, arquitetura e publicação foram minhas e estão registradas no repositório.

## O problema

Durante uma recolocação, usei agentes de IA todos os dias para acompanhar vagas, contatos e follow-ups. O controle vivia em planilhas e scripts soltos. A cada conversa, o agente relia tudo para responder perguntas simples como "o que vence hoje?". Cada pergunta gastava tokens para reinterpretar os mesmos dados.

## A arquitetura · *MCP; conhecimento*

- **Servidor MCP em Python** (pacote `fastmcp` 4.1.0, transporte stdio) com **7 ferramentas**: `list_jobs`, `add_job`, `update_job`, `list_contacts`, `log_interaction`, `pending_followups` e `daily_summary`.
- **SQLite local**, pela biblioteca padrão. O conhecimento do agente passa a ser **estado estruturado consultado por ferramenta**, e não texto relido a cada conversa. Não é RAG: para este problema, uma consulta exata resolve melhor que busca semântica.
- **Cliente:** Claude Code (e qualquer cliente MCP). O servidor não tem regra de negócio. O domínio são funções puras que recebem a conexão e a data, e isso permite testá-las sem subir o servidor.
- **Decisões registradas** em ADRs (`docs/architecture/decisions/`), incluindo por que *não* usar LangChain dentro do servidor.

## Os guardrails · *guardrails e harnesses*

- **Humano no circuito:** o servidor não envia mensagem, e-mail nem candidatura (está fora do escopo da especificação). O agente sugere, e eu reviso e envio.
- **Superfície mínima:** as ferramentas não acessam a rede nem executam comandos. Só leem e gravam no banco configurado. No meu uso diário, o acesso do agente ao Gmail é somente leitura, por um conector à parte.
- **Log de alterações:** toda mudança em vaga grava uma linha de histórico com valor anterior, valor novo e origem (`source`). Cada conversa com contato vira um registro de interação.
- **Erros previsíveis:** os erros de negócio voltam como objeto (`duplicate_url`, `invalid_status`, `invalid_date`, `invalid_input`, `not_found`), para o agente explicar o que houve em vez de inventar.
- **Dados:** o repositório é público e só tem dados sintéticos.

## Como avalio · *avaliação; orquestração multiagente*

- **152 testes** (pytest) e ruff no CI do GitHub Actions a cada pull request. Dois desses testes sobem o servidor real por stdio.
- **Evidência em dois níveis:** um cliente MCP programático executou os cinco casos de uso. Depois, uma conversa real no Claude Code confirmou que o agente escolhe a ferramenta certa a partir de linguagem natural (`docs/evidence/`).
- **Fluxo com papéis:** desenvolvimento guiado por especificação (spec → plano → tarefas), com agentes em papéis separados (Supervisor, Developer, Reviewer, QA). A revisão independente é feita em contexto novo, e os achados de cada rodada ficam registrados nas tarefas.

## Custo e limites · *responsabilidade por custo; observabilidade*

- O servidor **não chama modelo nenhum**: custo zero de tokens no lado das ferramentas. A economia vem de o agente receber um resumo estruturado em vez de reler planilhas. Não medi essa redução em números.
- Observabilidade hoje é o histórico no banco e os registros de evidência. Não há tracing das chamadas do agente.
- Limites: uso local e de um usuário, Claude Desktop e Linux/macOS sem verificação manual, `track` e `score` validados só no cadastro.

## O que deu errado

- **Validação de tipos:** a documentação dizia que argumentos de tipo errado eram recusados, mas o pydantic converte `score=true` em 1.0. Corrigi a documentação para descrever o comportamento real e deixei como decisão aberta tornar o contrato estrito.
- **Agente com iniciativa demais:** na verificação manual, o agente escolheu sozinho um status para um contato e só avisou depois. O servidor fez o que lhe pediram, mas a decisão não foi minha.
- **Processo:** reescrevi o histórico de `develop` para corrigir o e-mail de autor de commits de merge. Um PR de release foi integrado antes do PR de correções e precisou de um segundo PR para completar a `v0.1.0`.

## Próximo passo

**Fase 2:** um agente em LangGraph como cliente do servidor (ADR 0002). Ele monta o briefing diário, redige os follow-ups e **para para aprovação humana antes de gravar qualquer coisa**, o que resolve o problema do agente com iniciativa demais. Terá avaliações automatizadas com modelo simulado, para rodar no CI sem rede e sem custo.

Repositório: <https://github.com/lauroPereira/job-search-mcp> · versão [`v0.1.0`](https://github.com/lauroPereira/job-search-mcp/releases/tag/v0.1.0)
