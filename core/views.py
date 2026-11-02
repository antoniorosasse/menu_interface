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
CACHE_TTL = 60          # segundos (estado 'online' ou 'lento')
CACHE_TTL_OFFLINE = 10  # segundos (estado 'offline' - recupera rapido)
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
        return {'status': 'online' if ms < 4000 else 'lento', 'code': code, 'ms': ms}
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

    return {'status': 'online' if ms < 4000 else 'lento', 'code': code, 'ms': ms, 'erro': None}


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
            'id': 'cnpj',
            'nome': 'Consulta Empresas · Receita Federal',
            'descricao': 'Consulta de CNPJ sobre a base pública da RFB (38,5 milhões de estabelecimentos) com filtros, keyset pagination e estatísticas.',
            'url': urls['cnpj'],
            'repo': 'https://github.com/antoniorosasse/cnpj_interface',
            'icon': 'bi bi-building',
            'cor': 'primary',
            'imagem': 'cnpj/consulta-filtros.png',
            'stack': ['Django 6.1', 'PostgreSQL 15', 'psycopg2 (SQL puro)', 'Keyset pagination'],
            'destaques': [
                '38,5M de linhas com keyset pagination (nenhum OFFSET no código)',
                'Índices parciais (WHERE cd_matriz_filial = 1) e CTE MATERIALIZED',
                'Estatísticas pré-agregadas em c_estatisticas_totais (<5 ms)',
                'Filtro por cidade com semi-join (cnpj_basico IN ...) em 0,3 s',
            ],
            'galeria': [
                {'arquivo': 'cnpj/consulta-filtros.png',      'titulo': 'Filtros de consulta'},
                {'arquivo': 'cnpj/consulta-lista.png',        'titulo': 'Lista de empresas'},
                {'arquivo': 'cnpj/detalhe-dados.png',         'titulo': 'Detalhe: dados da empresa'},
                {'arquivo': 'cnpj/detalhe-endereco.png',      'titulo': 'Detalhe: endereço'},
                {'arquivo': 'cnpj/detalhe-estab-socios.png',  'titulo': 'Detalhe: estabelecimentos e sócios'},
            ],
            **_status_do_card('cnpj'),
        },
        {
            'id': 'chat_empresas',
            'nome': 'Chat com IA · Empresas (Receita Federal)',
            'descricao': 'Pergunte em linguagem natural sobre as empresas da RFB. Pipeline RAG (recuperação vetorial + SQL) com validação em 4 camadas e resposta ancorada nos dados.',
            'url': urls['chat_emp'],
            'repo': 'https://github.com/antoniorosasse/cnpj_interface',
            'icon': 'bi bi-chat-dots',
            'cor': 'warning',
            'imagem': 'chat-cnpj/chat-1.png',
            'stack': ['Django 6.1', 'RAG (pgvector + SQL)', 'DeepSeek', 'MongoDB 8', 'Chart.js'],
            'destaques': [
                'Pipeline SQL com 4 camadas de validação (SELECT-only, sem ;, LIMIT, sem funções perigosas)',
                'RAG: busca vetorial de CNAE (embeddings Braza, 384 dims) + linhas recuperadas como contexto do LLM',
                'Histórico em MongoDB (Repository pattern) com fallback para Postgres',
                'Texto natural + gráficos (Chart.js); recusa fora do schema (RECUSAR:)',
            ],
            'galeria': [
                {'arquivo': 'chat-cnpj/chat-1.png',          'titulo': 'Chat: perguntas, respostas, histórico'},
                {'arquivo': 'chat-cnpj/chat-resposta.png',   'titulo': 'Resposta da IA'},
                {'arquivo': 'chat-cnpj/chat-graficos.png',   'titulo': 'Gráficos'},
            ],
            **_status_do_card('chat_emp'),
        },
        {
            'id': 'as400',
            'nome': 'IBM i · DB2 · Pessoas',
            'descricao': 'CRUD completo de uma tabela de pessoas armazenadas em um banco DB2 hospedado num IBM i (AS/400) remoto (pub400.com) via JDBC.',
            'url': urls['as400'],
            'repo': 'https://github.com/antoniorosasse/as400_interface',
            'icon': 'bi bi-person-lines-fill',
            'cor': 'success',
            'imagem': 'ibmi-db2/consulta-lista.png',
            'stack': ['Django 6.0', 'JPype + jt400', 'JDBC', 'DB2 (IBM i)', 'Cache LocMem'],
            'destaques': [
                'Conexão JDBC real a um IBM i remoto (pub400.com), sem ORM',
                'CRUD completo + export CSV, com validação de CPF e de CEP existente na base',
                'Pool de conexões JDBC reutilizável e cache em memória (LocMem)',
            ],
            'galeria': [
                {'arquivo': 'ibmi-db2/consulta-filtros.png', 'titulo': 'Filtros de consulta'},
                {'arquivo': 'ibmi-db2/consulta-lista.png',   'titulo': 'Lista de pessoas'},
                {'arquivo': 'ibmi-db2/consulta-detalhe.png', 'titulo': 'Detalhe da pessoa'},
                {'arquivo': 'ibmi-db2/alteracao.png',        'titulo': 'Alteração'},
                {'arquivo': 'ibmi-db2/exclusao.png',         'titulo': 'Exclusão'},
                {'arquivo': 'ibmi-db2/api.png',              'titulo': 'API de dados'},
            ],
            **_status_do_card('as400'),
        },
        {
            'id': 'chat_pessoas',
            'nome': 'Chat com IA · Pessoas (IBM i · DB2)',
            'descricao': 'Pergunte em linguagem natural sobre os dados de pessoas do DB2 e receba a resposta em SQL executado.',
            'url': urls['chat_pes'],
            'repo': 'https://github.com/antoniorosasse/as400_interface',
            'icon': 'bi bi-robot',
            'cor': 'info',
            'imagem': 'chat-ibmi-db2/chat-1.png',
            'stack': ['Django 6.0', 'OpenAI SDK', 'DeepSeek', 'DB2 (IBM i)', 'JDBC'],
            'destaques': [
                'Tradução PT-BR -> SQL com contexto da conversa',
                'Contexto (cidade, UF, status) extraído por IA a cada interação',
                'Histórico em memória por sessão (5 interações) e fallback quando o LLM falha',
            ],
            'galeria': [
                {'arquivo': 'chat-ibmi-db2/chat-1.png',         'titulo': 'Interface do chat'},
                {'arquivo': 'chat-ibmi-db2/chat-resposta.png',  'titulo': 'Resposta da IA'},
            ],
            **_status_do_card('chat_pes'),
        },
        # ============================================================
        # CARD DA DEMONSTRACAO (o proprio site)
        # ============================================================
        # Sem health check de proposito: ele consultaria a si mesmo e
        # poderia travar um gunicorn de 1 worker. O status e' fixo.
        {
            'id': 'menu',
            'nome': 'Este site · Portfólio arosasse.tech',
            'descricao': 'A página que você está vendo: hub em Django que reúne os 4 apps, monitora a saúde de cada um e mostra a stack real de cada projeto. É a demonstração ao vivo do portfólio.',
            'url': 'https://arosasse.tech',
            'repo': 'https://github.com/antoniorosasse/menu_interface',
            'icon': 'bi bi-window-stack',
            'cor': 'secondary',
            'imagem': None,
            'demo': True,
            'stack': ['Django 5.1', 'Bootstrap 5.3', 'Gunicorn + Nginx', 'Health check (deep)', 'Dark mode'],
            'destaques': [
                'Demonstração ao vivo: este site é um dos projetos do portfólio',
                'Consome o /health/deep/ dos 3 apps (cache 60s online / 10s offline)',
                'Tema claro/escuro persistido em localStorage + prefers-color-scheme',
                'Cards e página de detalhe em Python puro (sem models, sem fixtures)',
            ],
            'galeria': [],
            'status': '🔵 Demo ao vivo',
            'status_cor': 'info',
        },
    ]

    # ============================================================
    # FAIXA DE TECNOLOGIAS (nome + onde foi usado de verdade + doc)
    # ============================================================
    # Fonte unica: o template so itera sobre esta lista. Cada 'desc' deve
    # descrever o uso REAL da tecnologia neste sistema, nao a definicao
    # generica dela (regra em .clinerules/00-projeto.md).
    tecnologias = [
        {
            'nome': 'Django 5.1 a 6.1',
            'desc': 'Framework dos 4 apps: ORM, templates, admin e middleware. '
                    'Versões diferentes por app, do 5.1 deste site ao 6.1 da consulta de CNPJ.',
            'doc': 'https://docs.djangoproject.com/',
        },
        {
            'nome': 'Python 3.13',
            'desc': 'Linguagem de todos os serviços, com um virtualenv separado por projeto.',
            'doc': 'https://docs.python.org/3.13/',
        },
        {
            'nome': 'PostgreSQL 15',
            'desc': 'Banco da base da Receita Federal: 38,5 milhões de estabelecimentos, '
                    '28 índices e CTEs materializadas para as estatísticas.',
            'doc': 'https://www.postgresql.org/docs/15/',
        },
        {
            'nome': 'MongoDB 8',
            'desc': 'Histórico do chat de empresas, acessado por Repository pattern '
                    '(com fallback para Postgres quando o Mongo não responde).',
            'doc': 'https://www.mongodb.com/docs/',
        },
        {
            'nome': 'pgvector',
            'desc': 'Busca semântica de CNAE: coluna halfvec(384) com os vetores dos '
                    'embeddings e busca por distância de cosseno — é a etapa de '
                    'recuperação do RAG do chat de empresas.',
            'doc': 'https://github.com/pgvector/pgvector',
        },
        {
            'nome': 'sentence-transformers (Braza)',
            'desc': 'Modelo de embeddings PT-BR que gera os vetores de 384 dimensões '
                    'usados na busca de CNAE.',
            'doc': 'https://sbert.net/',
        },
        {
            'nome': 'DB2 (IBM i)',
            'desc': 'Tabela PESSOAS com cerca de 500 mil linhas em um IBM i remoto '
                    '(pub400.com): consulta paginada por keyset e CRUD completo.',
            'doc': 'https://www.ibm.com/docs/en/i',
        },
        {
            'nome': 'JPype / JDBC',
            'desc': 'Ponte Python <-> JVM para falar JDBC com o DB2 a partir do Django, '
                    'sem ORM e com pool de conexões.',
            'doc': 'https://jpype.readthedocs.io/',
        },
        {
            'nome': 'DeepSeek',
            'desc': 'LLM que traduz a pergunta em PT-BR para SQL e redige a resposta '
                    'ancorada apenas nas linhas recuperadas (RAG), nos dois chats.',
            'doc': 'https://api-docs.deepseek.com/',
        },
        {
            'nome': 'OpenAI SDK',
            'desc': 'Cliente HTTP usado para chamar a API compatível do DeepSeek e '
                    'extrair o contexto da conversa.',
            'doc': 'https://platform.openai.com/docs',
        },
        {
            'nome': 'Chart.js',
            'desc': 'Gráficos montados a partir do resultado da query no chat de '
                    'empresas (o LLM escolhe o tipo de gráfico).',
            'doc': 'https://www.chartjs.org/docs/',
        },
        {
            'nome': 'Bootstrap 5.3',
            'desc': 'Layout e componentes do site, mais o tema claro/escuro por '
                    'variáveis CSS com persistência em localStorage.',
            'doc': 'https://getbootstrap.com/docs/5.3/',
        },
        {
            'nome': 'pandas / pyarrow',
            'desc': 'ETL: leitura dos Parquet da Receita Federal e carga no Postgres, '
                    'no Mongo e no DB2.',
            'doc': 'https://pandas.pydata.org/docs/',
        },
        {
            'nome': 'Gunicorn',
            'desc': 'WSGI em produção, 1 worker por serviço, gerenciado pelo systemd.',
            'doc': 'https://docs.gunicorn.org/',
        },
        {
            'nome': 'Nginx',
            'desc': 'Reverse proxy dos subdomínios, terminação TLS e entrega dos '
                    'arquivos estáticos.',
            'doc': 'https://nginx.org/en/docs/',
        },
        {
            'nome': "Let's Encrypt",
            'desc': 'Certificados TLS dos subdomínios, com renovação automática.',
            'doc': 'https://letsencrypt.org/docs/',
        },
        {
            'nome': 'Git / GitHub',
            'desc': '4 repositórios públicos com histórico de commits e README '
                    'explicando cada projeto.',
            'doc': 'https://github.com/antoniorosasse',
        },
    ]

    return {
        'projetos': projetos,
        'tecnologias': tecnologias,
        'repos_sem_card': [
            {'nome': 'ProjetoCargaDados', 'descricao': 'ETL em linha de comando: Parquet da Receita Federal -> Postgres/Mongo, e PESSOAS no DB2', 'url': 'https://github.com/antoniorosasse/ProjetoCargaDados'},
        ],
        'versao': '1.4',
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

