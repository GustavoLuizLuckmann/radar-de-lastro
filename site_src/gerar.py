"""Gera as páginas do site a partir de um cabeçalho e rodapé comuns.

Rode `python site_src/gerar.py` depois de editar qualquer arquivo em site_src/.
"""
import re
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SITE = AQUI.parent / "site"

PAGINAS = {
    "index.html": ("Radar de Lastro: eventos de crédito nos CRIs dos FIIs",
                   "Acompanhe inadimplência, assembleias, waivers e vencimento antecipado dos CRIs na carteira dos FIIs, "
                   "com o peso de cada um no PL do fundo. Dados públicos do Fundos.Net e da CVM, atualizados de hora em hora."),
    "fundos.html": ("Fundos expostos · Radar de Lastro", "Ranking dos FIIs com mais patrimônio em CRIs que tiveram eventos de crédito."),
    "assembleias.html": ("Próximas assembleias · Radar de Lastro", "Próximas assembleias de titulares de CRIs que estão na carteira dos FIIs, com data, pauta e fundos expostos."),
    "sobre.html": ("Sobre · Radar de Lastro", "O que é o Radar de Lastro, o problema que resolve, para quem é e de onde vêm os dados."),
    "termos.html": ("Termos de uso · Radar de Lastro", "Condições de uso do Radar de Lastro: informação pública, sem recomendação de investimento."),
    "privacidade.html": ("Privacidade · Radar de Lastro", "Como o Radar de Lastro trata dados: sem cadastro, sem cookies de rastreamento, preferências só no navegador."),
    "como-funciona.html": ("Como funciona · Radar de Lastro", "De onde vêm os dados do Radar de Lastro, como os eventos são classificados e o que cada um significa."),
}

HEAD = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{titulo}</title>
<meta name="description" content="{descricao}">
<meta property="og:title" content="{titulo}">
<meta property="og:description" content="{descricao}">
<meta property="og:type" content="website">
<meta property="og:url" content="https://radardelastro.com.br/{arquivo}">
<link rel="canonical" href="https://radardelastro.com.br/{arquivo}">
<meta property="og:image" content="https://radardelastro.com.br/assets/og.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0C2E54">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" type="image/png" sizes="96x96" href="/assets/favicon-96.png">
<link rel="icon" type="image/png" sizes="192x192" href="/assets/favicon-192.png">
<link rel="manifest" href="/site.webmanifest">{dados_estruturados}
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap">
<link rel="stylesheet" href="/assets/style.css">
</head>
<body class="pg-{pg}">
<a class="skip" href="#conteudo">Pular para o conteúdo</a>
<header class="band">
{aneis}
  <div class="wrap">
    <div class="topbar">
      <a class="brand" href="/">
        <img src="/assets/logo-emblema.png" alt="" width="44" height="44">
        <b>Radar de Lastro</b>
      </a>
      <form class="gsearch" role="search" action="/" method="get" autocomplete="off">
        <label for="gq" class="sr">Buscar fundo ou CRI</label>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
        <input id="gq" name="q" type="search" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="gq-list" placeholder="Buscar FII ou CRI">
        <kbd aria-hidden="true">/</kbd>
        <ul id="gq-list" class="gq-list" role="listbox" aria-label="Resultados" hidden></ul>
      </form>
      <nav class="nav" aria-label="Páginas">
        <a href="/"{a_index}>Eventos</a><a href="/fundos.html"{a_fundos}>Fundos expostos</a><a href="/assembleias.html"{a_assembleias}>Próximas assembleias</a><a href="/como-funciona.html"{a_como}>Como funciona</a>
      </nav>
    </div>
{fecha_header}"""

FIM = """<footer class="rodape">
  <div class="wrap">
    <div class="cols">
      <div class="col-marca">
        <a class="brand" href="/"><img src="/assets/logo-emblema.png" alt="" width="36" height="36"><b>Radar de Lastro</b></a>
        <p>Eventos de crédito nos CRIs da carteira dos FIIs, com dados públicos do Fundos.Net e da CVM, atualizados de hora em hora.</p>
      </div>
      <nav aria-label="Radar"><h2>Radar</h2><a href="/">Eventos</a><a href="/fundos.html">Fundos expostos</a><a href="/assembleias.html">Próximas assembleias</a><a href="/fii/">Todos os FIIs com CRI</a></nav>
      <nav aria-label="Dados"><h2>Dados</h2><a href="/como-funciona.html">Como funciona</a><a href="/como-funciona.html#limitacoes">Limitações</a><a href="https://dados.cvm.gov.br/" target="_blank" rel="noopener">Dados abertos da CVM</a><a href="https://fnet.bmfbovespa.com.br/fnet/publico/abrirGerenciadorDocumentosCVM" target="_blank" rel="noopener">Fundos.Net</a></nav>
      <nav aria-label="Institucional"><h2>Institucional</h2><a href="/sobre.html">Sobre</a><a href="/termos.html">Termos de uso</a><a href="/privacidade.html">Privacidade</a></nav>
    </div>
    <div class="legal" id="foot"><p>O Radar de Lastro reúne informação pública e não faz recomendação de investimento. Não tem relação com a B3 nem com a CVM.</p></div>
  </div>
</footer>
<script src="/assets/app.js"></script>
<script>
{script}
</script>
<!-- Cloudflare Web Analytics (sem cookies) -->
<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{{"token": "8320a7efa9a3461a9691bc75bac53d7b"}}'></script>
</body>
</html>
"""

NAV = {"index": "a_index", "fundos": "a_fundos", "assembleias": "a_assembleias", "como-funciona": "a_como"}
ANEIS = '  <div class="rings-clip" aria-hidden="true"><div class="rings"><div class="sweep"></div></div></div>'
HERO_ANTIGO = re.compile(r'\s*<div class="hero compact">\n(.*?)\n    </div>\n  </div>\n</header>\n', re.S)


def cabeca(titulo_h1: str, sub: str = "", trilha: str = "", extra: str = "", lado: str = "") -> str:
    """Cabeçalho claro das páginas internas: trilha, título, subtítulo e, opcionalmente, indicadores."""
    return f"""<section class="pagehead" id="conteudo">
  <div class="wrap">
    {f'<nav class="crumbs" aria-label="Você está em">{trilha}</nav>' if trilha else ''}
    <div class="ph-top">
      <div class="ph-id"><h1 id="headline">{titulo_h1}</h1>{f'<p class="ph-sub" id="subline">{sub}</p>' if sub else ''}</div>
      {lado}
    </div>
    {extra}
  </div>
</section>
"""


def pagina(url: str, titulo: str, descricao: str, corpo: str, script: str, nav: str | None = None) -> str:
    """Monta uma página completa. `url` é o caminho a partir da raiz do site, sem barra inicial."""
    atual = {v: "" for v in NAV.values()}
    if nav in NAV:
        atual[NAV[nav]] = ' aria-current="page"'
    # na página inicial, dados estruturados com nome do site, logo e caixa de busca para o Google
    dados = ""
    if url == "":
        dados = """
<script type="application/ld+json">
{{"@context":"https://schema.org","@graph":[
 {{"@type":"WebSite","@id":"https://radardelastro.com.br/#site","name":"Radar de Lastro","url":"https://radardelastro.com.br/","inLanguage":"pt-BR",
   "potentialAction":{{"@type":"SearchAction","target":"https://radardelastro.com.br/?q={{search_term_string}}","query-input":"required name=search_term_string"}}}},
 {{"@type":"Organization","@id":"https://radardelastro.com.br/#org","name":"Radar de Lastro","url":"https://radardelastro.com.br/","logo":"https://radardelastro.com.br/assets/favicon-512.png"}}
]}}
</script>""".format()
    inicio = nav == "index"
    if not inicio:
        # páginas internas: faixa azul só com logo, busca e menu; o título vai para um cabeçalho claro
        m = HERO_ANTIGO.match(corpo)
        if m:
            corpo = '<section class="pagehead" id="conteudo">\n  <div class="wrap">\n' + m.group(1) + '\n  </div>\n</section>\n' + corpo[m.end():]
    cab = HEAD.format(titulo=titulo, descricao=descricao, arquivo=url, dados_estruturados=dados, pg=nav or "outra",
                      aneis=ANEIS if inicio else "", fecha_header="" if inicio else "  </div>\n</header>\n", **atual)
    return cab + corpo.rstrip() + "\n" + FIM.format(script=script)


if __name__ == "__main__":
    for arquivo, (titulo, descricao) in PAGINAS.items():
        base = arquivo.removesuffix(".html")
        corpo = (AQUI / f"{base}.html").read_text()
        script = (AQUI / f"{base}.js").read_text().strip()
        html = pagina("" if arquivo == "index.html" else arquivo, titulo, descricao, corpo, script, nav=base)
        (SITE / arquivo).write_text(html)
        print("gerado", arquivo)
