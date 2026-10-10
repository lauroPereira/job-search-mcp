# Tarefa: Regras de domínio e operações de vagas

## Objetivo

Implementar os status válidos, a regra de follow-up e as operações de listar, registrar e atualizar vagas, com histórico.

## Especificação relacionada

`docs/specs/servidor-mcp-busca-de-emprego.md` (requisitos de vaga, status, follow-up e histórico) e o plano.

## Pré-condições

- Tarefa 02 concluída.
- Questão em aberto sobre o idioma dos nomes das ferramentas respondida pelo autor.

## Arquivos prováveis

- `src/job_search_mcp/dominio.py`
- `src/job_search_mcp/vagas.py`
- `tests/test_dominio.py`, `tests/test_vagas.py`

## Passos

1. Em `dominio.py`, declarar os status de vaga e de contato e os conjuntos "encerrado" e "sem follow-up" do plano.
2. Implementar `follow_up_vaga(data_candidatura, data_ultimo_contato)` (último contato mais 7 dias; sem contato, candidatura mais 7) e `follow_up_contato(data_ultimo_contato)` (mais 6 dias).
3. Implementar `classificar(follow_up, data_referencia, dias_a_vencer=2)` devolvendo vencido, a_vencer ou em_dia.
4. Em `vagas.py`, implementar `listar_vagas` com os filtros de status, trilha e nota mínima.
5. Implementar `registrar_vaga`, devolvendo erro estruturado de duplicidade com a vaga existente quando o link já estiver cadastrado.
6. Implementar `atualizar_vaga`, validando o status e gravando uma linha em `historico_vaga` para cada campo alterado, com valor anterior, novo e origem.
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
