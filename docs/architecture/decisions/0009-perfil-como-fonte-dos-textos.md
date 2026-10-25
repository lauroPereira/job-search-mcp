# 0009. Perfil como fonte dos textos gerados

## Título

Currículos, cartas, mensagens e posts são gerados a partir do Perfil estruturado, com autoria e evidência, e não editados à parte.

## Status

```text
aceita
```

Aceita pelo autor em 2026-10-25 (discovery do [modelo de domínios](../../specs/modelo-de-dominios.md), A5). Implementação prevista para a `v0.3.0`.

## Contexto

No uso real, datas, autoria e números de experiências saíram diferentes no currículo, no LinkedIn e nos portais, com correção em três lugares. A regra "participei" para trabalho de equipe precisou ser repetida a cada texto.

## Decisão

- O Perfil guarda os fatos de carreira: experiências, conquistas com métrica e autoria (individual ou equipe), competências com evidência, cases, formação e certificações com status.
- Textos são gerados pelo cliente a partir do Perfil; uma correção é feita uma vez, no Perfil.
- Competência sem evidência não é afirmada, e formação em andamento não aparece como concluída.

## Alternativas consideradas

- **Arquivos de currículo como fonte.** Descartada: é o cenário atual, com correções repetidas.

## Consequências

- Coerência entre currículo, cartas e mensagens passa a ser verificável.
- A geração de textos fica no agente cliente; o servidor só guarda e valida os fatos.

## Data

2026-10-25
