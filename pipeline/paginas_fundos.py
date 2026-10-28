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
from gerar import pagina  # noqa: E402

SITE = ROOT / "site"
SEV = {"crit": "Urgente", "warn": "Atenção", "mon": "Acompanhar"}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
CONECTIVOS = {"de", "da", "do", "das", "dos", "e"}
SECS = {"OPEA": "Opea", "PROVINCIA": "Província", "CANAL SEC": "Canal", "ISEC": "Virgo", "VIRGO": "Virgo",
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
    s = re.sub(r"fundo de investimento imobiliario|responsabilidade limitada|\bfii\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:50].strip("-")
    digitos = re.sub(r"\D", "", cnpj or "")[:8]
    return f"{s or 'fii'}-{digitos}"


def mapa_slugs(holdings: dict) -> dict:
    """CNPJ -> slug único. Quando dois fundos geram o mesmo ticker, os dois ganham o CNPJ no endereço."""
    fundos = {}
    for p in holdings["posicoes"]:
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
    pal = []
    for w in re.sub(r"\s+", " ", t).strip(" .,-–").split():
        lw = w.lower()
        pal.append(lw if lw in CONECTIVOS else (w.upper() if len(w) <= 3 else lw[:1].upper() + lw[1:]))
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


def data_br(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else "–"


def op_nome(o):
    t = re.sub(r"\s+\d{2}/\d{4}\s*$", "", o or "").strip()
    if not t:
        return "Operação sem nome"
    return titulo(t) if t == t.upper() else t


def gerar(saida: dict, holdings: dict) -> list[str]:
    """Escreve as páginas e devolve os caminhos (para o sitemap)."""
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
    for cnpj, pos in posicoes.items():
        info = pos[0]
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

        if evs:
            resumo = (f"{len(evs)} {'evento' if len(evs) == 1 else 'eventos'} de crédito nos CRIs da carteira "
                      f"desde {data_br(saida['janela']['inicio'])}"
                      + (f", {cont['crit']} {'urgente' if cont['crit'] == 1 else 'urgentes'}" if cont["crit"] else "") + ".")
        else:
            resumo = f"Nenhum evento de crédito nos CRIs da carteira desde {data_br(saida['janela']['inicio'])}."
        descricao = (f"{rot}: {resumo} Carteira de {len(pos)} CRIs com {pct(total_cri / pl) if pl else '–'} do PL, "
                     f"segundo o informe de {data_br(data_ref)}.")

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
            f"""<tr><td><b>{e_(p['codigo_if'] or '–')}</b><small>{e_(p['descricao'][:60])}</small></td>
        <td>{e_(p['emissao'] or '–')}ª / {e_(p['serie'] or '–')}ª</td>{f"<td>{data_br(p['vencimento'])}</td>" if tem_venc else ""}
        <td class="num">{brl(p['valor'])}</td><td class="num"><b>{pct(p['pct_pl'])}</b></td>
        <td>{'<span class="tag warn">Com evento</span>' if p['codigo_if'] and p['codigo_if'] in com_evento else ''}</td></tr>"""
            for p in sorted(pos, key=lambda x: -x["valor"])
        )

        corpo = f"""    <div class="hero compact">
      <p class="updated"><a href="/fundos.html" style="color:inherit">Fundos expostos</a> / {e_(rot)}</p>
      <h1 id="headline">{e_(rot)}{'' if not info['ticker'] else ''}</h1>
      <p id="subline">{e_(nome if info['ticker'] else 'Sem negociação em bolsa')}, gestão {e_(gestora_curta(info.get('gestor')))}. {e_(resumo)}</p>
      <div class="tally" aria-label="Eventos por severidade">
        <div><i style="background:var(--crit)"></i><b>{cont['crit']}</b><span>urgentes</span></div>
        <div><i style="background:var(--warn)"></i><b>{cont['warn']}</b><span>de atenção</span></div>
        <div><i style="background:var(--mon)"></i><b>{cont['mon']}</b><span>para acompanhar</span></div>
      </div>
    </div>
  </div>
</header>

<main class="wrap">
  <div class="grid">
    <section aria-labelledby="h-ev">
      <div class="head"><h2 id="h-ev">Eventos de crédito</h2><small>{len(evs)} {'evento' if len(evs) == 1 else 'eventos'}</small></div>
      <div class="panel"><ul class="list" style="list-style:none;margin:0;padding:0">{linhas_ev}</ul></div>
      <div class="head" style="margin-top:28px"><h2>Carteira de CRIs</h2><small>informe de {data_br(data_ref)}</small></div>
      <div class="panel tbl-wrap"><table class="rank"><thead><tr><th>Código IF</th><th>Emissão / série</th>{"<th>Vencimento</th>" if tem_venc else ""}<th class="num">Valor</th><th class="num">% do PL</th><th><span class="sr">Situação</span></th></tr></thead>
        <tbody>{linhas_pos}</tbody></table></div>
      <p class="note">Posições de CRI e CRA declaradas no informe trimestral estruturado do fundo, na CVM. Compras e vendas posteriores não aparecem.</p>
    </section>
    <aside class="side">
      <section class="panel">
        <h2>Resumo</h2>
        <div class="facts" style="grid-template-columns:1fr 1fr">
          <div><b>{brl(pl) if pl else '–'}</b><span>patrimônio líquido</span></div>
          <div><b>{pct(total_cri / pl) if pl else '–'}</b><span>do PL em CRI e CRA</span></div>
          <div><b>{len(pos)}</b><span>CRIs na carteira</span></div>
          <div><b>{len(evs)}</b><span>eventos no histórico</span></div>
        </div>
        <p class="sub" style="margin-top:12px">Gestora: {e_(gestora_curta(info.get('gestor')))}<br>Administrador: {e_(titulo(info.get('administrador') or '–'))}<br>CNPJ: {e_(cnpj)}</p>
        <button type="button" class="btn primary" id="seguir" data-cnpj="{e_(cnpj)}">Acompanhar este fundo</button>
        <p class="note" style="margin-top:8px">O fundo passa a aparecer primeiro na página de eventos. Fica salvo só neste navegador.</p>
      </section>
      <section class="panel">
        <h2>Ver no radar</h2>
        <p class="sub">Filtre a lista de eventos por este fundo, com período e severidade.</p>
        <a class="btn" href="/?q={e_(info['ticker'] or info['fundo'])}">Abrir eventos de {e_(rot)}</a>
      </section>
    </aside>
  </div>
</main>"""
        script = """const b=document.getElementById('seguir'), c=b.dataset.cnpj;
const atual=()=>new Set(store.get('rl-carteira',[]));
const pintar=()=>{const m=atual().has(c); b.textContent=m?'Acompanhando':'Acompanhar este fundo'; b.setAttribute('aria-pressed',m);};
b.addEventListener('click',()=>{const s=atual(); s.has(c)?s.delete(c):s.add(c); store.set('rl-carteira',[...s]); pintar();});
pintar();"""
        url = f"fii/{slug}/"
        titulo_pag = f"{rot}: eventos de crédito nos CRIs · Radar de Lastro"
        pasta = destino / slug
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "index.html").write_text(pagina(url, titulo_pag, descricao, corpo, script, nav="fundos"))
        urls.append(url)
        indice.append((rot, nome, url, len(evs), info["ticker"] is not None))

    # diretório com todos os fundos, para navegação e para os buscadores encontrarem as páginas
    indice.sort(key=lambda x: (not x[4], x[0]))
    itens = "".join(
        f'<li><a href="/{e_(u)}"><b class="{"tk" if t else ""}">{e_(r)}</b></a> <span class="note">{e_(n if t else "sem negociação em bolsa")}'
        f'{f", {ev} eventos" if ev > 1 else (", 1 evento" if ev == 1 else "")}</span></li>'
        for r, n, u, ev, t in indice
    )
    corpo = f"""    <div class="hero compact">
      <h1 id="headline">Todos os FIIs com CRI na carteira</h1>
      <p id="subline">{len(indice)} fundos imobiliários declararam CRI ou CRA no informe trimestral de {data_br(data_ref)}. Cada página mostra a carteira de CRIs e os eventos de crédito do fundo.</p>
    </div>
  </div>
</header>
<main class="wrap">
  <div class="panel" style="padding:18px 20px"><ul style="columns:3 260px;column-gap:28px;margin:0;padding-left:18px;line-height:1.9">{itens}</ul></div>
</main>"""
    (destino / "index.html").write_text(pagina("fii/", "Todos os FIIs com CRI · Radar de Lastro",
        f"Lista dos {len(indice)} FIIs com CRI na carteira, com links para a carteira de CRIs e os eventos de crédito de cada um.",
        corpo, "", nav="fundos"))
    urls.append("fii/")
    return urls
