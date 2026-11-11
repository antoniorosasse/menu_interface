/* ============================================================
   tema.js - alterna o tema claro/escuro nas paginas do site
   ------------------------------------------------------------
   A chave e' 'sistema-tema', a mesma do cnpj_interface e do
   as400_interface. O valor antigo 'menu-theme' e' lido como
   fallback, para nao perder a preferencia de quem ja usou o site.

   O <head> de cada template aplica o tema ANTES do CSS carregar
   (include core/_tema_head.html) para nao piscar; aqui cuidamos so
   do clique no botao e do icone.
   ============================================================ */
(function () {
    'use strict';

    var CHAVE = 'sistema-tema';
    var LEGADO = 'menu-theme';
    var html = document.documentElement;
    var botao = document.getElementById('siteTema');
    var icone = document.getElementById('siteTemaIcone');

    function atual() {
        return html.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    }

    /* data-theme = nossos estilos; data-bs-theme = Bootstrap 5.3 */
    function pinta(tema) {
        if (tema === 'dark') {
            html.setAttribute('data-theme', 'dark');
        } else {
            html.removeAttribute('data-theme');
        }
        html.setAttribute('data-bs-theme', tema);
        if (icone) {
            icone.className = tema === 'dark' ? 'bi bi-sun' : 'bi bi-moon-stars';
        }
    }

    function inicial() {
        /* ?tema=dark|light forca o tema (teste e captura de tela) */
        var q = new URLSearchParams(window.location.search).get('tema');
        if (q === 'dark' || q === 'light') { return q; }
        var salvo = localStorage.getItem(CHAVE) || localStorage.getItem(LEGADO);
        if (salvo === 'dark' || salvo === 'light') { return salvo; }
        return window.matchMedia('(prefers-color-scheme: dark)').matches
            ? 'dark'
            : 'light';
    }

    pinta(inicial());

    if (!botao) { return; }
    botao.addEventListener('click', function () {
        var novo = atual() === 'dark' ? 'light' : 'dark';
        localStorage.setItem(CHAVE, novo);
        pinta(novo);
    });
})();
