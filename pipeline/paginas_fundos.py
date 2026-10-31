"""Gera uma página estática por FII em site/fii/<slug>/, para buscadores e para links diretos.

Cada página traz, já renderizados no HTML, os eventos de crédito dos CRIs do fundo e a carteira de
CRIs do informe trimestral. Assim o Google lê o conteúdo sem depender de JavaScript.
"""
import html
import re
import shutil
import sys
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "site_src"))
from gerar import cabeca, pagina  # noqa: E402

SITE = ROOT / "site"
SEV = {"crit": "Urgente", "warn": "Atenção", "mon": "Acompanhar"}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
CONECTIVOS = {"de", "da", "do", "das", "dos", "e"}
SECS = {"OPEA": "Opea", "PROVINCIA": "Província", "CANAL SEC": "Canal", "ISEC": "Riza (ex-Virgo)", "VIRGO": "Riza (ex-Virgo)", "RIZA SEC": "Riza (ex-Virgo)",
        "HABITASEC": "Habitasec", "FORTE CAP": "Forte", "BARI SEC": "Bari", "BRAZILIAN SC": "Brazilian Securities",
        "LEVERAGE SEC": "Leverage", "Lever": "Leverage", "VERTCIASEC": "Vert", "REIT SEC": "Reit",
        "TRAVESSIASEC": "Travessia", "CASAPEDRASEC": "Casa de Pedra", "PLAYBANCOSEC": "Playbanco", "ÉXES": "Éxes",
        "RBCAPITALRES": "RB Capital", "OURINVESTSEC": "Ourinvest", "PATRIA SEC": "Pátria", "OCTANTE SEC": "Octante",
        "BSIP": "BSI Capital"}

e_ = lambda s: html.escape(str(s or ""), quote=True)  # noqa: E731


def slug_fundo(ticker, nome, cnpj):
    if ticker:
        return ticker.lower()
    s = unicodedata.normalize("NFKD", nome or "fii").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"fundo de investimento imobiliario|fundo de investimento imob\w*|\bfi imobiliario\b|responsabilidade limitada|"
               r"\bresp\.? limitada\b|\bfii\b|\bfi\b|\bresp\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:50].strip("-")
    digitos = re.sub(r"\D", "", cnpj or "")[:8]
    return f"{s or 'fii'}-{digitos}"


def mapa_slugs(holdings: dict) -> dict:
    """CNPJ -> slug único. Quando dois fundos geram o mesmo ticker, os dois ganham o CNPJ no endereço."""
    fundos = {}
    for p in holdings.get("fundos", []) + holdings["posicoes"]:
        fundos.setdefault(p["cnpj_fundo"], (p["ticker"], p["fundo"]))
    base = {c: slug_fundo(t, n, c) for c, (t, n) in fundos.items()}
    repetidos = {s for s in base.values() if list(base.values()).count(s) > 1}
    return {c: (f"{s}-{re.sub(r'[^0-9]', '', c)[:8]}" if s in repetidos else s) for c, s in base.items()}


def titulo(s):
    out = []
    for w in (s or "").lower().split():
        if w in CONECTIVOS:
            out.append(w)
        elif len(w) <= 3 and w.isalpha() and w not in {"sul", "rio", "sao", "são", "paz", "mar", "sol", "lar"}:
            out.append(w.upper())
        else:
            out.append(w[:1].upper() + w[1:])
    return " ".join(out)


def nome_curto(n):
    s = re.sub(r"FUNDO DE INVESTIMENTO IMOBILI[ÁA]RIO|FUNDO DE INVESTIMENTO IMOB\.?|FUNDO DE INV\.? IMOB\.?|"
               r"RESPONSABILIDADE LIMITADA|RESP\.? LIMITADA|\bFII\b|CLASSE [ÚU]NICA", " ", n or "", flags=re.I)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"(\s+(de|da|do|das|dos|e|-|–|,))+$", "", s, flags=re.I).strip(" -–,")
    return titulo(s) or "FII"


def gestora_curta(n):
    if not n:
        return "Gestora não informada"
    t = re.sub(r"\b(LTDA|S/?A|S\.A|EIRELI)\b\.?", " ", n, flags=re.I)
    t = re.sub(r"GEST(Ã|A)O DE RECURSOS|GESTORA DE RECURSOS|ADMINISTRA(Ç|C)(Ã|A)O DE RECURSOS|ASSET MANAGEMENT|"
               r"GEST(Ã|A)O E CONSULTORIA DE INVESTIMENTOS|INVESTIMENTOS E PARTICIPA(Ç|C)(Õ|O)ES|\bGESTORA\b|"
               r"INVESTIMENTOS|\bDTVM\b|DISTRIBUIDORA DE T(Í|I)TULOS E VALORES MOBILI(Á|A)RIOS|"
               r"CORRETORA DE T(Í|I)TULOS E VALORES MOBILI(Á|A)RIOS", " ", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" .,-–")
    t = re.sub(r"^((de|da|do|das|dos|e|&)\s+)+", "", t, flags=re.I)
    t = re.sub(r"(\s+(de|da|do|das|dos|e|&))+[\s.,\-–]*$", "", t, flags=re.I).strip(" .,-–")
    pal = []
    for w in t.split():
        lw = w.lower()
        pal.append(lw if lw in CONECTIVOS else (w.upper() if len(w) <= 3 and lw not in {"rio", "sul", "mar", "sol", "paz", "lar"} else lw[:1].upper() + lw[1:]))
    return " ".join(pal) or n


def pct(x):
    if x is None:
        return "–"
    v = x * 100
    if 0 < v < 0.1:
        return "< 0,1%"
    return f"{v:.1f}".replace(".", ",") + "%"


def brl(v):
    if v >= 1e9:
        return "R$ " + f"{v / 1e9:.1f}".replace(".", ",") + " bi"
    if v >= 1e6:
        return "R$ " + f"{v / 1e6:.1f}".replace(".", ",") + " mi"
    return "R$ " + f"{v / 1e3:,.0f}".replace(",", ".") + " mil"


def mes_br(ym):
    return f"{MESES[int(ym[5:7]) - 1]}/{ym[:4]}" if ym and len(ym) >= 7 else ""


def data_br(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else "–"


def op_nome(o):
    t = re.sub(r"\s+\d{2}/\d{4}\s*$", "", o or "").strip()
    if not t:
        return "Operação sem nome"
    return titulo(t) if t == t.upper() else t


SCRIPT_FUNDO = """const b=document.getElementById('seguir'), c=b.dataset.cnpj;
const atual=()=>new Set(store.get('rl-carteira',[]));
const pintar=()=>{const m=atual().has(c); b.textContent=m?'Acompanhando':'Acompanhar este fundo'; b.setAttribute('aria-pressed',m);};
b.addEventListener('click',()=>{const s=atual(); s.has(c)?s.delete(c):s.add(c); store.set('rl-carteira',[...s]); pintar();});
pintar();
abas(document.querySelector('.tabs'), location.hash==='#carteira' ? 't-cart' : (document.querySelector('#p-ev .empty') ? 't-cart' : 't-ev'));"""


def gerar(saida: dict, holdings: dict, ops: dict | None = None) -> list[str]:
    """Escreve as páginas e devolve os caminhos (para o sitemap)."""
    from paginas_cri import EMISSORES, nome_operacao  # evita import circular
    ops = ops or {}
    destino = SITE / "fii"
    if destino.exists():
        shutil.rmtree(destino)

    eventos_por_fundo = defaultdict(list)
    for ev in saida["eventos"]:
        for f in ev["fundos"]:
            eventos_por_fundo[f["cnpj_fundo"]].append((ev, f))

    posicoes = defaultdict(list)
    for p in holdings["posicoes"]:
        posicoes[p["cnpj_fundo"]].append(p)

    data_ref = holdings["resumo"]["data_referencia"]
    slugs = mapa_slugs(holdings)
    urls, indice = [], []
    cadastro = holdings.get("fundos") or [dict(pos[0], tem_cri=True, entregou_trimestral=True) for pos in posicoes.values()]
    for info in cadastro:
        cnpj = info["cnpj_fundo"]
        pos = posicoes.get(cnpj, [])
        slug = slugs[cnpj]
        tem_venc = any(p["vencimento"] for p in pos)
        nome = nome_curto(info["fundo"])
        rot = info["ticker"] or nome
        evs = sorted(eventos_por_fundo.get(cnpj, []), key=lambda x: x[0]["data"], reverse=True)
        cont = defaultdict(int)
        for ev, _ in evs:
            cont[ev["severidade"]] += 1
        total_cri = sum(p["valor"] for p in pos)
        pl = info["pl"]
        com_evento = {c for ev, _ in evs for c in ev["codigos_if"]}

        if not pos:
            resumo = (f"Não possui CRI na carteira, segundo o informe trimestral de {data_br(data_ref)}."
                      if info.get("entregou_trimestral") else
                      f"O informe trimestral de {data_br(data_ref)} deste fundo não foi encontrado na CVM, então não há carteira de CRIs para mostrar.")
        elif evs:
            resumo = (f"{len(evs)} {'evento' if len(evs) == 1 else 'eventos'} de crédito nos CRIs da carteira "
                      f"desde {data_br(saida['janela']['inicio'])}"
                      + (f", {cont['crit']} {'urgente' if cont['crit'] == 1 else 'urgentes'}" if cont["crit"] else "") + ".")
        else:
            resumo = f"Nenhum evento de crédito nos CRIs da carteira desde {data_br(saida['janela']['inicio'])}."
        if pos:
            descricao = (f"{rot}: {resumo} Carteira de {len(pos)} CRIs com {pct(total_cri / pl) if pl else '–'} do PL, "
                         f"segundo o informe de {data_br(data_ref)}.")
        else:
            descricao = (f"{rot} ({nome}): {resumo} O Radar de Lastro acompanha eventos de crédito nos CRIs da carteira dos FIIs.")

        linhas_ev = "".join(
            f"""<li><a class="ag-row" href="/#{e_(ev['id'])}">
      <div class="cal"><b>{int(ev['data'][8:10])}</b><span>{MESES[int(ev['data'][5:7]) - 1]}</span></div>
      <div><div class="ev-top"><span class="tag {ev['severidade']}">{SEV[ev['severidade']]}</span><span class="what">{e_(ev['tipo'])}</span></div>
        <div class="who">{e_(op_nome(ev['operacao']))}, CRI da {e_(ev['emissao'])}ª emissão, {e_(SECS.get(ev['securitizadora'], titulo(ev['securitizadora'])))}</div></div>
      <span class="in">{pct(f['pct_pl'])} do PL</span>
    </a></li>"""
            for ev, f in evs[:60]
        ) or '<li class="empty"><b>Nenhum evento no período.</b>Os CRIs da carteira não tiveram fatos relevantes, avisos ou assembleias de crédito no histórico do radar.</li>'

        linhas_pos = "".join(
            f"""<tr><td>{f'<a href="/cri/{e_(p["codigo_if"])}/"><b>{e_(p["codigo_if"])}</b></a>' if p['codigo_if'] else '<b>–</b>'}<small>{e_(nome_operacao(p, ops))}</small></td>
        <td>{e_(p['emissao'] or '–')}ª / {e_(p['serie'] or '–')}ª</td>{f"<td>{data_br(p['vencimento'])}</td>" if tem_venc else ""}
        <td class="num">{brl(p['valor'])}</td><td class="num"><b>{pct(p['pct_pl'])}</b></td>
        <td>{'<span class="tag warn">Com evento</span>' if p['codigo_if'] and p['codigo_if'] in com_evento else ''}</td></tr>"""
            for p in sorted(pos, key=lambda x: -x["valor"])
        )

        # composição da carteira de CRIs por securitizadora (ou emissor)
        comp = defaultdict(float)
        for p in pos:
            comp[EMISSORES.get(p["cnpj_emissor"]) or "Outros"] += p["valor"]
        comp = sorted(comp.items(), key=lambda kv: -kv[1])
        if len(comp) > 7:
            comp = comp[:6] + [("Outros", sum(v for _, v in comp[6:]))]
        maior = (comp[0][1] if comp else 0) or 1
        linhas_comp = "".join(
            f'<li><span>{e_(n)}</span><b>{pct(v / total_cri) if total_cri else "–"}</b>'
            f'<i class="cbar"><i style="width:{v / maior * 100:.1f}%"></i></i></li>' for n, v in comp)

        sevs = (f'<span class="sevline"><i class="crit"></i>{cont["crit"]} {"urgente" if cont["crit"] == 1 else "urgentes"}'
                f'<i class="warn"></i>{cont["warn"]} de atenção<i class="mon"></i>{cont["mon"]} para acompanhar</span>')
        kpis = f"""<div class="kpis">
      <div><span>Patrimônio líquido</span><b>{brl(pl) if pl else '–'}</b><small>{'informe de ' + mes_br(info.get('data_pl')) if info.get('data_pl') else 'mês do informe'}</small></div>
      <div><span>Em CRI</span><b>{(pct(total_cri / pl) if pl else '–') if pos else '0%'}</b><small>{brl(total_cri) if pos else 'nenhum CRI declarado'}</small></div>
      <div><span>CRIs na carteira</span><b>{len(pos)}</b><small>informe de {data_br(data_ref)}</small></div>
      <div><span>Eventos de crédito</span><b>{len(evs)}</b><small>desde {data_br(saida['janela']['inicio'])}</small></div>
    </div>"""
        sub = (f"{e_(nome) if info['ticker'] else 'Sem negociação em bolsa'}. Gestão {e_(gestora_curta(info.get('gestor')))}."
               f" {e_(resumo)}")
        cab = cabeca(
            f'{e_(rot)}<span class="ph-badge">{"FII" if info["ticker"] else "FII de balcão"}</span>'
            + ('' if pos else '<span class="ph-badge neutro">Sem CRI</span>'), sub,
            trilha=f'<a href="/fii/">Fundos</a><span aria-hidden="true">/</span><span>{e_(rot)}</span>',
            extra=kpis + (f'<p class="ph-sev">{sevs}</p>' if evs else ""),
            lado='<button type="button" class="btn primary" id="seguir" data-cnpj="' + e_(cnpj) + '">Acompanhar este fundo</button>')

        ficha = f"""<section class="panel">
        <h2>Ficha</h2>
        <dl class="ficha">
          <div><dt>Gestora</dt><dd>{e_(gestora_curta(info.get('gestor')))}</dd></div>
          <div><dt>Administrador</dt><dd>{e_(gestora_curta(info.get('administrador')) if info.get('administrador') else '–')}</dd></div>
          {f"<div><dt>Segmento</dt><dd>{e_(info['segmento'])}</dd></div>" if info.get('segmento') else ''}
          <div><dt>CNPJ</dt><dd>{e_(cnpj)}</dd></div>
          <div><dt>Negociação</dt><dd>{'Bolsa (B3), código ' + e_(info['ticker']) if info['ticker'] else 'Sem negociação em bolsa'}</dd></div>
        </dl>
        {f'<a class="btn" style="margin-top:14px" href="/?q={e_(info["ticker"] or info["fundo"])}">Filtrar eventos de {e_(rot)} no radar</a>' if pos else ''}
      </section>"""
        if not pos:
            motivo = ("não declarou CRI" if info.get("entregou_trimestral")
                      else "não tem informe trimestral disponível na CVM")
            corpo = cab + f"""<main class="wrap">
  <div class="grid">
    <section class="panel vazio" aria-labelledby="h-sem">
      <h2 id="h-sem">Este fundo não tem CRI na carteira</h2>
      <p>O {e_(rot)} {motivo} no informe trimestral de {data_br(data_ref)}. Por isso não há eventos de crédito de CRI para acompanhar aqui.</p>
      <p>O Radar de Lastro acompanha inadimplência, assembleias e outros eventos dos CRIs que estão na carteira dos FIIs. Se o fundo passar a ter CRIs, eles aparecem nesta página depois do próximo informe trimestral.</p>
      <div class="links" style="margin-top:14px"><a class="btn primary" href="/fundos.html">Ver fundos com eventos</a><a class="btn" href="/fii/">Todos os FIIs</a></div>
    </section>
    <aside class="side">
      {ficha}
    </aside>
  </div>
</main>"""
        else:
            corpo = cab + f"""<main class="wrap">
  <div class="tabs" role="tablist" aria-label="Seções do fundo">
    <button type="button" role="tab" id="t-ev" aria-controls="p-ev" aria-selected="true">Eventos de crédito <span>{len(evs)}</span></button>
    <button type="button" role="tab" id="t-cart" aria-controls="p-cart" aria-selected="false">Carteira de CRIs <span>{len(pos)}</span></button>
  </div>
  <div class="grid">
    <div>
      <section id="p-ev" role="tabpanel" aria-labelledby="t-ev">
        <div class="panel"><ul class="list" style="list-style:none;margin:0;padding:0">{linhas_ev}</ul></div>
      </section>
      <section id="p-cart" role="tabpanel" aria-labelledby="t-cart">
        <div class="panel tbl-wrap"><table class="rank"><thead><tr><th>CRI</th><th>Emissão / série</th>{"<th>Vencimento</th>" if tem_venc else ""}<th class="num">Valor</th><th class="num">% do PL</th><th><span class="sr">Situação</span></th></tr></thead>
          <tbody>{linhas_pos}</tbody></table></div>
        <p class="note">Posições de CRI declaradas no informe trimestral estruturado do fundo, na CVM, em {data_br(data_ref)}. Compras e vendas posteriores não aparecem.</p>
      </section>
    </div>
    <aside class="side">
      <section class="panel">
        <h2>Carteira de CRIs por securitizadora</h2>
        <p class="sub">Parte do valor em CRI de cada emissor.</p>
        <ul class="comp">{linhas_comp}</ul>
      </section>
      {ficha}
    </aside>
  </div>
</main>"""
        script = SCRIPT_FUNDO
        url = f"fii/{slug}/"
        titulo_pag = f"{rot}: eventos de crédito nos CRIs · Radar de Lastro"
        pasta = destino / slug
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "index.html").write_text(pagina(url, titulo_pag, descricao, corpo, script, nav="fundos"))
        urls.append(url)
        indice.append((rot, nome, url, len(evs), info["ticker"] is not None, len(pos)))

    # diretório com todos os fundos, para navegação e para os buscadores encontrarem as páginas
    indice.sort(key=lambda x: (not x[4], x[0]))
    itens = "".join(
        f'<li><a href="/{e_(u)}"><b class="{"tk" if t else ""}">{e_(r)}</b></a> <span class="note">{e_(n if t else "sem negociação em bolsa")}'
        f'{f", {ev} eventos" if ev > 1 else (", 1 evento" if ev == 1 else "")}{"" if nc else ", sem CRI"}</span></li>'
        for r, n, u, ev, t, nc in indice
    )
    corpo = cabeca("Todos os FIIs",
                   f"{len(indice)} fundos imobiliários: todos os negociados em bolsa e os de balcão com CRI na carteira. "
                   f"{sum(1 for x in indice if x[5])} deles declararam CRI no informe trimestral de {data_br(data_ref)}.",
                   trilha='<a href="/">Início</a><span aria-hidden="true">/</span><span>Fundos</span>') + f"""<main class="wrap">
  <div class="panel" style="padding:18px 20px"><ul style="columns:3 260px;column-gap:28px;margin:0;padding-left:18px;line-height:1.9">{itens}</ul></div>
</main>"""
    (destino / "index.html").write_text(pagina("fii/", "Todos os FIIs · Radar de Lastro",
        f"Lista de {len(indice)} FIIs, com a carteira de CRIs e os eventos de crédito de cada um.",
        corpo, "", nav="fundos"))
    return urls
