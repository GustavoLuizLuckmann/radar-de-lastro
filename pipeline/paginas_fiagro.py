"""Páginas dos Fiagros (/fiagro/<slug>/) e dos CRAs com evento (/cra/<ISIN>/).

A CVM não divulga o código dos CRAs na carteira de cada Fiagro. Por isso a página do Fiagro mostra a
composição declarada no informe mensal (quanto há em CRA, CRI, CPR e outros) e os eventos de crédito
das operações citadas no relatório gerencial mais recente do fundo.
"""
import re
import shutil
import unicodedata
from collections import Counter, defaultdict

from paginas_fundos import (MESES, SECS, SEV, SITE, brl, data_br, e_, gestora_curta, mes_br, op_nome, pct,
                            titulo)
from paginas_cri import EMISSORES, emissor_curto  # noqa: E402
from gerar import cabeca, pagina  # noqa: E402  (paginas_fundos põe site_src no caminho)

URL_FNET = "https://fnet.bmfbovespa.com.br/fnet/publico/exibirDocumento?id={id}&cvm=true"
METODO = {"carteira": "Na carteira entregue à CVM (CDA)", "codigo": "Código do CRA citado no relatório gerencial",
          "nome": "Devedor citado no relatório gerencial (pode ser outra série)"}

SCRIPT_FIAGRO = """const b=document.getElementById('seguir'), c=b.dataset.cnpj;
const atual=()=>new Set(store.get('rl-carteira',[]));
const pintar=()=>{const m=atual().has(c); b.textContent=m?'Acompanhando':'Acompanhar este fundo'; b.setAttribute('aria-pressed',m);};
b.addEventListener('click',()=>{const s=atual(); s.has(c)?s.delete(c):s.add(c); store.set('rl-carteira',[...s]); pintar();});
pintar();
abas(document.querySelector('.tabs'), location.hash==='#composicao' || document.querySelector('#p-ev .empty') ? 't-comp' : 't-ev');"""


# securitizadoras de CRA mais comuns nos CDAs (o nome no CDA vem truncado ou com acentos quebrados)
SEC_CRA = {"10753164000143": "Eco Securitizadora", "08769451000108": "Riza (ex-Virgo)", "02773542000122": "Opea",
           "11945604000127": "Opea", "25005683000109": "Vert", "12130744000100": "True Securitizadora",
           "04200649000107": "Província", "41811375000119": "Canal", "41534746000162": "Ceres",
           "55085811000124": "Éxes", "26609050000164": "Travessia", "14876090000193": "Gaia"}
INDEXADOR = {"DI1": "CDI", "CDI": "CDI", "IAP": "IPCA", "IPC": "IPCA", "IGP": "IGP-M", "PRE": "Pré"}


def emissor_cra(c):
    if c["cnpj_emissor"] in SEC_CRA:
        return SEC_CRA[c["cnpj_emissor"]]
    if c["cnpj_emissor"] in EMISSORES:
        return EMISSORES[c["cnpj_emissor"]]
    return emissor_curto(re.sub(r"SECURITIZ\S*(\s+O\b)?", "SECURITIZADORA", c["emissor"], flags=re.I))


def taxa_cra(c):
    idx = INDEXADOR.get((c.get("indexador") or "").upper(), "")
    cup = f"{c['cupom']:.2f}".replace(".", ",") + "%" if c.get("cupom") else ""
    return f"{idx} + {cup}" if idx and cup and idx != "Pré" else (f"{cup} a.a." if cup else idx)


def nome_fiagro(n):
    s = re.sub(r"\b(FUNDO DE INVESTIMENTO|F\.? ?I\.?)\s+(NAS|EM)\s+CADEIAS(\s+PROD\w*)?(\s+(DO\s+)?AGRO\w*)?|"
               r"\bNAS\s+CADEIAS(\s+PROD\w*)?(\s+(DO\s+)?AGRO\w*)?|"
               r"RESPONSABILIDAD\w*\s+LI\w*|\bRESP\.?\s+LIM\w*\.?|\bR\.?\s*L\.?$|\bLIMITADA\b|CLASSE [ÚU]NICA( D[OE])?|\bCLASSE\b|"
               r"\bFUNDO DE INVESTIMENTO\b", " ", n or "", flags=re.I)
    s = re.sub(r"\s+", " ", s).strip(" -–,")
    s = re.sub(r"(\s+(de|da|do|das|dos|e|-|–|,))+$", "", s, flags=re.I).strip(" -–,")
    s = re.sub(r"^(de|da|do)\s+", "", s, flags=re.I)
    if s and "FIAGRO" not in s.upper() and len(s.split()) <= 2:
        s += " Fiagro"
    return titulo(s) or "Fiagro"


def slug_fiagro(ticker, nome, cnpj):
    if ticker:
        return ticker.lower()
    s = unicodedata.normalize("NFKD", nome_fiagro(nome)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\bfiagro\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:50].strip("-")
    return f"{s or 'fiagro'}-{re.sub(r'[^0-9]', '', cnpj or '')[:8]}"


def mapa_slugs_fiagro(fg: dict) -> dict:
    base = {f["cnpj_fundo"]: slug_fiagro(f["ticker"], f["fundo"], f["cnpj_fundo"]) for f in fg.get("fundos", [])}
    cont = Counter(base.values())
    return {c: (f"{s}-{re.sub(r'[^0-9]', '', c)[:8]}" if cont[s] > 1 else s) for c, s in base.items()}


def sec_nome(s):
    return SECS.get(s, titulo(s or ""))


def lastro_txt(ev):
    return f"{ev.get('lastro') or 'CRI'} da {ev['emissao']}ª emissão, {sec_nome(ev['securitizadora'])}"


def chave_cra(ev):
    return ev.get("isin") or f"{re.sub(r'[^A-Z0-9]', '', ev['securitizadora'].upper())}-{ev['emissao']}-{ev['serie']}"


def linha_evento(ev, direita):
    return f"""<li><a class="ag-row" href="/#{e_(ev['id'])}">
      <div class="cal"><b>{int(ev['data'][8:10])}</b><span>{MESES[int(ev['data'][5:7]) - 1]}</span></div>
      <div><div class="ev-top"><span class="tag {ev['severidade']}">{SEV[ev['severidade']]}</span><span class="what">{e_(ev['tipo'])}</span></div>
        <div class="who">{e_(op_nome(ev['operacao']))}, {e_(lastro_txt(ev))}</div></div>
      <span class="in">{direita}</span>
    </a></li>"""


def gerar(saida: dict, fg: dict):
    destino = SITE / "fiagro"
    if destino.exists():
        shutil.rmtree(destino)
    slugs = mapa_slugs_fiagro(fg)
    eventos = defaultdict(list)
    for ev in saida["eventos"]:
        for f in ev["fundos"]:
            if f.get("tf") == "fiagro":
                eventos[f["cnpj_fundo"]].append((ev, f))
    inicio = data_br(saida["janela"]["inicio"])
    urls, busca, indice = [], [], []
    for info in fg.get("fundos", []):
        cnpj, slug = info["cnpj_fundo"], slugs[info["cnpj_fundo"]]
        nome = nome_fiagro(info["fundo"])
        rot = info["ticker"] or nome
        pl = info.get("pl") or 0
        g = info.get("gerencial") or {}
        evs = sorted(eventos.get(cnpj, []), key=lambda x: x[0]["data"], reverse=True)
        cont = Counter(ev["severidade"] for ev, _ in evs)
        venc = info["vencidos"] / info["prazo_total"] if info.get("prazo_total") else None

        if evs:
            resumo = (f"{len(evs)} {'evento' if len(evs) == 1 else 'eventos'} de crédito em CRAs da carteira ou citados no relatório gerencial"
                      + (f", {cont['crit']} {'urgente' if cont['crit'] == 1 else 'urgentes'}" if cont["crit"] else "") + ".")
        elif info["cra"] + info["cri"] <= 0:
            resumo = "Não declarou CRA nem CRI no informe mensal."
        elif g.get("valido"):
            resumo = f"Nenhum evento de crédito nos CRAs identificados na carteira desde {inicio}."
        else:
            resumo = "Sem relatório gerencial recente no Fundos.Net para ligar eventos de crédito ao fundo."

        comp = sorted(info.get("composicao", {}).items(), key=lambda kv: -kv[1])
        maior = (comp[0][1] if comp else 0) or 1
        linhas_comp = "".join(
            f'<li><span>{e_(n)}</span><b>{pct(v / pl) if pl else brl(v)}</b><i class="cbar"><i style="width:{min(100, v / maior * 100):.1f}%"></i></i></li>'
            for n, v in comp) or '<li><span>Nada declarado</span><b>–</b></li>'

        cda = info.get("cda") or {}
        cras = sorted(cda.get("cras", []), key=lambda c: -c["valor"])
        pl_cda = cda.get("pl") or pl
        tabela_cras = ""
        if cras:
            ident = sum(1 for c in cras if c.get("codigos"))
            linhas_cra = "".join(
                f"""<tr><td><b>{e_(next((x for x in c.get('codigos', []) if x.startswith('CRA')), '') or 'Não identificado')}</b>
          <small>{e_(emissor_cra(c))}{(', ' + e_(c['emissao']) + 'ª emissão') if c.get('emissao') else ''}{(', série ' + e_(c['serie'])) if c.get('serie') else ''}</small></td>
          <td>{data_br(c['venc'])}<small>{e_(taxa_cra(c))}</small></td>
          <td class="num">{brl(c['valor'])}</td><td class="num"><b>{pct(c['valor'] / pl_cda) if pl_cda else '–'}</b></td></tr>"""
                for c in cras[:80])
            tabela_cras = f"""<div class="panel tbl-wrap" style="margin-top:20px">
          <h2 style="padding:16px 18px 0">CRAs na carteira</h2>
          <p class="sub" style="padding:0 18px">Composição da carteira (CDA) de {e_(cda.get('referencia') or '–')} entregue à CVM: {len(cras)} CRAs, {ident} com o código identificado pelo informe das securitizadoras.</p>
          <table class="rank"><thead><tr><th>CRA</th><th>Vencimento</th><th class="num">Valor</th><th class="num">% do PL</th></tr></thead><tbody>{linhas_cra}</tbody></table>
        </div>"""

        linhas_ev = "".join(linha_evento(ev, (pct(f["pct_pl"]) + " do PL") if f.get("pct_pl") is not None
                                         else "código citado" if f.get("metodo") == "codigo" else "devedor citado")
                            for ev, f in evs[:60]) or (
            f'<li class="empty"><b>Nenhum evento no período.</b>As operações citadas no relatório gerencial não tiveram fatos relevantes, avisos ou assembleias de crédito desde {inicio}.</li>'
            if g.get("valido") else
            '<li class="empty"><b>Sem relatório gerencial recente.</b>Sem um relatório dos últimos meses no Fundos.Net, o radar não tem como saber quais CRAs este Fiagro tem. A composição ao lado vem do informe mensal da CVM.</li>')

        kpis = f"""<div class="kpis">
      <div><span>Patrimônio líquido</span><b>{brl(pl) if pl else '–'}</b><small>informe de {mes_br(info.get('data_pl'))}</small></div>
      <div><span>Em CRA</span><b>{pct(info['cra'] / pl) if pl else '–'}</b><small>{brl(info['cra']) if info['cra'] else 'nenhum CRA declarado'}</small></div>
      <div><span>Carteira vencida</span><b>{pct(venc) if venc is not None else '–'}</b><small>{'dos ativos com prazo' if venc is not None else 'sem ativos com prazo'}</small></div>
      <div><span>Eventos de crédito</span><b>{len(evs)}</b><small>desde {inicio}</small></div>
    </div>"""
        sevs = (f'<span class="sevline"><i class="crit"></i>{cont["crit"]} {"urgente" if cont["crit"] == 1 else "urgentes"}'
                f'<i class="warn"></i>{cont["warn"]} de atenção<i class="mon"></i>{cont["mon"]} para acompanhar</span>')
        sub = f"{e_(nome) if info['ticker'] else 'Sem código de negociação identificado'}. Gestão {e_(gestora_curta(info.get('gestor')))}. {e_(resumo)}"
        cab = cabeca(
            f'{e_(rot)}<span class="ph-badge">Fiagro</span>' + ('' if info["ticker"] else '<span class="ph-badge neutro">Sem ticker</span>'),
            sub, trilha=f'<a href="/fiagro/">Fiagros</a><span aria-hidden="true">/</span><span>{e_(rot)}</span>',
            extra=kpis + (f'<p class="ph-sev">{sevs}</p>' if evs else ""),
            lado='<button type="button" class="btn primary" id="seguir" data-cnpj="' + e_(cnpj) + '">Acompanhar este fundo</button>')

        rel = (f"""<p>Relatório gerencial{(' de ' + e_(g['referencia'])) if g.get('referencia') else ''}, entregue em {data_br(g['data_entrega'])}.</p>
        <a class="btn" style="margin-top:10px" href="{URL_FNET.format(id=int(g['doc_id']))}" target="_blank" rel="noopener noreferrer">Abrir no Fundos.Net</a>"""
               if g.get("doc_id") and g.get("data_entrega") else "<p>Nenhum relatório gerencial encontrado no Fundos.Net.</p>")
        ficha = f"""<section class="panel">
        <h2>De onde vêm os eventos</h2>
        <p class="sub">A carteira entregue à CVM (CDA) não traz o código dos CRAs. O radar cruza securitizadora, vencimento e taxa de cada CRA com o informe das securitizadoras para chegar ao código. Quando não fecha, procura a operação no relatório gerencial mais recente.</p>
        {f"<p>Carteira (CDA) de {e_(cda.get('referencia'))}.</p>" if cda.get('referencia') else ''}
        {rel}
      </section>
      <section class="panel">
        <h2>Ficha</h2>
        <dl class="ficha">
          <div><dt>Gestora</dt><dd>{e_(gestora_curta(info.get('gestor')))}</dd></div>
          <div><dt>Administrador</dt><dd>{e_(gestora_curta(info.get('administrador')) if info.get('administrador') else '–')}</dd></div>
          <div><dt>CNPJ</dt><dd>{e_(cnpj)}</dd></div>
          <div><dt>Negociação</dt><dd>{'Bolsa (B3), código ' + e_(info['ticker']) if info['ticker'] else 'Código de negociação não identificado'}</dd></div>
          {f"<div><dt>Cotistas</dt><dd>{info['cotistas']:,}</dd></div>".replace(',', '.') if info.get('cotistas') else ''}
          {f"<div><dt>Vencido há mais de 90 dias</dt><dd>{brl(info['vencidos_90'])}</dd></div>" if info.get('vencidos_90') else ''}
        </dl>
      </section>"""
        corpo = cab + f"""<main class="wrap">
  <div class="tabs" role="tablist" aria-label="Seções do fundo">
    <button type="button" role="tab" id="t-ev" aria-controls="p-ev" aria-selected="true">Eventos de crédito <span>{len(evs)}</span></button>
    <button type="button" role="tab" id="t-comp" aria-controls="p-comp" aria-selected="false">Composição da carteira</button>
  </div>
  <div class="grid">
    <div>
      <section id="p-ev" role="tabpanel" aria-labelledby="t-ev">
        <div class="panel"><ul class="list" style="list-style:none;margin:0;padding:0">{linhas_ev}</ul></div>
        <p class="note">“% do PL”: o CRA está na carteira entregue à CVM, identificado pelo informe das securitizadoras. “Código citado”: o código do CRA aparece no relatório gerencial. “Devedor citado”: aparece o nome do devedor, que pode ter outros CRAs.</p>
      </section>
      <section id="p-comp" role="tabpanel" aria-labelledby="t-comp">
        <div class="panel">
          <h2>Composição por tipo de ativo</h2>
          <p class="sub">Parte do patrimônio líquido em cada tipo de ativo, segundo o informe mensal de {mes_br(info.get('data_pl'))}.</p>
          <ul class="comp">{linhas_comp}</ul>
        </div>
        <p class="note">Informe mensal de Fiagro, dados abertos da CVM. “Carteira vencida” é a parte dos ativos com prazo que já passou do vencimento sem ser paga.</p>
        {tabela_cras}
      </section>
    </div>
    <aside class="side">
      {ficha}
    </aside>
  </div>
</main>"""
        url = f"fiagro/{slug}/"
        descricao = (f"{rot}: {resumo} {pct(info['cra'] / pl) if pl else '–'} do patrimônio em CRA, segundo o informe mensal de "
                     f"{mes_br(info.get('data_pl'))}. O Radar de Lastro acompanha eventos de crédito dos CRAs e CRIs dos Fiagros.")
        (destino / slug).mkdir(parents=True, exist_ok=True)
        (destino / slug / "index.html").write_text(
            pagina(url, f"{rot}: eventos de crédito nos CRAs · Radar de Lastro", descricao, corpo, SCRIPT_FIAGRO, nav="fiagro"))
        urls.append(url)
        indice.append((rot, nome, url, len(evs), bool(info["ticker"]), info["cra"] > 0))
        busca.append({"t": "f", "tp": "Fiagro", "k": info["ticker"] or "", "n": nome, "s": gestora_curta(info.get("gestor")),
                      "u": "/" + url, "c": 0, "cra": round(info["cra"] / pl, 4) if pl else 0, "e": len(evs)})

    indice.sort(key=lambda x: (not x[4], x[0]))
    itens = "".join(
        f'<li><a href="/{e_(u)}"><b class="{"tk" if t else ""}">{e_(r)}</b></a> <span class="note">{e_(n if t else "sem ticker")}'
        f'{f", {ev} eventos" if ev > 1 else (", 1 evento" if ev == 1 else "")}{"" if cra else ", sem CRA"}</span></li>'
        for r, n, u, ev, t, cra in indice)
    ref = mes_br(fg.get("data_referencia"))
    corpo = cabeca("Todos os Fiagros",
                   f"{len(indice)} Fiagros: os negociados em bolsa e os de balcão com CRA ou CRI na carteira. "
                   f"{sum(1 for x in indice if x[5])} deles declararam CRA no informe mensal de {ref}.",
                   trilha='<a href="/">Início</a><span aria-hidden="true">/</span><span>Fiagros</span>') + f"""<main class="wrap">
  <div class="panel" style="padding:18px 20px"><ul style="columns:3 260px;column-gap:28px;margin:0;padding-left:18px;line-height:1.9">{itens}</ul></div>
</main>"""
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "index.html").write_text(pagina("fiagro/", "Todos os Fiagros · Radar de Lastro",
        f"Lista de {len(indice)} Fiagros, com a composição da carteira e os eventos de crédito dos CRAs de cada um.",
        corpo, "", nav="fiagro"))
    return urls, busca


def gerar_cras(saida: dict, fg: dict):
    """Uma página por operação de CRA com evento no histórico."""
    destino = SITE / "cra"
    if destino.exists():
        shutil.rmtree(destino)
    slugs = mapa_slugs_fiagro(fg)
    grupos = defaultdict(list)
    for ev in saida["eventos"]:
        if ev.get("lastro") == "CRA":
            grupos[chave_cra(ev)].append(ev)
    urls, busca = [], []
    for chave, evs in grupos.items():
        evs.sort(key=lambda e: e["data"], reverse=True)
        topo = evs[0]
        sec = sec_nome(topo["securitizadora"])
        nome_op = op_nome(topo["operacao"])
        codigos = sorted({c for e in evs for c in e["codigos_if"]})
        fiagros = {}
        for e in evs:
            for f in e["fundos"]:
                if f.get("tf") == "fiagro" and (f["cnpj_fundo"] not in fiagros or f.get("metodo") in ("carteira", "codigo")):
                    fiagros[f["cnpj_fundo"]] = f
        fs = sorted(fiagros.values(), key=lambda f: ({"carteira": 0, "codigo": 1}.get(f.get("metodo"), 2), -(f.get("pct_pl") or 0), f["ticker"] or f["fundo"]))
        cont = Counter(e["severidade"] for e in evs)
        serie = (f"séries {topo['serie']} a {int(topo['serie']) + topo['outras_series']}" if topo.get("outras_series") and topo["serie"].isdigit()
                 else f"{topo['serie']}ª série")
        linha = f"{nome_op}, {sec}, {topo['emissao']}ª emissão, {serie}"

        linhas_ev = "".join(linha_evento(e, "ver detalhes") for e in evs)
        linhas_f = "".join(
            f"""<tr><td><a href="/fiagro/{e_(slugs.get(f['cnpj_fundo'], ''))}/"><b class="{'tk' if f['ticker'] else ''}">{e_(f['ticker'] or nome_fiagro(f['fundo']))}</b></a>
          <small>{e_(gestora_curta(f.get('gestor')))}</small></td>
        <td>{e_(METODO.get(f.get('metodo'), ''))}{(' · <b>' + pct(f['pct_pl']) + ' do PL</b>') if f.get('pct_pl') is not None else ''}<small class="quote">{e_(f.get('trecho'))}</small></td></tr>""" for f in fs
        ) or '<tr><td colspan="2" class="empty"><b>Nenhum Fiagro identificado.</b>A operação não aparece na última carteira entregue à CVM pelos Fiagros, nem nos relatórios gerenciais recentes. Pode estar em fundos cuja carteira não deu para identificar, ou com outros investidores.</td></tr>'
        kpis = f"""<div class="kpis">
      <div><span>Eventos de crédito</span><b>{len(evs)}</b><small>desde {data_br(saida['janela']['inicio'])}</small></div>
      <div><span>Urgentes</span><b>{cont['crit']}</b><small>{cont['warn']} de atenção</small></div>
      <div><span>Fiagros ligados</span><b>{len(fs)}</b><small>{sum(1 for f in fs if f.get("metodo") == "carteira")} pela carteira</small></div>
      <div><span>Último documento</span><b>{data_br(topo['data'][:10])}</b><small>{e_(topo['especie'] or topo['categoria'])}</small></div>
    </div>"""
        titulo_cra = codigos[0] if len(codigos) == 1 else (topo.get("isin") or nome_op)
        corpo = cabeca(f'CRA {e_(titulo_cra)}<span class="ph-badge">{e_(sec)}</span>', e_(linha) + ".",
                       trilha=f'<a href="/fiagro/">Fiagros</a><span aria-hidden="true">/</span><span>CRA {e_(nome_op)}</span>',
                       extra=kpis) + f"""<main class="wrap">
  <div class="grid">
    <section aria-labelledby="h-ev">
      <div class="head"><h2 id="h-ev">Eventos de crédito</h2><small>{len(evs)} {'evento' if len(evs) == 1 else 'eventos'}</small></div>
      <div class="panel"><ul class="list" style="list-style:none;margin:0;padding:0">{linhas_ev}</ul></div>
      <div class="head" style="margin-top:28px"><h2>Fiagros com esta operação</h2><small>carteira entregue à CVM ou relatório gerencial</small></div>
      <div class="panel tbl-wrap"><table class="rank"><thead><tr><th>Fiagro</th><th>Como ligamos</th></tr></thead><tbody>{linhas_f}</tbody></table></div>
    </section>
    <aside class="side">
      <section class="panel">
        <h2>Ficha</h2>
        <dl class="gloss" style="margin-top:10px">
          <div><dt>Operação</dt><dd>{e_(nome_op)}</dd></div>
          <div><dt>Securitizadora</dt><dd>{e_(sec)}</dd></div>
          <div><dt>Emissão e série</dt><dd>{e_(topo['emissao'])}ª emissão, {e_(serie)}</dd></div>
          {f"<div><dt>ISIN</dt><dd>{e_(topo['isin'])}</dd></div>" if topo.get('isin') else ''}
          {f"<div><dt>Códigos IF citados nos documentos</dt><dd>{e_(', '.join(codigos))}</dd></div>" if codigos else ''}
        </dl>
        <a class="btn" style="margin-top:14px" href="{e_(topo['url'])}" target="_blank" rel="noopener noreferrer">Último documento no Fundos.Net</a>
      </section>
    </aside>
  </div>
  <p class="note" style="margin-top:20px">A carteira dos Fiagros entregue à CVM não traz o código dos CRAs: o radar cruza securitizadora, vencimento e taxa com o informe das securitizadoras, e usa o relatório gerencial quando o cruzamento não fecha. Valores e % do PL são da data da carteira. Confira sempre no documento original.</p>
</main>"""
        url = f"cra/{chave}/"
        (destino / chave).mkdir(parents=True, exist_ok=True)
        (destino / chave / "index.html").write_text(pagina(
            url, f"CRA {nome_op}, {sec} · Radar de Lastro",
            f"CRA {titulo_cra}: {linha}. {len(evs)} {'evento' if len(evs) == 1 else 'eventos'} de crédito e {len(fs)} Fiagros ligados à operação.",
            corpo, "", nav="fiagro"))
        urls.append(url)
        busca.append({"t": "c", "tp": "CRA", "k": titulo_cra if titulo_cra != nome_op else (topo.get("isin") or ""),
                      "n": nome_op, "s": f"{sec}, {topo['emissao']}ª emissão", "f": len(fs), "e": len(evs), "u": "/" + url,
                      "x": " ".join(codigos + [topo.get("isin") or ""])})
    return urls, busca
