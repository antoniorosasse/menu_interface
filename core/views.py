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


# ============================================================
# VIEW
# ============================================================

def menu_principal(request):
    """
    Pagina inicial com links para todos os projetos.

    - Em LOCAL (DEBUG=True): cada projeto em uma porta diferente, mesmo host.
    - Em PRODUCAO: menu na raiz de arosasse.tech, outros projetos em subdominios.
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
        'as400':    f'{as400_base}/health/',
        'chat_pes': f'{as400_base}/health/',      # mesmo app do as400
        'cnpj':     f'{cnpj_base}/health/',
        'chat_emp': f'{chat_ia_base}/health/',
    }


    # ============================================================
    # HEALTH CHECK (com cache)
    # ============================================================
    saude = {k: _check_url_cached(u) for k, u in urls_health.items()}

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
            'nome': 'AS/400 · Pessoas',
            'descricao': 'CRUD completo de pessoas que fala com um banco DB2 hospedado num IBM i remoto (pub400.com) via JDBC.',
            'url': urls['as400'],
            'icon': 'bi bi-person-lines-fill',
            'cor': 'success',
            'imagem': 'CardDB2AS400_1.png',
            'stack': ['Django 6.0', 'JPype', 'jt400', 'DB2 (IBM i)', 'Redis'],
            'destaques': [
                'Conexao JDBC real a um mainframe IBM i (pub400.com)',
                'CRUD completo com validacao de CPF e CEP',
                'Cache Redis e pool de conexoes JDBC',
            ],
            **_status_do_card('as400'),
        },
        {
            'id': 'chat_pessoas',
            'nome': 'Chat com IA · Pessoas (AS/400)',
            'descricao': 'Pergunte em linguagem natural sobre os dados de pessoas do DB2 e receba a resposta em SQL executado.',
            'url': urls['chat_pes'],
            'icon': 'bi bi-robot',
            'cor': 'info',
            'imagem': 'CardDB2AS400_Chat_1.png',
            'stack': ['Django 6.0', 'OpenAI SDK', 'DeepSeek', 'DB2 (IBM i)', 'Redis'],
            'destaques': [
                'Traducao PT-BR -> SQL com contexto da conversa',
                'Historico persistido (contexto de 10 mensagens)',
                'Fallback automatico quando o LLM falha',
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
            'imagem': 'Card_CNPJ_1.png',
            'stack': ['Django 5.1', 'PostgreSQL 15', 'Redis', 'Keyset pagination'],
            'destaques': [
                '38M de linhas com keyset pagination (sem OFFSET)',
                'Indices parciais e CTEs MATERIALIZED',
                'Estatisticas agregadas com cache de 1h',
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
            'imagem': 'Card_CNPJ_Chat1.png',
            'stack': ['Django 5.1', 'MongoDB 8', 'DeepSeek', 'Chart.js'],
            'destaques': [
                'Pipeline SQL com 5 camadas de seguranca',
                'Historico em MongoDB (Repository pattern)',
                'Resposta em texto natural + graficos (Chart.js)',
                'Recusa perguntas fora do schema (RECUSAR:)',
            ],
            **_status_do_card('chat_emp'),
        },
    ]

    context = {
        'projetos': projetos,
        'versao': '1.2',
        'ambiente': ambiente_nome,
        'ambiente_cor': ambiente_cor,
        'is_local': is_local,
        'host_atual': host_completo,
    }

    return render(request, 'core/menu.html', context)