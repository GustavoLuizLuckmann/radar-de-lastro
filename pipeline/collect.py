"""Lista documentos de CRI no Fundos.Net num intervalo de datas e grava os metadados."""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from fnet import CATEGORIAS, Fnet, ler_descricao

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "raw" / "fnet" / "docs.json"


def coletar(dias: int = 30, fim: date | None = None):
    fim = fim or date.today()
    inicio = fim - timedelta(days=dias)
    api = Fnet()
    docs = {}
    for cat, nome in CATEGORIAS.items():
        n = 0
        for item in api.pesquisar(cat, inicio, fim):
            desc = ler_descricao(item.get("descricaoFundo", ""))
            if not desc or desc["tipo"] != "CRI":
                continue
            if item.get("status", "").startswith("C"):  # documento cancelado
                continue
            docs[item["id"]] = {
                "id": item["id"], "categoria": item.get("categoriaDocumento") or nome,
                "tipo_documento": item.get("tipoDocumento") or "", "especie": item.get("especieDocumento") or "",
                "data_entrega": item.get("dataEntrega"), "data_referencia": item.get("dataReferencia"),
                "descricao": item.get("descricaoFundo"), "versao": item.get("versao"),
                "alta_prioridade": bool(item.get("altaPrioridade")), **desc,
            }
            n += 1
        print(f"{nome}: {n} documentos de CRI", file=sys.stderr)
    return {"inicio": inicio.isoformat(), "fim": fim.isoformat(), "documentos": list(docs.values())}


if __name__ == "__main__":
    dias = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    res = coletar(dias)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(f"{len(res['documentos'])} documentos gravados em {OUT}", file=sys.stderr)
