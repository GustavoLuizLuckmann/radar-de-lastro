"""Junta carteira, documentos e classificação no arquivo de dados que o site lê."""
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from classify import classificar
from match import Indice, expor
from paginas_fundos import gerar as gerar_paginas_fundos, mapa_slugs

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
           ("como-funciona.html", "monthly", "0.5")]


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
    idx = Indice(h["posicoes"])
    slugs = mapa_slugs(h)

    stats = defaultdict(int)
    brutos = []
    for d in coleta["documentos"]:
        arq = TXT / f"{d['id']}.txt"
        texto = arq.read_text(errors="ignore") if arq.exists() else ""
        stats["documentos"] += 1
        if not texto.strip():
            stats["sem_texto"] += 1
        pos, metodo = idx.casar(d, texto or None)
        if not metodo:
            continue
        stats["casados_" + metodo] += 1
        c = classificar(d, texto)
        if not c:
            stats["rotina"] += 1
            continue
        fundos = expor(pos)
        brutos.append({
            "doc_id": d["id"], "data": data_iso(d["data_entrega"]), "categoria": d["categoria"],
            "especie": d["especie"], "securitizadora": d["securitizadora"], "emissao": d["emissao"],
            "serie": d["serie"], "outras_series": d["outras_series"], "operacao": d["operacao"],
            "url": URL_DOC.format(id=d["id"]), "cruzamento": metodo, **c,
            "codigos_if": sorted({p["codigo_if"] for p in pos if p["codigo_if"]}),
            "fundos": [{**{k: f.get(k) for k in ("cnpj_fundo", "ticker", "fundo", "listado", "gestor", "valor", "pct_pl")},
                        "slug": slugs.get(f["cnpj_fundo"])} for f in fundos],
        })

    # um card por operação e tipo de evento; documentos repetidos (edital, proposta, ata) viram histórico
    grupos = defaultdict(list)
    for e in brutos:
        grupos[(e["securitizadora"], e["emissao"], e["serie"], e["tipo"])].append(e)
    eventos = []
    for lista in grupos.values():
        lista.sort(key=lambda e: e["data"], reverse=True)
        topo = dict(lista[0])
        topo["severidade"] = min((e["severidade"] for e in lista), key=ORDEM.get)
        topo["data_assembleia"] = next((e["data_assembleia"] for e in lista if e["data_assembleia"]), None)
        topo["historico"] = [{"doc_id": e["doc_id"], "data": e["data"], "especie": e["especie"] or e["categoria"],
                              "url": e["url"]} for e in lista[1:]]
        topo["id"] = f"e{topo['doc_id']}"
        eventos.append(topo)
    eventos.sort(key=lambda e: e["data"], reverse=True)

    # exposição por fundo aos eventos do período
    fundos = {}
    for e in eventos:
        for f in e["fundos"]:
            x = fundos.setdefault(f["cnpj_fundo"], {"cnpj_fundo": f["cnpj_fundo"], "ticker": f["ticker"], "fundo": f["fundo"],
                                                    "listado": f["listado"], "gestor": f.get("gestor"), "pl": None,
                                                    "expo": {"crit": 0.0, "warn": 0.0, "mon": 0.0}, "eventos": 0, "_ops": {}})
            x["eventos"] += 1
            # a mesma operação pode aparecer em mais de um evento; conta o pior
            op = (e["securitizadora"], e["emissao"], e["serie"])
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
        "estatisticas": dict(stats),
        "eventos": eventos,
        "fundos": sorted(fundos.values(), key=lambda x: -(x["expo"]["crit"] * 10 + x["expo"]["warn"] * 3 + x["expo"]["mon"])),
    }
    SITE.mkdir(exist_ok=True)
    (SITE / "data.json").write_text(json.dumps(saida, ensure_ascii=False))
    paginas = gerar_paginas_fundos(saida, h)
    escrever_sitemap(saida["gerado_em"][:10], paginas)
    print(json.dumps({"eventos": len(eventos), "fundos": len(fundos), **stats}, ensure_ascii=False), file=sys.stderr)


if __name__ == "__main__":
    main()
