# 0005. Banco do servidor como fonte única

## Título

O banco SQLite do servidor é a única fonte dos dados da busca de emprego; planilhas passam a ser só importação inicial e exportação.

## Status

```text
aceita
```

Aceita pelo autor em 2026-10-25 (discovery do [modelo de domínios](../../specs/modelo-de-dominios.md), A1).

## Contexto

Em 25 dias de uso real, o controle viveu em duas planilhas e em várias sessões de agente escrevendo nos mesmos arquivos. A mesma vaga existia em dois cadastros com status e prioridades diferentes, e mudanças feitas em uma sessão precisavam ser repetidas em outra. Foi o retrabalho mais frequente do levantamento.

## Decisão

- Todo dado da busca (empresas, pessoas, vagas, candidaturas, etapas, interações) é lido e gravado só pelo servidor MCP.
- Os dados existentes entram uma vez por importação de CSV em formato documentado, idempotente (deduplicação pelo link da vaga e pelo nome da pessoa na empresa), com relatório do que seria importado antes de gravar.
- A exportação para CSV existe para análise e cópia de segurança, não para edição paralela.

## Alternativas consideradas

- **Manter as planilhas como fonte e o servidor como leitor.** Descartada: mantém a divergência e a escrita concorrente.
- **Sincronização nos dois sentidos com a planilha.** Descartada: complexa, com conflitos de edição, sem ganho para um usuário só.
- **Importador do formato exato das planilhas pessoais.** Descartada: amarraria o repositório público a um arquivo pessoal; a conversão para o CSV documentado é feita localmente.

## Consequências

- A pessoa deixa de editar planilhas; consulta e altera pelo agente.
- Um único processo grava no banco, o que elimina a escrita concorrente.
- É preciso uma conversão local, fora do repositório, das planilhas atuais para o CSV de importação.

## Data

2026-10-25
