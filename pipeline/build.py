"""Junta carteira, documentos e classificação no arquivo de dados que o site lê."""
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from classify import classificar
from match import CRA_RE, Indice, IndiceCarteiraFiagro, IndiceGerencial, expor
from paginas_fiagro import chave_cra, gerar as gerar_paginas_fiagro, gerar_cras, mapa_slugs_fiagro
from paginas_fundos import gerar as gerar_paginas_fundos, mapa_slugs
from paginas_cri import EMISSORES, emissores_por_cnpj, escrever_busca, gerar as gerar_paginas_cri

ROOT = Path(__file__).resolve().parent.parent
TXT = ROOT / "raw" / "fnet" / "txt"
SITE = ROOT / "site"
URL_DOC = "https://fnet.bmfbovespa.com.br/fnet/publico/exibirDocumento?id={id}&cvm=true"
ORDEM = {"crit": 0, "warn": 1, "mon": 2}


def data_iso(br: str):
    # "27/10/2026 22:14" -> "2026-10-27T22:14"
    d, _, h = (br or "").partition(" ")
    dd, mm, aa = d.split("/")
    return f"{aa}-{mm}-{dd}T{h or '00:00'}"


PAGINAS = [("", "daily", "1.0"), ("fundos.html", "daily", "0.8"), ("assembleias.html", "daily", "0.8"),
           ("como-funciona.html", "monthly", "0.5"), ("fii/", "daily", "0.7"), ("fiagro/", "daily", "0.7"), ("sobre.html", "monthly", "0.3"),
           ("termos.html", "yearly", "0.2"), ("privacidade.html", "yearly", "0.2")]


def escrever_sitemap(data: str, fundos: list[str] = ()):
    """Mapa do site para buscadores; a data muda a cada atualização dos dados."""
    todas = list(PAGINAS) + [(u, "daily", "0.6") for u in sorted(fundos)]
    itens = "\n".join(
        f"  <url><loc>https://radardelastro.com.br/{p}</loc><lastmod>{data}</lastmod>"
        f"<changefreq>{f}</changefreq><priority>{pr}</priority></url>"
        for p, f, pr in todas
    )
    (SITE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + itens + "\n</urlset>\n"
    )


def main():
    h = json.loads((ROOT / "data" / "holdings.json").read_text())
    coleta = json.loads((ROOT / "raw" / "fnet" / "docs.json").read_text())
    arq_fiagro = ROOT / "data" / "fiagro.json"
    fg = json.loads(arq_fiagro.read_text()) if arq_fiagro.exists() else {"data_referencia": None, "fundos": []}
    idx = Indice(h["posicoes"])
    gidx = IndiceGerencial(fg["fundos"], ROOT / "raw" / "fiagro" / "gerencial")
    cidx = IndiceCarteiraFiagro(fg["fundos"])
    slugs = mapa_slugs(h)
    slugs_fg = mapa_slugs_fiagro(fg)

    stats = defaultdict(int)
    brutos = []
    ops = {}  # código IF -> dados da operação no Fundos.Net (documento mais recente que cita o código)
    for d in coleta["documentos"]:
        arq = TXT / f"{d['id']}.txt"
        texto = arq.read_text(errors="ignore") if arq.exists() else ""
        stats["documentos"] += 1
        if not texto.strip():
            stats["sem_texto"] += 1
        d.setdefault("tipo", "CRI")
        pos, metodo = idx.casar(d, texto or None)
        # Fiagros: primeiro a carteira (CDA cruzado com o informe das securitizadoras), que dá valor e
        # % do PL; depois o relatório gerencial, para os fundos que a carteira não alcança
        na_carteira = cidx.casar(d, texto or None)
        ja = {a["fiagro"]["cnpj_fundo"] for a in na_carteira}
        citam = na_carteira + [a for a in gidx.casar(d, texto or None) if a["fiagro"]["cnpj_fundo"] not in ja]
        if na_carteira:
            stats["fiagro_carteira"] += 1
        if citam:
            stats["citados_gerencial"] += 1
        # CRI sem FII nem Fiagro ligado fica de fora; CRA entra mesmo sem Fiagro identificado, porque a
        # CVM não divulga os CRAs de cada Fiagro e o evento interessa a quem acompanha o mercado
        if not metodo and not citam and d["tipo"] != "CRA":
            continue
        stats["casados_" + (metodo or ("gerencial" if citam else "cra_sem_fundo"))] += 1
        if metodo in ("if", "if_texto"):
            for p in pos:
                c = p["codigo_if"]
                if c and (c not in ops or data_iso(d["data_entrega"]) > ops[c]["data"]):
                    ops[c] = {"operacao": d["operacao"], "securitizadora": d["securitizadora"], "emissao": d["emissao"],
                              "serie": d["serie"], "doc_id": d["id"], "data": data_iso(d["data_entrega"])}
        c = classificar(d, texto)
        if not c:
            stats["rotina"] += 1
            continue
        fundos = expor(pos)
        cods = sorted(set(CRA_RE.findall(texto)))[:6] if d["tipo"] == "CRA" else []
        brutos.append({
            "doc_id": d["id"], "data": data_iso(d["data_entrega"]), "categoria": d["categoria"],
            "especie": d["especie"], "securitizadora": d["securitizadora"], "emissao": d["emissao"],
            "serie": d["serie"], "outras_series": d["outras_series"], "operacao": d["operacao"],
            "url": URL_DOC.format(id=d["id"]), "cruzamento": metodo or ("gerencial" if citam else None), **c,
            "lastro": d["tipo"], "isin": d.get("isin"),
            "codigos_if": sorted({p["codigo_if"] for p in pos if p["codigo_if"]}) or cods,
            "fundos": [{**{k: f.get(k) for k in ("cnpj_fundo", "ticker", "fundo", "listado", "gestor", "valor", "pct_pl")},
                        "slug": slugs.get(f["cnpj_fundo"])} for f in fundos]
                      + [{"cnpj_fundo": a["fiagro"]["cnpj_fundo"], "ticker": a["fiagro"]["ticker"], "fundo": a["fiagro"]["fundo"],
                          "listado": a["fiagro"]["listado"], "gestor": a["fiagro"]["gestor"],
                          "valor": a.get("valor"), "pct_pl": a.get("pct_pl"),
                          "slug": slugs_fg.get(a["fiagro"]["cnpj_fundo"]), "tf": "fiagro", "metodo": a["metodo"],
                          "trecho": a["trecho"], "ref": a.get("ref") or (a["fiagro"].get("gerencial") or {}).get("referencia"),
                          "cra_pl": round(a["fiagro"]["cra"] / a["fiagro"]["pl"], 4) if a["fiagro"].get("pl") else None}
                         for a in citam if a["fiagro"]["cnpj_fundo"] not in {f["cnpj_fundo"] for f in fundos}],
        })

    # um card por operação e tipo de evento; documentos repetidos (edital, proposta, ata) viram histórico
    grupos = defaultdict(list)
    for e in brutos:
        grupos[(e["lastro"], e["securitizadora"], e["emissao"], e["serie"], e["tipo"])].append(e)
    cris_com_pagina = {p["codigo_if"] for p in h["posicoes"] if p["codigo_if"]}
    eventos = []
    for lista in grupos.values():
        lista.sort(key=lambda e: e["data"], reverse=True)
        topo = dict(lista[0])
        topo["severidade"] = min((e["severidade"] for e in lista), key=ORDEM.get)
        topo["data_assembleia"] = next((e["data_assembleia"] for e in lista if e["data_assembleia"]), None)
        topo["historico"] = [{"doc_id": e["doc_id"], "data": e["data"], "especie": e["especie"] or e["categoria"],
                              "url": e["url"]} for e in lista[1:]]
        topo["id"] = f"e{topo['doc_id']}"
        if topo["lastro"] == "CRA":
            topo["pag"] = f"/cra/{chave_cra(topo)}/"
        elif len(topo["codigos_if"]) == 1 and topo["codigos_if"][0] in cris_com_pagina:
            topo["pag"] = f"/cri/{topo['codigos_if'][0]}/"
        eventos.append(topo)
    eventos.sort(key=lambda e: e["data"], reverse=True)

    # exposição por fundo aos eventos do período
    fundos = {}
    for e in eventos:
        for f in e["fundos"]:
            if f.get("tf") == "fiagro":
                continue  # sem posição declarada, não entra na conta de exposição
            x = fundos.setdefault(f["cnpj_fundo"], {"cnpj_fundo": f["cnpj_fundo"], "ticker": f["ticker"], "fundo": f["fundo"],
                                                    "listado": f["listado"], "gestor": f.get("gestor"), "pl": None,
                                                    "expo": {"crit": 0.0, "warn": 0.0, "mon": 0.0}, "eventos": 0, "_ops": {}})
            x["eventos"] += 1
            # a mesma operação pode aparecer em mais de um evento; conta o pior
            op = (e["lastro"], e["securitizadora"], e["emissao"], e["serie"])
            atual = x["_ops"].get(op)
            if f["pct_pl"] is not None and (atual is None or ORDEM[e["severidade"]] < ORDEM[atual[0]]):
                x["_ops"][op] = (e["severidade"], f["pct_pl"])
    for x in fundos.values():
        for sev, pct in x.pop("_ops").values():
            x["expo"][sev] += pct
        x["expo"] = {k: round(v, 6) for k, v in x["expo"].items()}
    pl = {p["cnpj_fundo"]: p["pl"] for p in h["posicoes"]}
    for x in fundos.values():
        x["pl"] = pl.get(x["cnpj_fundo"])

    saida = {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "janela": {"inicio": coleta["inicio"], "fim": coleta["fim"]},
        "carteira": h["resumo"],
        "fiagro": {"data_referencia": fg["data_referencia"], "fundos": len(fg["fundos"]),
                   "com_cra": sum(1 for f in fg["fundos"] if f["cra"] > 0),
                   "valor_cra": round(sum(f["cra"] for f in fg["fundos"]), 2),
                   "com_relatorio": sum(1 for f in fg["fundos"] if (f.get("gerencial") or {}).get("valido")),
                   "com_carteira": sum(1 for f in fg["fundos"] if (f.get("cda") or {}).get("cras"))},
        "estatisticas": dict(stats),
        "eventos": eventos,
        "fundos": sorted(fundos.values(), key=lambda x: -(x["expo"]["crit"] * 10 + x["expo"]["warn"] * 3 + x["expo"]["mon"])),
    }
    SITE.mkdir(exist_ok=True)
    (SITE / "data.json").write_text(json.dumps(saida, ensure_ascii=False))
    EMISSORES.update(emissores_por_cnpj(h["posicoes"]))
    paginas = gerar_paginas_fundos(saida, h, ops)
    paginas_cri, busca_cri = gerar_paginas_cri(saida, h, ops)
    paginas_fg, busca_fg = gerar_paginas_fiagro(saida, fg)
    paginas_cra, busca_cra = gerar_cras(saida, fg)
    stats["paginas_cri"] = len(paginas_cri)
    stats["paginas_fiagro"] = len(paginas_fg)
    stats["paginas_cra"] = len(paginas_cra)
    stats["itens_busca"] = escrever_busca(h, busca_cri + busca_fg + busca_cra)
    escrever_sitemap(saida["gerado_em"][:10], paginas + paginas_cri + paginas_fg + paginas_cra)
    print(json.dumps({"eventos": len(eventos), "fundos": len(fundos), **stats}, ensure_ascii=False), file=sys.stderr)


if __name__ == "__main__":
    main()
