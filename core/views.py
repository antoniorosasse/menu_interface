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
# HOSTS E URLS DO SITE
# ============================================================
# O mesmo processo (menu.service) serve dois sites e escolhe pelo Host:
#   - busquecnpj.com.br (e www) -> landing comercial
#   - qualquer outro host       -> menu/portfolio (arosasse.tec.br)
#
# Durante a transicao o portfolio atende em portfolio.busquecnpj.com.br;
# quando o dominio proprio entrar, a virada e' so de .env (PORTFOLIO_URL
# e ALLOWED_HOSTS) + restart. Nenhuma linha de codigo muda.

def _hosts_env(nome: str, default: str) -> set:
    """Le do ambiente uma lista de hosts separada por virgula."""
    bruto = os.getenv(nome, default)
    return {h.strip().lower() for h in bruto.split(',') if h.strip()}


HOSTS_COMERCIAL = _hosts_env(
    'HOSTS_COMERCIAL', 'busquecnpj.com.br,www.busquecnpj.com.br'
)
PORTFOLIO_URL = os.getenv('PORTFOLIO_URL', 'https://arosasse.tec.br').rstrip('/')

# Pagina inicial do produto (landing comercial). Em producao e' o dominio raiz;
# no dev a landing e' servida em /site/ pelo runserver da porta 8000 (o
# portfolio fica em /menu/ quando HOSTS_COMERCIAL inclui o host). LANDING_URL
# no .env aponta para outro host sem mexer no codigo.
LANDING_URL = os.getenv('LANDING_URL', '').rstrip('/')


# ============================================================
# LANDING COMERCIAL (busquecnpj.com.br)
# ============================================================
# Ids dos projetos de _montar_contexto que a landing apresenta, na ordem
# em que aparecem. A landing NAO e' o portfolio: ela mostra o sistema em
# uma frase, para quem quer contratar. Destaques tecnicos, stack e telas
# continuam so' no menu (/menu/).
SOLUCOES_LANDING = ('cnpj', 'chat_empresas', 'proximidade', 'estatisticas')

# Versao comercial da descricao de cada solucao: sem jargao (keyset,
# RAG, CTE, pgvector...). O texto tecnico do card fica intacto no
# portfolio; aqui trocamos so' a frase de apresentacao.
TEXTOS_LANDING = {
    'cnpj': (
        'Consulte qualquer uma das 74,4 milhões de empresas da Receita '
        'Federal por nome, ramo de atividade, cidade ou situação cadastral, '
        'com endereço e sócios de cada uma.'
    ),
    'chat_empresas': (
        'Pergunte em português e receba a resposta pronta: a IA busca as '
        'empresas na base, confere os números e responde apenas com o que '
        'está registrado.'
    ),
    'proximidade': (
        'Encontre estabelecimentos num raio de até 100 km a partir de um '
        'CNPJ, CEP, cidade ou coordenada, com a distância em km de cada '
        'resultado.'
    ),
    'estatisticas': (
        'Os totais da base prontos para consultar: quantas empresas estão '
        'ativas, quantas são do Simples/MEI, ranking de estados, porte, '
        'natureza jurídica e ramo de atividade.'
    ),
}


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
        cnpj_base    = 'https://cnpj.busquecnpj.com.br'
        chat_ia_base = 'https://chat.busquecnpj.com.br'

        ambiente_nome = '🚀 Produção'
        ambiente_cor = 'success'

    # ============================================================
    # URLS DOS PROJETOS (link que aparece no card)
    # ============================================================
    urls = {
        'as400':    f'{as400_base}/pessoas/',
        'chat_pes': f'{as400_base}/chat-pessoas/',
        'cnpj':     f'{cnpj_base}/',
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
        # voltava para esta propria landing (parecia que o site nao reconhecia
        # o usuario). A sessao e' do cnpj_interface, nao deste site.
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
        # (landing). Em dev o runserver da landing fica na porta 8000.
        'landing_url': LANDING_URL or (
            f'http://{host_sem_porta}:8000/site/' if is_local
            else 'https://busquecnpj.com.br/'
        ),
    }


def home(request):
    """
    Entrada do site: escolhe a pagina pelo Host da requisicao.

    - busquecnpj.com.br / www  -> landing comercial (site de servicos)
    - qualquer outro host      -> menu/portfolio

    A lista de hosts comerciais vem do .env (HOSTS_COMERCIAL), entao a
    troca do dominio do portfolio nao exige mexer aqui.
    """
    host = request.get_host().split(':')[0].lower()
    if host in HOSTS_COMERCIAL:
        return landing_comercial(request)
    return menu_principal(request)


def landing_comercial(request):
    """
    Landing do site comercial (busquecnpj.com.br).

    Reusa _montar_contexto para herdar as URLs dos apps (dev: :8001/:8002,
    prod: subdominios) e o health check com cache de 60s. As solucoes
    apresentadas saem de SOLUCOES_LANDING, com a descricao comercial de
    TEXTOS_LANDING (o texto tecnico fica no portfolio).

    A copia com {**projeto} evita sobrescrever o dict original: o mesmo
    objeto e' usado pelo menu.
    """
    context = _montar_contexto(request)
    por_id = {p['id']: p for p in context['projetos']}

    solucoes = []
    for solucao_id in SOLUCOES_LANDING:
        projeto = por_id.get(solucao_id)
        if projeto is None:
            continue
        solucoes.append({
            **projeto,
            'descricao': TEXTOS_LANDING.get(solucao_id, projeto['descricao']),
        })

    context['solucoes'] = solucoes
    context['todos_online'] = bool(solucoes) and all(
        s['status_cor'] == 'success' for s in solucoes
    )

    return render(request, 'core/landing.html', context)


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

