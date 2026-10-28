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

ICONE = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%23173F31'/%3E"
         "%3Cg fill='none' stroke='%23CFE6D9' stroke-width='1.6'%3E%3Ccircle cx='16' cy='16' r='10'/%3E%3Ccircle cx='16' cy='16' r='6' opacity='.6'/%3E%3C/g%3E"
         "%3Cpath d='M16 16 L24 9' stroke='%23D9A441' stroke-width='2.2' stroke-linecap='round'/%3E%3Ccircle cx='16' cy='16' r='2' fill='%23D9A441'/%3E%3C/svg%3E")

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
<meta name="theme-color" content="#173F31">
<link rel="icon" href="{icone}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<header class="band">
  <div class="rings" aria-hidden="true"><div class="sweep"></div></div>
  <div class="wrap">
    <div class="topbar">
      <a class="brand" href="index.html">
        <svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="7" fill="var(--brand-2)"/><g fill="none" stroke="var(--brand-ink)" stroke-width="1.5"><circle cx="16" cy="16" r="10.5"/><circle cx="16" cy="16" r="6.5" opacity=".55"/></g><path d="M16 16 L24 8.8" stroke="var(--seal)" stroke-width="2.2" stroke-linecap="round"/><circle cx="16" cy="16" r="2.1" fill="var(--seal)"/></svg>
        <b>Radar de Lastro</b>
      </a>
      <nav class="nav" aria-label="Páginas">
        <a href="index.html">Eventos</a><a href="fundos.html">Fundos expostos</a><a href="assembleias.html">Assembleias</a><a href="como-funciona.html">Como funciona</a>
      </nav>
    </div>
"""

FIM = """<footer>
  <div class="wrap" id="foot"><p>Fontes: Fundos.Net (B3 e CVM) e Portal de Dados Abertos da CVM.</p></div>
</footer>
<script src="assets/app.js"></script>
<script>
{script}
</script>
<!-- Cloudflare Web Analytics (sem cookies) -->
<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{{"token": "8320a7efa9a3461a9691bc75bac53d7b"}}'></script>
</body>
</html>
"""

for arquivo, (titulo, descricao) in PAGINAS.items():
    base = arquivo.removesuffix(".html")
    corpo = (AQUI / f"{base}.html").read_text()
    script = (AQUI / f"{base}.js").read_text().strip()
    html = HEAD.format(titulo=titulo, descricao=descricao, arquivo="" if arquivo == "index.html" else arquivo, icone=ICONE) + corpo.rstrip() + "\n" + FIM.format(script=script)
    (SITE / arquivo).write_text(html)
    print("gerado", arquivo)
