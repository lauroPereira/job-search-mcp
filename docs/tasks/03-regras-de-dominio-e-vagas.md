# Tarefa: Regras de domínio e operações de vagas

## Objetivo

Implementar os status válidos, a regra de follow-up e as operações de listar, registrar e atualizar vagas, com histórico.

## Especificação relacionada

`docs/specs/servidor-mcp-busca-de-emprego.md` (requisitos de vaga, status, follow-up e histórico) e o plano.

## Pré-condições

- Tarefa 02 concluída.

## Arquivos prováveis

- `src/job_search_mcp/domain.py`
- `src/job_search_mcp/jobs.py`
- `tests/test_domain.py`, `tests/test_jobs.py`

## Passos

1. Em `domain.py`, declarar os status de vaga e de contato e os conjuntos "encerrado" e "sem follow-up" do plano.
2. Implementar `job_follow_up(applied_on, last_contact_on)` (último contato mais 7 dias; sem contato, candidatura mais 7) e `contact_follow_up(last_contact_on)` (mais 6 dias).
3. Implementar `classify(follow_up, reference_date, days_ahead=2)` devolvendo overdue, due_soon ou on_track.
4. Em `jobs.py`, implementar `list_jobs` com os filtros de status, trilha e nota mínima.
5. Implementar `add_job`, devolvendo erro estruturado de duplicidade com a vaga existente quando o link já estiver cadastrado.
6. Implementar `update_job`, validando o status e gravando uma linha em `job_history` para cada campo alterado, com valor anterior, novo e origem.
7. Escrever os testes de cada regra com a data de referência fixa.

## Critérios de conclusão

- [ ] Vaga com último contato há 7 dias é classificada como vencida; com 5 dias, como a vencer; com 2 dias, em dia.
- [ ] Vaga sem último contato usa a data da candidatura.
- [ ] Status inválido devolve erro com a lista de status válidos e não altera a vaga.
- [ ] Link duplicado devolve erro de duplicidade e não cria vaga.
- [ ] Mudar o status gera uma linha de histórico com valor anterior e novo.
- [ ] Nenhuma função lê a data atual por conta própria.

## Validação

A preencher na execução.

## Status

```text
pendente
```
