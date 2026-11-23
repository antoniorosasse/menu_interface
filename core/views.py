# /home/neto/menu_interface/core/views.py
"""
View do menu principal.

Faz health check dos servicos remotos (com cache de 60s) para exibir
um badge de status (verde/amarelo/vermelho) por card.

Sem acentos no codigo. Comentarios em PT-BR sem acento.
"""

import os
import socket
import logging
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from django.core.cache import cache
from django.http import Http404
from django.shortcuts import render

from .dados_projetos import (
    FONTES_CEP,
    FONTES_EMPRESAS,
    FONTES_IBGE,
    FONTES_RFB,
    TECNOLOGIAS,
    montar_projetos,
    montar_secoes,
)


logger = logging.getLogger(__name__)


# ============================================================
# HEALTH CHECK
# ============================================================

CACHE_KEY_PREFIX = 'menu_health_'
CACHE_TTL = 60          # segundos (estado 'online' ou 'lento')
CACHE_TTL_OFFLINE = 10  # segundos (estado 'offline' - recupera rapido)
HEALTH_TIMEOUT = 5      # segundos por tentativa
# Limite entre 'online' e 'lento'. Fica numa constante so porque o docstring
# de _check_url sempre falou 2s e o codigo comparava com 4000 ms: agora os
# dois _check_* usam o mesmo numero.
LIMIAR_LENTO_MS = 2000


# ============================================================
# URLS DO SITE
# ============================================================
# Este processo (menu.service) e' so o portfolio (arosasse.tec.br). Desde
# 23/11/2026 o dominio do produto (busquecnpj.com.br) aponta direto para o
# cnpj_interface no nginx: nao existe mais decisao por Host aqui.

PORTFOLIO_URL = os.getenv('PORTFOLIO_URL', 'https://arosasse.tec.br').rstrip('/')

# Pagina inicial do produto (raiz do dominio). No dev e' o runserver do cnpj
# na 8002; LANDING_URL no .env aponta para outro host sem mexer em codigo.
LANDING_URL_PADRAO = 'https://busquecnpj.com.br/'
LANDING_URL = os.getenv('LANDING_URL', '').rstrip('/')


# ============================================================
# FONTES PUBLICAS DOS DADOS
# ============================================================
# FONTES_RFB/FONTES_CEP/FONTES_IBGE e o conteudo dos cards moram em
# core/dados_projetos.py (importados no topo deste modulo).


def _check_url(url: str) -> dict:
    """
    Faz um HEAD rapido na URL e devolve:
      {'status': 'online' | 'lento' | 'offline', 'code': int | None, 'ms': int}

    Regras:
      - Resposta ate 2s                      -> 'online'
      - Resposta entre 2s e HEALTH_TIMEOUT   -> 'lento'
      - Erro / timeout / 5xx                 -> 'offline'
    """
    import time
    import urllib.request
    import urllib.error

    inicio = time.monotonic()
    req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'menu-health/1.0'})

    try:
        with urllib.request.urlopen(req, timeout=HEALTH_TIMEOUT) as resp:
            code = resp.status
    except urllib.error.HTTPError as e:
        code = e.code
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError):
        return {'status': 'offline', 'code': None, 'ms': int((time.monotonic() - inicio) * 1000)}

    ms = int((time.monotonic() - inicio) * 1000)

    if code in (200, 301, 302, 401, 403):
        return {'status': 'online' if ms < LIMIAR_LENTO_MS else 'lento', 'code': code, 'ms': ms}
    return {'status': 'offline', 'code': code, 'ms': ms}


def _check_url_cached(url: str) -> dict:
    """Versao com cache de 60s para nao martelar os servicos a cada F5."""
    chave = f'{CACHE_KEY_PREFIX}{url}'
    resultado = cache.get(chave)
    if resultado is None:
        resultado = _check_url(url)
        cache.set(chave, resultado, CACHE_TTL)
    return resultado

def _check_health_deep(url: str) -> dict:
    """
    Faz um GET na URL (deep health check) e le o JSON.

    O endpoint /health/deep/ devolve HTTP 200 SEMPRE, mas o JSON tem
    campo 'status': 'ok' | 'error'. So consideramos online se status == 'ok'.

    Devolve:
      {'status': 'online' | 'lento' | 'offline', 'code': int | None, 'ms': int,
       'erro': str | None}
    """
    import time
    import json
    import urllib.request
    import urllib.error

    inicio = time.monotonic()
    req = urllib.request.Request(url, method='GET', headers={'User-Agent': 'menu-health/1.0'})

    try:
        with urllib.request.urlopen(req, timeout=HEALTH_TIMEOUT) as resp:
            code = resp.status
            body = resp.read().decode('utf-8', errors='ignore')
    except urllib.error.HTTPError as e:
        code = e.code
        return {'status': 'offline', 'code': code, 'ms': int((time.monotonic() - inicio) * 1000), 'erro': f'HTTP {code}'}
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
        return {'status': 'offline', 'code': None, 'ms': int((time.monotonic() - inicio) * 1000), 'erro': str(e)[:100]}

    ms = int((time.monotonic() - inicio) * 1000)

    if code != 200:
        return {'status': 'offline', 'code': code, 'ms': ms, 'erro': f'HTTP {code}'}

    # Le o JSON
    try:
        dados = json.loads(body)
    except (ValueError, TypeError):
        return {'status': 'offline', 'code': code, 'ms': ms, 'erro': 'JSON invalido'}

    if dados.get('status') != 'ok':
        return {'status': 'offline', 'code': code, 'ms': ms, 'erro': dados.get('erro') or dados.get('status') or 'status != ok'}

    return {'status': 'online' if ms < LIMIAR_LENTO_MS else 'lento', 'code': code, 'ms': ms, 'erro': None}


def _check_health_deep_cached(url: str) -> dict:
    """
    Versao cacheada do _check_health_deep.

    - Resultado 'online' ou 'lento': cache de 60s (CACHE_TTL).
    - Resultado 'offline': cache de 10s (CACHE_TTL_OFFLINE), pra
      recuperar rapido se o backend estava apenas subindo.
    """
    chave = f'{CACHE_KEY_PREFIX}deep_{url}'
    resultado = cache.get(chave)
    if resultado is None:
        resultado = _check_health_deep(url)
        if resultado.get('status') == 'offline':
            cache.set(chave, resultado, CACHE_TTL_OFFLINE)
        else:
            cache.set(chave, resultado, CACHE_TTL)
    return resultado

# ============================================================
# VIEW
# ============================================================

def _montar_contexto(request):
    """
    Monta o dicionario de contexto usado pelo menu E pela pagina de detalhe.

    Contem: projetos (com stack, destaques, galeria), ambiente, versao, etc.
    Extraido do antigo menu_principal pra ser reusado em detalhe_projeto.
    """
    # ============================================================
    # AMBIENTE
    # ============================================================
    is_local = os.getenv('DEBUG', 'False') == 'True'

    # ============================================================
    # HOST ATUAL
    # ============================================================
    host_completo = request.get_host()
    host_sem_porta = host_completo.split(':')[0]

    # ============================================================
    # URLS DOS PROJETOS
    # ============================================================
    if is_local:
        as400_base  = f'http://{host_sem_porta}:8001'
        cnpj_base   = f'http://{host_sem_porta}:8002'
        chat_ia_base = f'http://{host_sem_porta}:8002'   # mesmo host do cnpj em local

        ambiente_nome = '🖥 Desenvolvimento Local'
        ambiente_cor = 'warning'
    else:
        as400_base   = 'https://as400.busquecnpj.com.br'
        cnpj_base    = 'https://busquecnpj.com.br'
        chat_ia_base = 'https://chat.busquecnpj.com.br'

        ambiente_nome = '🚀 Produção'
        ambiente_cor = 'success'

    # ============================================================
    # URLS DOS PROJETOS (link que aparece no card)
    # ============================================================
    urls = {
        'as400':    f'{as400_base}/pessoas/',
        'chat_pes': f'{as400_base}/chat-pessoas/',
        'cnpj':     f'{cnpj_base}/empresas/',
        'chat_emp': f'{chat_ia_base}/chat/',
        # Paginas do cnpj_interface que ganharam card proprio no menu
        'proximidade':  f'{cnpj_base}/proximidade/',
        'estatisticas': f'{cnpj_base}/estatisticas/',
    }

    # ============================================================
    # URLS DE HEALTH CHECK (endpoint leve que so responde 'ok')
    # ============================================================
    urls_health = {
        'as400':    f'{as400_base}/health/deep/',
        'chat_pes': f'{as400_base}/health/deep/',      # mesmo app do as400
        'cnpj':     f'{cnpj_base}/health/deep/',
        'chat_emp': f'{chat_ia_base}/chat/health/deep/',
    }

    # ============================================================
    # HEALTH CHECK (com cache)
    # ============================================================
    # Os quatro checks sao independentes, entao vao em paralelo: em serie, com
    # um servico fora do ar, a pagina esperava HEALTH_TIMEOUT por servico (ate
    # 20 s antes de renderizar). O cache continua evitando martelar os servicos.
    with ThreadPoolExecutor(max_workers=len(urls_health)) as executor:
        resultados = list(executor.map(_check_health_deep_cached, urls_health.values()))
    saude = dict(zip(urls_health, resultados))

    def _status_do_card(chave: str) -> dict:
        """Devolve dict com status/status_cor prontos pro template."""
        s = saude.get(chave, {})
        st = s.get('status', 'offline')
        if st == 'online':
            return {'status': '🟢 No ar', 'status_cor': 'success'}
        if st == 'lento':
            return {'status': '🟡 Lento', 'status_cor': 'warning'}
        return {'status': '🔴 Fora', 'status_cor': 'danger'}

    # ============================================================
    # LISTA DE PROJETOS
    # ============================================================
    projetos = montar_projetos(urls, _status_do_card, PORTFOLIO_URL)

    # ============================================================
    # SECOES DO MENU
    # ============================================================
    # Os 5 cards em destaque (4 do sistema CNPJ + o card deste site) ficam na
    # primeira secao; os 2 apps de IBM i/DB2 aparecem abaixo, em card reduzido.
    # 'projetos' continua plano, porque detalhe_projeto busca o id nessa lista.
    secoes = montar_secoes(projetos)

    # ============================================================
    # FAIXA DE TECNOLOGIAS (nome + onde foi usado de verdade + doc)
    # ============================================================
    # Fonte unica: o template so itera sobre esta lista. Cada 'desc' deve
    # descrever o uso REAL da tecnologia neste sistema, nao a definicao
    # generica dela (regra em .clinerules/00-projeto.md).
    tecnologias = TECNOLOGIAS

    return {
        'projetos': projetos,
        'secoes': secoes,
        'tecnologias': tecnologias,
        # Barra comum (core/templates/core/_topbar.html): os mesmos 4 apps
        # que aparecem no menu do cnpj_interface, apontando para as URLs
        # deste ambiente (dev: :8002, prod: subdominios).
        'nav_apps': [
            {'nome': 'Empresas', 'icon': 'bi-building', 'url': urls['cnpj']},
            {'nome': 'Proximidade', 'icon': 'bi-geo-alt', 'url': urls['proximidade']},
            {'nome': 'Estatísticas', 'icon': 'bi-bar-chart', 'url': urls['estatisticas']},
            {'nome': 'Chat IA', 'icon': 'bi-chat-dots', 'url': urls['chat_emp']},
        ],
        # "Entrar" leva ao CHAT do cnpj_interface (rota protegida): deslogado
        # pede a senha e volta para la' (next=/chat/); logado entra direto.
        # Nao apontar para /accounts/login/: como o login redireciona para a
        # pagina inicial do produto, quem ja estava logado clicava em Entrar e
        # voltava para a propria pagina inicial (parecia que o site nao
        # reconhecia o usuario). A sessao e' do cnpj_interface, nao deste site.
        'login_url': f'{cnpj_base}/chat/',
        'repos_sem_card': [
            {'nome': 'ProjetoCargaDados', 'descricao': 'ETL em linha de comando: Parquet da Receita Federal -> Postgres/Mongo, e PESSOAS no DB2', 'url': 'https://github.com/antoniorosasse/ProjetoCargaDados'},
        ],
        'versao': '1.4',
        'ambiente': ambiente_nome,
        'ambiente_cor': ambiente_cor,
        'is_local': is_local,
        'host_atual': host_completo,
        'portfolio_url': PORTFOLIO_URL,
        # Barra do portfolio: link "Inicio" para a pagina inicial do produto
        # (raiz do dominio), servida pelo cnpj_interface. No dev o runserver
        # do cnpj fica na porta 8002.
        'landing_url': LANDING_URL or (
            f'http://{host_sem_porta}:8002/' if is_local
            else LANDING_URL_PADRAO
        ),
    }


def home(request):
    """
    Raiz do site: sempre o portfolio.

    O dominio do produto (busquecnpj.com.br) nao chega mais aqui - o nginx
    o manda direto para o cnpj_interface, que serve a pagina do produto na
    raiz. Este site (menu.service) e' o portfolio (arosasse.tec.br).
    """
    return menu_principal(request)


def menu_principal(request):
    """Pagina inicial com links para todos os projetos."""
    context = _montar_contexto(request)
    return render(request, 'core/menu.html', context)


def detalhe_projeto(request, projeto_id):
    """
    Pagina de detalhe de um projeto do portifolio.

    Reusa _montar_contexto (mesma logica do menu). Se o id nao existir, 404.
    """
    context = _montar_contexto(request)
    projeto = next((p for p in context['projetos'] if p.get('id') == projeto_id), None)
    if projeto is None:
        raise Http404(f'Projeto nao encontrado: {projeto_id}')
    context['projeto'] = projeto
    return render(request, 'core/projeto.html', context)

