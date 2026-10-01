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
from urllib.parse import urlparse

from django.core.cache import cache
from django.http import Http404
from django.shortcuts import render


logger = logging.getLogger(__name__)


# ============================================================
# HEALTH CHECK
# ============================================================

CACHE_KEY_PREFIX = 'menu_health_'
CACHE_TTL = 60          # segundos
HEALTH_TIMEOUT = 5      # segundos por tentativa




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
        return {'status': 'online' if ms < 2000 else 'lento', 'code': code, 'ms': ms}
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

    return {'status': 'online' if ms < 2000 else 'lento', 'code': code, 'ms': ms, 'erro': None}


def _check_health_deep_cached(url: str) -> dict:
    """Versao cacheada (60s) do _check_health_deep."""
    chave = f'{CACHE_KEY_PREFIX}deep_{url}'
    resultado = cache.get(chave)
    if resultado is None:
        resultado = _check_health_deep(url)
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
        as400_base   = 'https://as400.arosasse.tech'
        cnpj_base    = 'https://cnpj.arosasse.tech'
        chat_ia_base = 'https://chat.arosasse.tech'

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
    saude = {k: _check_health_deep_cached(u) for k, u in urls_health.items()}

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
    projetos = [
        {
            'id': 'as400',
            'nome': 'IBM i · DB2 · Pessoas',
            'descricao': 'CRUD completo de uma tabela de pessoas armazenadas em um banco DB2 hospedado num IBM i (AS/400) remoto (pub400.com) via JDBC.',
            'url': urls['as400'],
            'icon': 'bi bi-person-lines-fill',
            'cor': 'success',
            'imagem': 'ibmi-db2/consulta-lista.png',
            'stack': ['Django 6.0', 'JPype', 'jt400', 'DB2 (IBM i)', 'Redis'],
            'destaques': [
                'Conexao JDBC real a um mainframe IBM i (pub400.com)',
                'CRUD completo com validacao de CPF e CEP',
                'Cache Redis e pool de conexoes JDBC',
            ],
            'galeria': [
                {'arquivo': 'ibmi-db2/consulta-filtros.png', 'titulo': 'Filtros de consulta'},
                {'arquivo': 'ibmi-db2/consulta-lista.png',   'titulo': 'Lista de pessoas'},
                {'arquivo': 'ibmi-db2/consulta-detalhe.png', 'titulo': 'Detalhe da pessoa'},
                {'arquivo': 'ibmi-db2/alteracao.png',        'titulo': 'Alteracao'},
                {'arquivo': 'ibmi-db2/exclusao.png',         'titulo': 'Exclusao'},
                {'arquivo': 'ibmi-db2/api.png',              'titulo': 'API de dados'},
            ],
            **_status_do_card('as400'),
        },
        {
            'id': 'chat_pessoas',
            'nome': 'Chat com IA · Pessoas (IBM i · DB2)',
            'descricao': 'Pergunte em linguagem natural sobre os dados de pessoas do DB2 e receba a resposta em SQL executado.',
            'url': urls['chat_pes'],
            'icon': 'bi bi-robot',
            'cor': 'info',
            'imagem': 'chat-ibmi-db2/chat-1.png',
            'stack': ['Django 6.0', 'OpenAI SDK', 'DeepSeek', 'DB2 (IBM i)', 'Redis'],
            'destaques': [
                'Traducao PT-BR -> SQL com contexto da conversa',
                'Historico persistido (contexto de 10 mensagens)',
                'Fallback automatico quando o LLM falha',
            ],
            'galeria': [
                {'arquivo': 'chat-ibmi-db2/chat-1.png',         'titulo': 'Interface do chat'},
                {'arquivo': 'chat-ibmi-db2/chat-resposta.png',  'titulo': 'Resposta da IA'},
            ],
            **_status_do_card('chat_pes'),
        },
        {
            'id': 'cnpj',
            'nome': 'Consulta Empresas · Receita Federal',
            'descricao': 'Consulta de CNPJ sobre a base publica da RFB (38 milhoes de estabelecimentos) com filtros, keyset pagination e estatisticas.',
            'url': urls['cnpj'],
            'icon': 'bi bi-building',
            'cor': 'primary',
            'imagem': 'cnpj/consulta-filtros.png',
            'stack': ['Django 5.1', 'PostgreSQL 15', 'Redis', 'Keyset pagination'],
            'destaques': [
                '38M de linhas com keyset pagination (sem OFFSET)',
                'Indices parciais e CTEs MATERIALIZED',
                'Estatisticas agregadas com cache de 1h',
            ],
            'galeria': [
                {'arquivo': 'cnpj/consulta-filtros.png',      'titulo': 'Filtros de consulta'},
                {'arquivo': 'cnpj/consulta-lista.png',        'titulo': 'Lista de empresas'},
                {'arquivo': 'cnpj/detalhe-dados.png',         'titulo': 'Detalhe: dados da empresa'},
                {'arquivo': 'cnpj/detalhe-endereco.png',      'titulo': 'Detalhe: endereco'},
                {'arquivo': 'cnpj/detalhe-estab-socios.png',  'titulo': 'Detalhe: estabelecimentos e socios'},
            ],
            **_status_do_card('cnpj'),
        },
        {
            'id': 'chat_empresas',
            'nome': 'Chat com IA · Empresas (Receita Federal)',
            'descricao': 'Pergunte em linguagem natural sobre as empresas da RFB. Pipeline com validacao SQL, resposta em texto e graficos.',
            'url': urls['chat_emp'],
            'icon': 'bi bi-chat-dots',
            'cor': 'warning',
            'imagem': 'chat-cnpj/chat-1.png',
            'stack': ['Django 5.1', 'MongoDB 8', 'DeepSeek', 'Chart.js'],
            'destaques': [
                'Pipeline SQL com 5 camadas de seguranca',
                'Historico em MongoDB (Repository pattern)',
                'Resposta em texto natural + graficos (Chart.js)',
                'Recusa perguntas fora do schema (RECUSAR:)',
            ],
            'galeria': [
                {'arquivo': 'chat-cnpj/chat-1.png',          'titulo': 'Chat: perguntas, respostas, historico'},
                {'arquivo': 'chat-cnpj/chat-resposta.png',   'titulo': 'Resposta da IA'},
                {'arquivo': 'chat-cnpj/chat-graficos.png',   'titulo': 'Graficos'},
            ],
            **_status_do_card('chat_emp'),
        },
    ]

    return {
        'projetos': projetos,
        'versao': '1.2',
        'ambiente': ambiente_nome,
        'ambiente_cor': ambiente_cor,
        'is_local': is_local,
        'host_atual': host_completo,
    }


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

