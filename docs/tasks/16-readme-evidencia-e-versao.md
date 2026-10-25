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
4. Rascunho das notas da `v0.2.0`. Destacar a mudança incompatível: as ferramentas de escrita passam a devolver proposta. Registrar também a mudança de comportamento de `log_interaction`: só candidaturas ativas ligadas à pessoa (qualquer papel) têm o último contato atualizado; vaga encerrada deixa de ser atualizada, e `job` é nulo quando a pessoa está ligada a mais de uma vaga (a lista vem em `jobs`).
5. Preparar o pull request `develop` → `main` e parar: a promoção e a tag dependem do responsável humano.

## Critérios de conclusão

- [ ] Todos os critérios de aceitação de `docs/specs/fonte-unica-v0-2.md` marcados, com evidência. Oito de nove marcados; o dos seis casos de uso aguarda a verificação manual no Claude Code.
- [x] README coerente com as 17 ferramentas e com a linha de comando.
- [x] Notas da versão com a mudança de contrato.
- [x] `python tools/scripts/lint_and_tests.py --strict` sem falhas.

## Validação

Data: 2026-10-25. Ambiente: Windows 11, Python 3.12.7. Branch `docs/16-readme-evidencia-e-versao` a partir de `develop` @ `d0af3e5` (tarefas 09 a 15). Esta tarefa não altera código.

- `.venv\Scripts\python.exe tools/scripts/lint_and_tests.py --strict`: estrutura e skills válidas, `346 passed`, `ruff check` sem achados (`All checks passed!`), "Validação estrita concluída sem falhas".
- **Evidência programática** em [`docs/evidence/2026-10-25-verificacao-v0-2.md`](../evidence/2026-10-25-verificacao-v0-2.md): ambiente virtual novo com `pip install -e .`, cliente fastmcp `Client` por stdio no executável `job-search-mcp`, bancos novos com `--seed`, data de referência 2026-03-16. Os seis casos de uso conferem; também a importação de um CSV sintético (relatório sem gravar, `--apply`, segunda importação só com duplicados, `;` com BOM aceito, linhas com erro listadas), a exportação, a proposta desatualizada e a migração de um banco da `v0.1.0` (cópia `.v1.bak`, relatório em stderr, empresas unidas, segunda abertura sem nova migração). O script foi descartável e não está versionado.
- **Divergência encontrada:** o plano diz que `update_job` ganha `resume_track`, `salary_ask` e `contract_type`, mas o servidor não os expõe; hoje só a importação grava esses campos. README e notas da versão descrevem o código; a decisão (ajustar o plano ou o servidor) fica com o Supervisor.
- **Busca por dado real** nos 144 arquivos versionados (`git grep`): e-mails (fora `noreply@anthropic.com` e `example.com`), telefones (`+55`, `(NN) NNNN-NNNN`), valores em reais (`R$`), CPF, perfis do LinkedIn, links de plataformas de vagas e caminhos de máquina (`C:\Users`, `/home/`, `AppData`): nenhuma ocorrência, exceto as citações das buscas anteriores em `docs/specs/servidor-mcp-busca-de-emprego.md` e `docs/tasks/07-readme-e-evidencia.md` e o `%APPDATA%` genérico do README. Links em `data/`, `tests/fixtures/` e `docs/import-format.md`: só `vagas.example.com`. Nomes próprios em `src/`, `tests/`, `data/` e `evals/`: só os fictícios ("Banco Aurora", "Ana Exemplo", "Empresa Exemplo"...). O nome do autor aparece só onde é autoria (`LICENSE`, `CODEOWNERS`, `docs/case.md`). A confirmação final de que nada é real cabe ao autor.
- **Documentos:** `README.md` (estado, 17 ferramentas em grupos, gravação em duas etapas, configuração local, importação e exportação, migração, exemplos com confirmação, arquitetura, limitações e roteiro), `docs/releases/v0.2.0.md` (rascunho), critérios de aceitação marcados em `docs/specs/fonte-unica-v0-2.md` com a referência de cada evidência. `docs/case.md` não mudou: descreve a `v0.1.0`, com link para a tag.

Pendências:

- Verificação manual dos seis casos no Claude Code pelo responsável humano (roteiro na evidência); depois, marcar o primeiro critério de aceitação da especificação.
- Divergência de `update_job` acima.
- A versão do pacote (`job_search_mcp.__version__`) continua `0.1.0`; atualizar para `0.2.0` antes da tag.
- `docs/case.md` descreve a `v0.1.0`; atualizar depois da promoção, se o autor quiser.
- Pull request `develop` → `main`: preparado pelo Supervisor; promoção e tag dependem do responsável humano.

## Status

```text
concluída, exceto verificação manual pelo responsável humano
```
