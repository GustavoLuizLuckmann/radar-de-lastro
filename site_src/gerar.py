"""Gera as páginas do site a partir de um cabeçalho e rodapé comuns.

Rode `python site_src/gerar.py` depois de editar qualquer arquivo em site_src/.
"""
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SITE = AQUI.parent / "site"

PAGINAS = {
    "index.html": ("Radar de Lastro", "Eventos de crédito nos CRIs da carteira dos FIIs, com dados públicos do Fundos.Net e da CVM."),
    "fundos.html": ("Fundos expostos · Radar de Lastro", "Ranking dos FIIs com mais patrimônio em CRIs que tiveram eventos de crédito."),
    "assembleias.html": ("Assembleias · Radar de Lastro", "Assembleias de titulares de CRIs que estão na carteira dos FIIs, com data e pauta."),
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
<link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32.png">
<link rel="icon" type="image/png" sizes="64x64" href="/assets/favicon-64.png">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap">
<link rel="stylesheet" href="/assets/style.css">
</head>
<body>
<header class="band">
  <div class="rings" aria-hidden="true"><div class="sweep"></div></div>
  <div class="wrap">
    <div class="topbar">
      <a class="brand" href="/">
        <img src="/assets/logo-emblema.png" alt="" width="44" height="44">
        <b>Radar de Lastro</b>
      </a>
      <nav class="nav" aria-label="Páginas">
        <a href="/"{a_index}>Eventos</a><a href="/fundos.html"{a_fundos}>Fundos expostos</a><a href="/assembleias.html"{a_assembleias}>Assembleias</a><a href="/como-funciona.html"{a_como}>Como funciona</a>
      </nav>
    </div>
"""

FIM = """<footer>
  <div class="wrap" id="foot"><p>Fontes: Fundos.Net (B3 e CVM) e Portal de Dados Abertos da CVM.</p></div>
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


def pagina(url: str, titulo: str, descricao: str, corpo: str, script: str, nav: str | None = None) -> str:
    """Monta uma página completa. `url` é o caminho a partir da raiz do site, sem barra inicial."""
    atual = {v: "" for v in NAV.values()}
    if nav in NAV:
        atual[NAV[nav]] = ' aria-current="page"'
    return HEAD.format(titulo=titulo, descricao=descricao, arquivo=url, **atual) + corpo.rstrip() + "\n" + FIM.format(script=script)


if __name__ == "__main__":
    for arquivo, (titulo, descricao) in PAGINAS.items():
        base = arquivo.removesuffix(".html")
        corpo = (AQUI / f"{base}.html").read_text()
        script = (AQUI / f"{base}.js").read_text().strip()
        html = pagina("" if arquivo == "index.html" else arquivo, titulo, descricao, corpo, script, nav=base)
        (SITE / arquivo).write_text(html)
        print("gerado", arquivo)
