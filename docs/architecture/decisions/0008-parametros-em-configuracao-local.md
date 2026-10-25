# 0008. Regras e parâmetros em configuração local

## Título

Prazos de follow-up, prazo-âncora, metas e parâmetros salariais ficam num arquivo de configuração local, fora do Git, com padrões genéricos no código.

## Status

```text
aceita
```

Aceita pelo autor em 2026-10-25 (discovery do [modelo de domínios](../../specs/modelo-de-dominios.md), A4).

## Contexto

Os scripts do uso real tinham constantes pessoais escritas no código: prazo-limite, piso salarial, fator de pacote de uma empresa e caminhos absolutos. Prazos de follow-up diferentes (7 dias para vagas, 6 para contatos) estavam espalhados em fórmulas e scripts.

## Decisão

- Um arquivo de configuração local, indicado por variável de ambiente, com os parâmetros: dias de follow-up por domínio, prazo-âncora, metas e parâmetros salariais.
- O código traz padrões genéricos (7 e 6 dias de follow-up, nenhum parâmetro salarial) e funciona sem o arquivo.
- O repositório traz só um exemplo com valores fictícios.

## Alternativas consideradas

- **Parâmetros no banco.** Adiada: mistura configuração com dado e complica a revisão; pode ser revista se o agente precisar alterá-los.
- **Constantes no código.** Descartada: expõe valores pessoais e exige mudar código para ajustar uma regra.

## Consequências

- Valores pessoais nunca entram no repositório público.
- As regras ficam visíveis e ajustáveis num lugar só.

## Data

2026-10-25
