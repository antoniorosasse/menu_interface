# Menu Interface

Pagina inicial do Sistema Integrado (arosasse.tech). Mostra 4 cards com os
modulos do sistema, faz health check em tempo real de cada um, e tem uma
pagina de detalhe por projeto (com galeria de telas).

## Stack

- Django 5.1.7
- Python 3.13
- Gunicorn + systemd (producao)
- SQLite (sessoes e admin)
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

| Metodo | URL | O que faz |
|---|---|---|
| GET | `/` | Pagina do menu (4 cards + faixa de tecnologias) |
| GET | `/projeto/<id>/` | Pagina de detalhe de um projeto (galeria) |
| GET | `/health/` | Health check leve (responde `ok`) |

## Funcionalidades da home

- **4 cards de projeto** com imagem de capa, badges de stack, lista de
  destaques tecnicos e botao de acesso.
- **Badge de status dinamico por card** (🟢 No ar / 🟡 Lento / 🔴 Fora),
  atualizado por health check (ver secao abaixo).
- **Botao "Detalhes"** em cada card, que abre a pagina `/projeto/<id>/`
  com a galeria completa de telas daquele projeto.
- **Faixa de tecnologias** no rodape (pílulas).
- **Dark mode** (tema claro/escuro) com:
  - Botao flutuante (canto superior direito).
  - Persistencia em `localStorage` (`menu-theme`).
  - Deteccao de preferencia do SO (`prefers-color-scheme`) no primeiro acesso.

## Health check dos servicos

Cada card consulta o endpoint **`/health/deep/`** do seu respectivo app
(note: **nao** e' `/health/`, e' o `/health/deep/`). O endpoint devolve
um JSON com `status: "ok" | "error"`. O menu considera:

- **🟢 No ar** — `status: "ok"` e resposta em ate **4s**.
- **🟡 Lento** — `status: "ok"` mas resposta entre 4s e 5s.
- **🔴 Fora** — `status: "error"`, timeout (5s), HTTP != 200, ou JSON invalido.

**Cache:** o resultado fica em cache (`LocMemCache`) por:

- **60 segundos** quando o resultado e' `online` ou `lento`.
- **10 segundos** quando e' `offline` — pra recuperar rapido se o backend
  estava apenas subindo ou teve um blip.

**URLs consultadas** (por ambiente):

Em local (`DEBUG=True`), o menu assume que os apps estao na mesma maquina,
em portas diferentes:

- IBM i · DB2 · Pessoas: `http://<host>:8001/health/deep/`
- Chat IA · Pessoas: `http://<host>:8001/health/deep/` (mesmo app)
- Consulta Empresas: `http://<host>:8002/health/deep/`
- Chat IA · Empresas: `http://<host>:8002/chat/health/deep/`

Em producao:

- IBM i · DB2 · Pessoas: `https://as400.arosasse.tech/health/deep/`
- Chat IA · Pessoas: `https://as400.arosasse.tech/health/deep/`
- Consulta Empresas: `https://cnpj.arosasse.tech/health/deep/`
- Chat IA · Empresas: `https://chat.arosasse.tech/chat/health/deep/`

**Nota:** o timeout por chamada e' `HEALTH_TIMEOUT = 5` segundos (hardcoded
em `core/views.py`).

## Deploy

Na maquina NoteNeto:

    ./deploy.sh menu

## Ambiente

- **Local:** http://localhost:8000
- **Producao:** https://arosasse.tech

## Variaveis de ambiente

Ver `.env.example`. Sao 3:

- `SECRET_KEY` — chave do Django (obrigatorio)
- `DEBUG` — `True` ou `False`
- `ALLOWED_HOSTS` — lista separada por virgula

## Repositorios relacionados

- [as400_interface](https://github.com/antoniorosasse/as400_interface)
- [cnpj_interface](https://github.com/antoniorosasse/cnpj_interface)
- [ProjetoCargaDados](https://github.com/antoniorosasse/ProjetoCargaDados)
