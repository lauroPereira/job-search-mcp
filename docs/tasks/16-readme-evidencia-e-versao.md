# Tarefa: README, evidência e versão

## Objetivo

Documentar a `v0.2.0`, registrar a evidência dos seis casos de uso e preparar as notas da versão para a promoção.

## Especificação relacionada

`docs/specs/fonte-unica-v0-2.md` (critérios de aceitação) e `docs/specs/fonte-unica-v0-2-plano.md` (etapa 8).

## Pré-condições

- Tarefas 09 a 15 concluídas e integradas em `develop`.

## Arquivos prováveis

- `README.md`
- `docs/evidence/<data>-verificacao-v0-2.md` (novo)
- `docs/case.md` (só se algo do case mudar de fato)

## Passos

1. README:
   - ferramentas novas e a gravação em duas etapas, com um exemplo de proposta e confirmação;
   - configuração local;
   - importação e exportação;
   - migração automática com cópia de segurança;
   - exemplos de conversa atualizados;
   - roteiro.
2. Evidência dos seis casos de uso:
   - por cliente MCP programático, sobre o seed;
   - em conversa real no Claude Code, feita pelo responsável humano.
   
   Registrar o nível de cada verificação.
3. Busca nos arquivos versionados por dado real (e-mails, telefones, valores, nomes reais).
4. Rascunho das notas da `v0.2.0`. Destacar a mudança incompatível: as ferramentas de escrita passam a devolver proposta.
5. Preparar o pull request `develop` → `main` e parar: a promoção e a tag dependem do responsável humano.

## Critérios de conclusão

- [ ] Todos os critérios de aceitação de `docs/specs/fonte-unica-v0-2.md` marcados, com evidência.
- [ ] README coerente com as 17 ferramentas e com a linha de comando.
- [ ] Notas da versão com a mudança de contrato.
- [ ] `python tools/scripts/lint_and_tests.py --strict` sem falhas.

## Validação

Pendente.

## Status

```text
pendente
```
