# Tarefa: Métricas do funil

## Objetivo

Expor `jobs_funnel_metrics`, com as métricas do funil calculadas por consulta.

## Especificação relacionada

`docs/specs/fonte-unica-v0-2-plano.md` ("APIs ou interfaces" e etapa 7); caso de uso 6 de `docs/specs/fonte-unica-v0-2.md`.

## Pré-condições

- Tarefa 14 concluída (seed novo com etapas).

## Arquivos prováveis

- `src/job_search_mcp/summary.py`, `src/job_search_mcp/server.py`
- `tests/test_summary.py`, `tests/test_server.py`

## Passos

1. Calcular, para uma data de referência:
   - candidaturas ativas por status (`on_hold` conta como ativa);
   - em entrevista;
   - taxa de entrevista, conforme a definição do plano;
   - candidaturas por semana nas últimas `weeks` semanas;
   - ativas com e sem indicação confirmada;
   - follow-ups vencidos e a vencer;
   - dias até `goals.deadline`;
   - metas da configuração, quando houver.
2. Registrar `jobs_funnel_metrics` como ferramenta de leitura.
3. Testes com o seed e data fixa, comparando com valores contados à mão e anotados no teste; taxa de entrevista sem candidaturas devolve nulo, sem divisão por zero.

## Critérios de conclusão

- [ ] As métricas batem com a contagem feita à mão sobre o seed (teste).
- [ ] Funciona sem configuração (sem prazo-âncora e sem metas).
- [ ] `python tools/scripts/lint_and_tests.py --strict` sem falhas.

## Validação

Pendente.

## Status

```text
pendente
```
