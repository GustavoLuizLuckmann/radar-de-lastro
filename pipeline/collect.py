"""Lista documentos de CRI no Fundos.Net e mantém um histórico acumulado dos metadados.

Cada execução busca os últimos `dias` e junta ao histórico já salvo. Se o histórico estiver vazio
ou começar depois de HISTORICO_MINIMO dias atrás, busca esse período inteiro uma vez (carga inicial).
Documentos com mais de RETENCAO dias saem do histórico.
"""
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from fnet import CATEGORIAS, Fnet, ler_descricao

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "raw" / "fnet" / "docs.json"
HISTORICO_MINIMO = 90
RETENCAO = 365


def _data(br: str) -> date:
    return datetime.strptime((br or "01/01/1970")[:10], "%d/%m/%Y").date()


def buscar(api: Fnet, inicio: date, fim: date) -> dict:
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
        print(f"{nome}: {n} documentos de CRI ({inicio:%d/%m} a {fim:%d/%m})", file=sys.stderr)
    return docs


def coletar(dias: int = 7, fim: date | None = None):
    fim = fim or date.today()
    antigo = json.loads(OUT.read_text()) if OUT.exists() else {"documentos": []}
    docs = {d["id"]: d for d in antigo["documentos"]}
    inicio_hist = date.fromisoformat(antigo["inicio"]) if antigo.get("inicio") else None

    meta = fim - timedelta(days=HISTORICO_MINIMO)
    inicio = fim - timedelta(days=dias)
    if inicio_hist is None or inicio_hist > meta:
        inicio = meta  # carga inicial do histórico
    api = Fnet()
    docs.update(buscar(api, inicio, fim))

    corte = fim - timedelta(days=RETENCAO)
    docs = {k: d for k, d in docs.items() if _data(d["data_entrega"]) >= corte}
    novo_inicio = max(corte, min(inicio, inicio_hist or inicio))
    return {"inicio": novo_inicio.isoformat(), "fim": fim.isoformat(), "documentos": list(docs.values())}


if __name__ == "__main__":
    dias = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    res = coletar(dias)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(f"{len(res['documentos'])} documentos no histórico, de {res['inicio']} a {res['fim']}", file=sys.stderr)
