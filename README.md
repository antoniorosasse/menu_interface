# Menu Interface

Pagina inicial do Sistema Integrado (arosasse.tech). Mostra 4 cards com os
modulos do sistema e faz health check em tempo real de cada um.

## Stack

- Django 5.1.7
- Python 3.13
- Gunicorn + systemd (producao)
- SQLite (sessoes e admin)

## Estrutura

    menu_interface/
    ├── core/                       # App principal
    │   ├── templates/core/
    │   │   └── menu.html           # Pagina do menu
    │   ├── urls.py
    │   └── views.py                # menu_principal + health checks
    ├── menu_project/               # Configuracao Django
    │   ├── settings.py
    │   ├── urls.py
    │   └── wsgi.py
    ├── manage.py
    └── requirements.txt

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
| GET | `/` | Pagina do menu (4 cards) |
| GET | `/health/` | Health check (responde `ok`) |

## Deploy

Na maquina NoteNeto:

    ./deploy.sh menu

## Ambiente

- **Local:** http://localhost:8000
- **Producao:** https://arosasse.tech

## Health check dos servicos

A view `menu_principal` faz um `HEAD` no `/health/` de cada servico,
com cache de 60s (pra nao martelar os servicos a cada F5). Badge:

- 🟢 **No ar** — resposta < 2s
- 🟡 **Lento** — resposta entre 2s e 5s
- 🔴 **Fora** — erro, timeout ou 5xx

Os servicos monitorados sao:

- `as400.arosasse.tech` (consulta de pessoas)
- `as400.arosasse.tech/chat-pessoas/` (chat IA de pessoas)
- `cnpj.arosasse.tech` (consulta de empresas)
- `chat.arosasse.tech` (chat IA de empresas)

## Repositorios relacionados

- [as400_interface](https://github.com/antoniorosasse/as400_interface)
- [cnpj_interface](https://github.com/antoniorosasse/cnpj_interface)
- [ProjetoCargaDados](https://github.com/antoniorosasse/ProjetoCargaDados)
- [Projetos](https://github.com/antoniorosasse/Projetos) — scripts e manual de git
