# Regras do projeto menu_interface

Este arquivo e lido automaticamente pelo Cline no inicio de **toda** conversa
neste workspace. Mantenha-o enxuto e versionado no git.

## Onde esta o que

| Assunto | Arquivo |
|---|---|
| Regras globais (valem nos 4 projetos: menu, as400, cnpj, carga) | `~/Documentos/Cline/Rules/00-sistema-arosasse.md` |
| Estado atual, pendencias, decisoes e arquitetura | `/home/neto/Projetos/docs/PROJETOS.md` |
| Comandos (dev/prod, queries, git, djLint) | `/home/neto/Projetos/docs/COMANDOS.md` |
| Historico detalhado (blocos 1-32) | `/home/neto/Projetos/docs/HISTORICO.md` |
| Briefing portatil (para outra IA) | `/home/neto/Projetos/docs/TODOS_PROJETOS.md` |

Nao repita aqui o que ja esta nas regras globais nem duplique o estado atual: se
algo mudar, atualize o `PROJETOS.md`.

## Idioma e estilo

- Responda sempre em **portugues do Brasil (pt-BR)**.
- Codigo, comentarios e docstrings: **sem acentos** (ex: `versao`, `nao`,
  `conexao`). Prosa em Markdown (.md) pode usar acentos normalmente.
- Comentarios e docstrings em PT-BR. Nao traduza nomes de tabelas/colunas da
  RFB nem nomes de projeto (`menu_interface`, `chat_pessoas`).
- Siga o estilo dos arquivos vizinhos (4 espacos, aspas simples).

## Stack e arquitetura

- Django **5.1.7** (`requirements.txt`), Python 3.13, venv **`venv`**.
- Bootstrap 5.3.2 + bootstrap-icons por **CDN** (o `menu.html` nao usa
  `extends` nem crispy). SQLite (`db.sqlite3`) **so** para o admin.
- Pacote Django: **`menu_project/`**; app unico **`core/`**.
  `menu_interface` e o repositorio/pasta, nao o pacote.
- **Nao ha banco de negocio, Postgres, Mongo nem Redis.** Cache e
  `LocMemCache` (`menu-health-cache`, `TIMEOUT=300`).
- `core/views.py` mantem a lista de projetos em Python puro (`_montar_contexto`),
  sem models e sem fixtures. 4 cards: `cnpj`, `chat_empresas`, `as400`,
  `chat_pessoas`; mais `repos_sem_card` (`menu_interface`, `ProjetoCargaDados`).
  Versao exibida: `1.2`.
- Rotas (`core/urls.py`): `''` (`core:menu`), `projeto/<str:projeto_id>/`
  (`core:detalhe_projeto`, HTTP 404 se o id nao existe), `health/` (texto `ok`)
  e `admin/`.
- Health: `_check_url` (HEAD), `_check_health_deep` (GET + JSON) e as versoes
  `_cached`; `HEALTH_TIMEOUT = 5`; cache 60s para online/lento e 10s para
  offline. O menu **consome** os `/health/deep/` dos outros tres e **nao expoe**
  um `/health/deep/` proprio (nao tem banco para testar).

## Comandos do projeto

    source venv/bin/activate
    python manage.py runserver 8000          # http://localhost:8000/
    python manage.py check
    python manage.py test core               # core/tests.py esta vazio hoje
    bash ~/Projetos/start_all.sh             # sobe 8000, 8001 e 8002
    cd ~/Projetos && ./deploy.sh menu        # producao (pedir confirmacao)

- Use sempre o Python do `venv/`. Nunca instale pacotes globalmente e nao altere
  `requirements.txt` (3 pacotes) sem pedir.

## Regras de seguranca

- Nunca commitar/alterar segredos: `.env` (esta no repo so o `.env.example`).
- Nao executar `git commit`, `git push`, `collectstatic` ou deploy sem
  confirmacao explicita.
- Proibido criar arquivos de backup manuais (`*.bak`, `*.bak_*`) no repo.

## Convencoes de implementacao

- **Card = codigo real do outro projeto**: ao corrigir versao/tecnologia, ajustar
  os tres lugares na mesma tarefa — `_montar_contexto` (`core/views.py`), a faixa
  de tecnologias em `core/templates/core/menu.html` e o `docs/PROJETOS.md`
  (secao 7.2 + 3 linhas na secao 2).
- Links externos abrem em **nova aba** (`target="_blank"` com `rel="noopener"`);
  icones vem de biblioteca, nao de emoji.
- Nao adicionar dependencia nova nem logica de banco: o menu so linka e monitora.
- Prefira editar arquivos existentes em vez de criar modulos novos.
- Antes de finalizar: `python manage.py check` e abrir a home (4 cards) e a
  pagina de detalhe; relate o resultado.
