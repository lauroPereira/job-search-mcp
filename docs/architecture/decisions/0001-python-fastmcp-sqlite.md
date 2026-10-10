# 0001. Python com FastMCP e SQLite

## Título

Usar Python 3.12 com o SDK oficial de MCP (FastMCP) e SQLite como armazenamento.

## Status

```text
aceita
```

Proposta e aceita pelo autor em 2026-10-10.

## Contexto

O projeto precisa expor ferramentas a clientes MCP rodando na máquina do usuário, guardar algumas centenas de vagas e contatos e funcionar sem serviço externo. O autor já mantém scripts em Python para o mesmo domínio e quer um MVP em um dia de trabalho. O repositório é público e não pode depender de infraestrutura paga.

## Decisão

O servidor é escrito em Python 3.12 com o SDK oficial de MCP para Python, usando a interface FastMCP e transporte stdio. Os dados ficam em um arquivo SQLite local, acessado pela biblioteca padrão `sqlite3`, sem ORM.

## Alternativas consideradas

- **TypeScript com o SDK de MCP.** Descartada: o autor é mais produtivo em Python e os scripts existentes do domínio estão em Python.
- **Planilha (xlsx) como armazenamento.** Descartada: sem restrição de unicidade nem transação, e o formato binário não permite revisar mudanças; foi a origem dos problemas que o projeto resolve.
- **PostgreSQL.** Descartada: exige um serviço em execução para um uso local e de um usuário só.
- **ORM (SQLAlchemy).** Descartada: quatro tabelas simples não justificam a dependência; SQL direto fica mais fácil de ler e de testar.
- **Transporte HTTP.** Descartada para o MVP: stdio basta para clientes locais e evita tratar autenticação.

## Consequências

- Instalação simples: um pacote Python e um arquivo de banco.
- A lógica fica testável sem o servidor, porque o SDK só aparece na camada de registro das ferramentas.
- Uso por vários usuários ou em nuvem exigirá outro transporte e outro banco; a separação entre domínio e servidor reduz esse custo, mas não o elimina.
- O projeto depende da estabilidade da API do SDK de MCP; a versão será fixada.

## Data

2026-10-10
