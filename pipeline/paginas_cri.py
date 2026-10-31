"""Páginas por CRI (/cri/<código IF>/) e índice da busca do site (busca.json).

Cada CRI com código IF no informe trimestral ganha uma página com os FIIs que o têm na carteira e os
eventos de crédito da operação. O nome da operação vem dos documentos do Fundos.Net que citam o
código; sem documento, usa o nome do emissor declarado no informe.
"""
import json
import re
import shutil
from collections import Counter, defaultdict

from gerar import cabeca  # noqa: E402
from paginas_fundos import (MESES, SECS, SEV, SITE, brl, data_br, e_, gestora_curta, mapa_slugs, nome_curto,
                            op_nome, pagina, pct, titulo)

IF_RE = re.compile(r"\d{2}[A-L]\d{7}|CRA0\d{2}[0-9A-Z]{5}")


def limpar_emissor(descricao: str) -> str:
    """'CRI_23L1952070 - OPEA SEC' / 'OPEA SECURITIZADORA S.A. - CRI - 22K1159009' -> 'OPEA SECURITIZADORA S.A.'"""
    t = IF_RE.sub(" ", descricao or "")
    t = re.sub(r"\bCRI_?|_DU\d\b|\bCRA\b", " ", t, flags=re.I)
    t = re.sub(r"\s*[-–]\s*", " ", t)
    return re.sub(r"\s+", " ", t).strip(" -_.,")


def emissor_curto(nome: str) -> str:
    t = re.sub(r"COMPANHIA DE SECURITIZA(Ç|C)(Ã|A)O|CIA\.? DE SECURITIZA(Ç|C)(Ã|A)O|COMPANHIA SECURITIZADORA|"
               r"SECURITIZADORA DE CR(É|E)DITOS? (IMOBILI(Á|A)RIOS?|FINANCEIROS?)?|SECURITIZADORA|\bSEC\b|"
               r"\bS\.?A\.?\b|\bS/A\b|\bLTDA\.?\b|\bCOMPANHIA\b|\bCIA\.?\b", " ", nome or "", flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" -.,")
    t = re.sub(r"^(de|da|do)\s+|\s+(de|da|do|e)$", "", t, flags=re.I)
    return titulo(t) if t else (nome or "Emissor não informado")


# nomes conferidos das securitizadoras mais comuns nos informes (CNPJ só com dígitos)
EMISSORES_MANUAIS = {
    "02773542000122": "Opea", "08769451000108": "Riza (ex-Virgo)", "12130744000100": "True", "25005683000109": "Vert",
    "04200649000107": "Província", "09304427000158": "Habitasec", "41811375000119": "Canal", "12979898000170": "Forte",
    "10608405000160": "Bari", "10608405000241": "Bari", "48415978000140": "Leverage", "53192655000175": "Leverage",
    "03559006000191": "RB Capital", "03559006000272": "RB Capital", "02916265000160": "RB Capital",
    "26609050000164": "Travessia", "43335774000186": "Travessia", "07587384000130": "Planeta",
    "31468139000198": "Casa de Pedra", "02105040000123": "Cibrasec", "35082277000195": "Base", "13349677000181": "Reit",
    "11257352000143": "BSI Capital", "12320349000190": "Ore", "10753164000143": "Eco Securitizadora",
    "19851496000135": "Logos", "43737117000165": "Vert", "48238484000138": "Kanastra",
    "03767538000114": "Brazilian Securities", "55085811000124": "Éxes", "40446476000175": "Playbanco",
    "60746948000112": "Bradesco", "61194353000164": "Itaú Corretora", "12113074000100": "True", "51319586000192": "Rock",
    "54414102000182": "Liqi", "49947676000186": "Creditcorp", "52890908000111": "Artesanal",
    "08769451000180": "Riza (ex-Virgo)",  # CNPJ da Riza/Virgo digitado com os dígitos trocados em alguns informes
    "20502525000132": "Emissor não identificado",  # CNPJ usado para CRIs de securitizadoras diferentes

}


def emissores_por_cnpj(posicoes) -> dict:
    """CNPJ do emissor -> nome mais completo que aparece nos informes."""
    nomes = defaultdict(Counter)
    for p in posicoes:
        n = limpar_emissor(p["descricao"])
        if len(n) >= 3:
            nomes[p["cnpj_emissor"]][n] += 1
    auto = {c: emissor_curto(max(cnt, key=lambda n: (cnt[n], len(n)))) for c, cnt in nomes.items()}
    return {**auto, **EMISSORES_MANUAIS}


EMISSORES = {}


def nome_operacao(p, ops) -> str:
    """Nome legível de uma posição: operação do Fundos.Net, ou o emissor do informe."""
    op = ops.get(p.get("codigo_if") or "")
    if op and op.get("operacao"):
        return f"{op_nome(op['operacao'])}, {SECS.get(op['securitizadora'], titulo(op['securitizadora']))}"
    return EMISSORES.get(p.get("cnpj_emissor")) or emissor_curto(limpar_emissor(p.get("descricao", "")))


def gerar(saida: dict, holdings: dict, ops: dict) -> list[str]:
    destino = SITE / "cri"
    if destino.exists():
        shutil.rmtree(destino)
    EMISSORES.update(emissores_por_cnpj(holdings["posicoes"]))
    slugs = mapa_slugs(holdings)

    por_if = defaultdict(list)
    for p in holdings["posicoes"]:
        if p["codigo_if"]:
            por_if[p["codigo_if"]].append(p)
    eventos_por_if = defaultdict(list)
    for ev in saida["eventos"]:
        for c in ev["codigos_if"]:
            eventos_por_if[c].append(ev)

    data_ref = holdings["resumo"]["data_referencia"]
    urls, busca_cri = [], []
    for codigo, pos in por_if.items():
        tipo = "CRA" if codigo.startswith("CRA") else "CRI"
        op = ops.get(codigo, {})
        sec = SECS.get(op.get("securitizadora"), titulo(op["securitizadora"])) if op.get("securitizadora") else EMISSORES.get(pos[0]["cnpj_emissor"], "Emissor não informado")
        nome_op = op_nome(op["operacao"]) if op.get("operacao") else None
        emissao = op.get("emissao") or pos[0]["emissao"] or ""
        serie = op.get("serie") or pos[0]["serie"] or ""
        venc = next((p["vencimento"] for p in pos if p["vencimento"]), None)
        evs = sorted(eventos_por_if.get(codigo, []), key=lambda e: e["data"], reverse=True)
        total = sum(p["valor"] for p in pos)
        fundos = sorted(pos, key=lambda p: -(p["pct_pl"] or 0))
        cont = Counter(e["severidade"] for e in evs)

        partes = [nome_op, sec, f"{emissao}ª emissão" if emissao not in ("", "0") else None,
                  f"{serie}ª série" if serie not in ("", "0") else None]
        linha = ", ".join(x for x in partes if x)
        resumo = f"{len(fundos)} {'FII tem' if len(fundos) == 1 else 'FIIs têm'} este {tipo} na carteira, somando {brl(total)}"
        if evs:
            resumo += f", e a operação teve {len(evs)} {'evento' if len(evs) == 1 else 'eventos'} de crédito no período"
        resumo += "."

        linhas_ev = "".join(
            f"""<li><a class="ag-row" href="/#{e_(ev['id'])}">
      <div class="cal"><b>{int(ev['data'][8:10])}</b><span>{MESES[int(ev['data'][5:7]) - 1]}</span></div>
      <div><div class="ev-top"><span class="tag {ev['severidade']}">{SEV[ev['severidade']]}</span><span class="what">{e_(ev['tipo'])}</span></div>
        <div class="who">{e_(ev['categoria'] if not ev.get('especie') else ev['especie'])}</div></div>
      <span class="in">ver detalhes</span>
    </a></li>""" for ev in evs
        ) or f'<li class="empty"><b>Nenhum evento de crédito no período.</b>O radar não encontrou fatos relevantes, avisos ou assembleias de crédito desta operação desde {data_br(saida["janela"]["inicio"])}.</li>'

        linhas_f = "".join(
            f"""<tr><td><a href="/fii/{e_(slugs[p['cnpj_fundo']])}/"><b class="{'tk' if p['ticker'] else ''}">{e_(p['ticker'] or nome_curto(p['fundo']))}</b></a>
          <small>{e_(nome_curto(p['fundo']) if p['ticker'] else 'Sem negociação em bolsa')}</small></td>
        <td>{e_(gestora_curta(p.get('gestor')))}</td><td class="num">{brl(p['valor'])}</td><td class="num"><b>{pct(p['pct_pl'])}</b></td></tr>"""
            for p in fundos
        )
        doc = op.get("doc_id")
        kpis = f"""<div class="kpis">
      <div><span>FIIs com este {tipo}</span><b>{len(fundos)}</b><small>informe de {data_br(data_ref)}</small></div>
      <div><span>Em carteira de FIIs</span><b>{brl(total)}</b><small>soma das posições</small></div>
      <div><span>Maior exposição</span><b>{pct(fundos[0]['pct_pl'])}</b><small>do PL de {e_(fundos[0]['ticker'] or nome_curto(fundos[0]['fundo']))}</small></div>
      <div><span>Eventos de crédito</span><b>{len(evs)}</b><small>desde {data_br(saida['janela']['inicio'])}</small></div>
    </div>"""
        corpo = cabeca(f'{tipo} {e_(codigo)}<span class="ph-badge">{e_(sec)}</span>', e_(linha) + ".",
                       trilha=f'<a href="/fii/">Fundos</a><span aria-hidden="true">/</span><span>{tipo} {e_(codigo)}</span>',
                       extra=kpis) + f"""<main class="wrap">
  <div class="grid">
    <section aria-labelledby="h-f">
      <div class="head"><h2 id="h-f">FIIs com este {tipo}</h2><small>informe de {data_br(data_ref)}</small></div>
      <div class="panel tbl-wrap"><table class="rank"><thead><tr><th>Fundo</th><th>Gestora</th><th class="num">Valor</th><th class="num">% do PL</th></tr></thead>
        <tbody>{linhas_f}</tbody></table></div>
      <div class="head" style="margin-top:28px"><h2>Eventos de crédito</h2><small>{len(evs)} {'evento' if len(evs) == 1 else 'eventos'}</small></div>
      <div class="panel"><ul class="list" style="list-style:none;margin:0;padding:0">{linhas_ev}</ul></div>
    </section>
    <aside class="side">
      <section class="panel">
        <h2>Ficha</h2>
        <dl class="gloss" style="margin-top:10px">
          <div><dt>Código IF</dt><dd>{e_(codigo)}</dd></div>
          {f'<div><dt>Operação</dt><dd>{e_(nome_op)}</dd></div>' if nome_op else ''}
          <div><dt>{'Securitizadora' if op else 'Emissor'}</dt><dd>{e_(sec)}</dd></div>
          {f'<div><dt>Emissão e série</dt><dd>{e_(emissao)}ª emissão, {e_(serie)}ª série</dd></div>' if emissao not in ('', '0') else ''}
          {f'<div><dt>Vencimento</dt><dd>{data_br(venc)}</dd></div>' if venc else ''}
          <div><dt>Em carteira de FIIs</dt><dd>{brl(total)} em {len(fundos)} {'fundo' if len(fundos) == 1 else 'fundos'}</dd></div>
        </dl>
        {f'<a class="btn" style="margin-top:14px" href="https://fnet.bmfbovespa.com.br/fnet/publico/exibirDocumento?id={doc}&cvm=true" target="_blank" rel="noopener">Último documento no Fundos.Net</a>' if doc else ''}
      </section>
    </aside>
  </div>
  <p class="note" style="margin-top:20px">Posições declaradas no informe trimestral estruturado dos FIIs, na CVM. FIIs que guardam o CRI sem informar o código IF podem não aparecer aqui.</p>
</main>"""
        url = f"cri/{codigo}/"
        descricao = f"{tipo} {codigo}: {linha}. {resumo}"
        (destino / codigo).mkdir(parents=True, exist_ok=True)
        (destino / codigo / "index.html").write_text(
            pagina(url, f"{tipo} {codigo}{' ' + nome_op if nome_op else ''} · Radar de Lastro", descricao, corpo, "", nav="fundos"))
        urls.append(url)
        busca_cri.append({"t": "c", "k": codigo, "n": nome_op or sec, "s": linha, "f": len(fundos),
                          "e": len(evs), "u": "/" + url})
    return urls, busca_cri


def escrever_busca(holdings: dict, busca_cri: list):
    """Índice leve para a barra de busca do site."""
    slugs = mapa_slugs(holdings)
    fundos = {}
    for p in holdings.get("fundos", []):
        fundos[p["cnpj_fundo"]] = {"t": "f", "k": p["ticker"] or "", "n": nome_curto(p["fundo"]),
                                   "s": gestora_curta(p.get("gestor")), "u": f"/fii/{slugs[p['cnpj_fundo']]}/", "c": 0}
    for p in holdings["posicoes"]:
        f = fundos.setdefault(p["cnpj_fundo"], {"t": "f", "k": p["ticker"] or "", "n": nome_curto(p["fundo"]),
                                                "s": gestora_curta(p.get("gestor")), "u": f"/fii/{slugs[p['cnpj_fundo']]}/", "c": 0})
        f["c"] += 1
    itens = list(fundos.values()) + busca_cri
    (SITE / "busca.json").write_text(json.dumps(itens, ensure_ascii=False, separators=(",", ":")))
    return len(itens)
