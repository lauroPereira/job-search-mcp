# Especificação: Perfil e aderência (v0.3)

Status: **rascunho**, para a `v0.3.0` (decisão D2 do [modelo de domínios](modelo-de-dominios.md)). Será revisto depois da `v0.2.0`, à luz do modelo completo e da [decisão 0009](../architecture/decisions/0009-perfil-como-fonte-dos-textos.md). O cliente com agentes fica no `job-search-agent` ([decisão 0004](../architecture/decisions/0004-agente-em-repositorio-separado.md)).

## Problema

- **O currículo não é dado.** Não dá para perguntar "onde eu comprovo esta habilidade?" nem comparar o que uma vaga pede com o que eu tenho.
- **A nota de aderência é dada à mão**, sem explicação do que bate e do que falta.
- **Empresa** passa a ser entidade na `v0.2.0`; a aderência usa esse vínculo para mostrar quem eu conheço na empresa de uma vaga.

## Usuário afetado

A pessoa candidata, ao avaliar uma vaga e decidir onde investir tempo; e o agente cliente, que precisa dessas respostas como ferramentas, sem reinterpretar documentos.

## Resultado desejado

O servidor guarda o currículo estruturado, as empresas e os requisitos das vagas, e calcula a aderência de cada vaga ao currículo de forma explicável e determinística. O agente cliente consulta e altera esses dados por ferramentas MCP agrupadas por domínio.

## Escopo

- Currículo: resumo e preferências, experiências, habilidades com evidência, projetos.
- Network: empresa como entidade, pessoas ligadas a empresas.
- Vagas: requisitos por vaga e aderência calculada.
- Migração do banco da `v0.1.0` sem perda de dados.
- Dados sintéticos para os novos domínios.

## Fora do escopo

- Qualquer chamada a modelo de linguagem no servidor (continua sem custo de tokens).
- Gerar versões do currículo (tarefa do agente cliente).
- Formação, certificações e idiomas; canais como entidade; candidatura separada da vaga (próximas versões).
- Extrair requisitos de uma descrição em texto livre (tarefa do agente cliente, que envia os requisitos já estruturados).

## Requisitos funcionais

- O sistema deve expor ferramentas para consultar e alterar o currículo (`resume_*`), as empresas e pessoas (`network_*`) e os requisitos das vagas (`jobs_*`).
- O sistema deve ligar cada habilidade às experiências ou projetos que a comprovam.
- O sistema deve calcular a aderência de uma vaga com: habilidades obrigatórias e desejáveis atendidas (com a evidência), lacunas, compatibilidade de nível e de faixa salarial com as preferências, pessoas da rede na empresa e uma nota.
- O cálculo da aderência deve ser determinístico: os mesmos dados dão sempre a mesma nota e a mesma explicação.
- O sistema deve reconhecer sinônimos de habilidades (se aprovado em D5).
- Toda alteração deve ficar no histórico, com valor anterior, valor novo, data e origem.
- As sete ferramentas da `v0.1.0` devem manter o contrato.

## Requisitos não funcionais

- **Privacidade:** repositório público, só dados sintéticos; currículo real, pretensão salarial e contatos reais ficam no banco local, fora do Git.
- **Custo:** nenhuma chamada a modelo de linguagem.
- **Compatibilidade:** migração automática do banco da `v0.1.0`, testada sobre o seed atual.

## Casos de uso

1. **Aderência de uma vaga** — o agente chama a aderência da vaga 8: recebe nota, habilidades atendidas com a evidência, lacunas, compatibilidade de nível e faixa e quem da rede está na empresa.
2. **Onde eu comprovo isso?** — o agente consulta a habilidade "SQL": recebe as experiências e projetos ligados.
3. **Cadastrar requisitos** — o agente envia os requisitos estruturados de uma vaga; a aderência passa a refletir esses requisitos.
4. **Empresas-alvo** — o agente lista empresas de prioridade alta com vagas abertas e pessoas conhecidas.

## Critérios de aceitação

- [ ] Os quatro casos de uso funcionam com os dados sintéticos, com evidência em `docs/evidence/`.
- [ ] A aderência é testada com casos de nota e explicação esperadas, incluindo vaga sem requisitos e currículo sem a habilidade.
- [ ] Um banco criado pela `v0.1.0` abre na `v0.2.0` sem perda de dados (teste automatizado).
- [ ] Os testes existentes das sete ferramentas da `v0.1.0` continuam passando.
- [ ] Busca nos arquivos versionados não encontra dado real.

## Riscos

- **Crescimento além do case:** mitigado pela regra de corte do discovery; o que não serve à aderência fica para depois.
- **Migração do esquema:** mitigada por migração versionada e testada.
- **Nota de aderência enganosa:** pesos arbitrários podem distorcer a prioridade. Mitigação: a nota sempre vem com a explicação, e a nota pessoal continua existindo.

## Questões em aberto

- **Q1.** Questões D1 a D7 do [modelo de domínios](modelo-de-dominios.md). Bloqueia o plano. Responsável: autor.
- **Q2.** Pesos da nota de aderência (obrigatória × desejável, nível, faixa). Proposta no plano, aprovação do autor.
