# Menu Interface

Página inicial do Sistema Integrado (arosasse.tech). Mostra 5 cards — os 4
módulos do sistema e este próprio site como **demonstração ao vivo** do
portfólio —, faz health check em tempo real dos outros apps e tem uma página
de detalhe por projeto (com galeria de telas).

## Índice

- [Stack](#stack)
- [Estrutura](#estrutura)
- [Como rodar local](#como-rodar-local)
- [Endpoints](#endpoints)
- [Funcionalidades da home](#funcionalidades-da-home)
- [Health check dos serviços](#health-check-dos-serviços)
- [Deploy](#deploy)
- [Ambiente](#ambiente)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Repositórios relacionados](#repositórios-relacionados)

## Stack

- Django 5.1.7
- Python 3.13
- Gunicorn + systemd (produção)
- SQLite (sessões e admin)
- Bootstrap 5.3 (via CDN)

## Estrutura

    menu_interface/
    ├── core/                          # App principal
    │   ├── templates/core/
    │   │   ├── menu.html              # Pagina do menu (cards)
    │   │   └── projeto.html           # Pagina de detalhe de um projeto
    │   ├── urls.py
    │   └── views.py                   # menu_principal + detalhe_projeto + health checks
    ├── menu_project/                  # Configuracao Django
    │   ├── settings.py
    │   ├── urls.py
    │   └── wsgi.py
    ├── static/                        # Imagens do portfolio (galeria + capas)
    │   ├── ibmi-db2/                  # Screenshots do AS/400 + DB2
    │   ├── chat-ibmi-db2/             # Screenshots do chat IA do AS/400
    │   ├── cnpj/                      # Screenshots da consulta de CNPJ
    │   └── chat-cnpj/                 # Screenshots do chat IA do CNPJ
    ├── manage.py
    ├── requirements.txt
    └── .env.example

## Como rodar local

    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env            # preencher valores
    python manage.py runserver 8000

Acessa em http://localhost:8000/

## Endpoints

| Método | URL | O que faz |
|---|---|---|
| GET | `/` | Página do menu (5 cards + faixa de tecnologias) |
| GET | `/projeto/<id>/` | Página de detalhe de um projeto (galeria) |
| GET | `/health/` | Health check leve (responde `ok`) |

## Funcionalidades da home

- **5 cards**: os 4 projetos do sistema (`cnpj`, `chat_empresas`, `as400`,
  `chat_pessoas`) + o card `menu`, que apresenta este site como
  **demonstração ao vivo** do portfólio (sem health check: ele mostraria a si
  mesmo; status fixo "Demo ao vivo", imagem de capa gerada por CSS e botão
  "Ver em produção"). Cada card tem imagem de capa, badges de stack, lista de
  destaques técnicos e botão de acesso.
- **Badge de status dinâmico por card** (🟢 No ar / 🟡 Lento / 🔴 Fora),
  atualizado por health check (ver seção abaixo).
- **Botão "Detalhes"** em cada card, que abre a página `/projeto/<id>/`
  com a galeria completa de telas daquele projeto.
- **Faixa de tecnologias interativa** no rodapé (17 pílulas): Django 5.1 a 6.1,
  Python 3.13, PostgreSQL 15, MongoDB 8, pgvector, sentence-transformers (Braza),
  DB2 (IBM i), JPype/JDBC, DeepSeek, OpenAI SDK, Chart.js, Bootstrap 5.3,
  pandas/pyarrow, Gunicorn, Nginx, Let's Encrypt, Git/GitHub. Cada pílula é um
  `<button>` que abre, no painel logo abaixo da faixa, o uso **real** da tecnologia
  neste sistema + link para a documentação oficial. Funciona por hover (desktop),
  foco (teclado) e clique/toque (celular, que fixa o painel; `Esc` ou clique fora
  solta). Textos e links vivem em `_montar_contexto` (lista `tecnologias`) — o
  template só itera. **Não citar Docker** (nenhum dos projetos usa container).
- **Bloco "Outros repositórios"**: abaixo dos cards, a lista
  `repos_sem_card` (em `_montar_contexto`) mostra os repositórios que **não**
  têm card — hoje só o **ProjetoCargaDados**, com a descrição no `title` do
  botão.
- **Rodapé**: mostra `Versao {{ versao }}` (hoje `1.4`), o host atual e o badge
  de ambiente. A versão também vem de `_montar_contexto`.
- **Fonte dos cards**: além das tecnologias, os textos, URLs, stacks, destaques
  e galerias de cada card vivem na lista `projetos` de `_montar_contexto` — o
  template só itera. Health check e imagem de capa também saem de lá.
- **Texto exibido** (cards, faixa, títulos) é escrito com acentos; comentários,
  identificadores e nomes de tabela seguem sem acento (ver `.clinerules`).
- **Dark mode** (tema claro/escuro) com:
  - Botão flutuante (canto superior direito).
  - Persistência em `localStorage` (`menu-theme`).
  - Detecção de preferência do SO (`prefers-color-scheme`) no primeiro acesso.

## Health check dos serviços

Cada card consulta o endpoint **`/health/deep/`** do seu respectivo app
(note: **não** é `/health/`, e sim o `/health/deep/`). O endpoint devolve
um JSON com `status: "ok" | "error"`. O menu considera:

- **🟢 No ar** — `status: "ok"` e resposta em até **4s**.
- **🟡 Lento** — `status: "ok"` mas resposta entre 4s e 5s.
- **🔴 Fora** — `status: "error"`, timeout (5s), HTTP != 200, ou JSON inválido.

**Cache:** o resultado fica em cache (`LocMemCache`) por:

- **60 segundos** quando o resultado é `online` ou `lento`.
- **10 segundos** quando é `offline` — pra recuperar rápido se o backend
  estava apenas subindo ou teve um blip.

**URLs consultadas** (por ambiente):

Em local (`DEBUG=True`), o menu assume que os apps estão na mesma máquina,
em portas diferentes:

- IBM i · DB2 · Pessoas: `http://<host>:8001/health/deep/`
- Chat IA · Pessoas: `http://<host>:8001/health/deep/` (mesmo app)
- Consulta Empresas: `http://<host>:8002/health/deep/`
- Chat IA · Empresas: `http://<host>:8002/chat/health/deep/`

Em produção:

- IBM i · DB2 · Pessoas: `https://as400.arosasse.tech/health/deep/`
- Chat IA · Pessoas: `https://as400.arosasse.tech/health/deep/`
- Consulta Empresas: `https://cnpj.arosasse.tech/health/deep/`
- Chat IA · Empresas: `https://chat.arosasse.tech/chat/health/deep/`

**Nota:** o timeout por chamada é `HEALTH_TIMEOUT = 5` segundos (hardcoded
em `core/views.py`).

## Deploy

Na máquina NoteNeto:

    ./deploy.sh menu

## Ambiente

- **Local:** http://localhost:8000
- **Produção:** https://arosasse.tech

## Variáveis de ambiente

Ver `.env.example`. São 3:

- `SECRET_KEY` — chave do Django (obrigatório)
- `DEBUG` — `True` ou `False`
- `ALLOWED_HOSTS` — lista separada por vírgula

## Repositórios relacionados

- [as400_interface](https://github.com/antoniorosasse/as400_interface)
- [cnpj_interface](https://github.com/antoniorosasse/cnpj_interface)
- [ProjetoCargaDados](https://github.com/antoniorosasse/ProjetoCargaDados)
