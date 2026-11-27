"""Cadastro e composição dos Fiagros, e o texto do relatório gerencial mais recente de cada um.

Fontes:
  - Informe Mensal de Fiagro (CVM, dados abertos): nome, ISIN, gestor, PL, quanto há em CRA, CRI,
    CPR e outros ativos, e quanto da carteira está vencido.
  - Relatório gerencial no Fundos.Net: a CVM não divulga quais CRAs cada Fiagro tem (o informe só
    traz o total em CRA, e a composição da carteira aberta vem sem o código dos títulos). Os
    relatórios gerenciais costumam listar as operações pelo nome do devedor, e é por esse nome que
    ligamos os eventos de crédito aos Fiagros (ver build.py).

Saída: data/fiagro.json; textos em raw/fiagro/gerencial/<cnpj>.txt.
"""
import io
import json
import re
import subprocess
import sys
import time
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

from holdings import aplicar_manuais, limpo, ticker_do_isin

BASE = "https://dados.cvm.gov.br/dados/FIAGRO/DOC/INF_MENSAL/DADOS"
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw" / "fiagro"
GER = RAW / "gerencial"
OUT = ROOT / "data" / "fiagro.json"
MESES_INFORME = 6           # meses de informe lidos (o ISIN às vezes só aparece em meses anteriores)
RECHECAR_DIAS = 3           # intervalo mínimo entre consultas ao Fundos.Net por fundo
IDADE_MAX_RELATORIO = 150   # relatório gerencial mais antigo que isso não serve para ligar eventos
ORCAMENTO_S = 6 * 60        # tempo máximo de consultas ao Fundos.Net por rodada (o resto fica para a próxima)

# colunas do informe mensal mostradas na composição (rótulo, coluna)
COMPOSICAO = [
    ("CRA", "CRA"), ("CRI", "CRI"), ("CPR", "CPR"), ("CDCA", "CDCA"), ("LCA", "LCA"),
    ("Direitos creditórios do agro", "Direitos_Creditorios_Agronegocio"),
    ("Imóveis rurais", "Imoveis_Rurais"), ("Participações societárias", "Participacoes_Societarias"),
    ("Cotas de outros fundos", "Cotas_Fundos_Investimento"), ("Debêntures", "Debentures"),
    ("Renda fixa e caixa", "Total_Necessidades_Liquidez"),
]


def num(v) -> float:
    try:
        return float(v) if v is not None and v == v else 0.0
    except (TypeError, ValueError):
        return 0.0


def so_digitos(s) -> str:
    return re.sub(r"\D", "", str(s or ""))


def cnpj_fmt(d: str) -> str:
    d = so_digitos(d).zfill(14)
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def baixar_informes(hoje: date) -> list[Path]:
    RAW.mkdir(parents=True, exist_ok=True)
    arquivos = []
    ano, mes = hoje.year, hoje.month
    for _ in range(MESES_INFORME + 2):  # o mês corrente e o anterior podem ainda não existir
        mes -= 1
        if mes == 0:
            ano, mes = ano - 1, 12
        nome = f"inf_mensal_fiagro_{ano}{mes:02d}.zip"
        destino = RAW / nome
        # meses fechados mudam pouco, mas reapresentações acontecem: baixa de novo se tiver mais de 5 dias
        if not destino.exists() or time.time() - destino.stat().st_mtime > 5 * 86400:
            r = requests.get(f"{BASE}/{nome}", timeout=120)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            destino.write_bytes(r.content)
        arquivos.append(destino)
        if len(arquivos) >= MESES_INFORME:
            break
    return sorted(arquivos)


def ler(zpath: Path) -> pd.DataFrame:
    with zipfile.ZipFile(zpath) as z:
        nome = next(n for n in z.namelist() if "subclasse" not in n)
        with z.open(nome) as f:
            return pd.read_csv(io.TextIOWrapper(f, encoding="latin1"), sep=";", dtype=str)


def montar(hoje: date) -> list[dict]:
    df = pd.concat([ler(z) for z in baixar_informes(hoje)], ignore_index=True)
    df["Versao"] = pd.to_numeric(df["Versao"], errors="coerce").fillna(1)
    df = df.sort_values(["Data_Referencia", "Versao"])
    isin = df.dropna(subset=["Codigo_ISIN"]).groupby("CNPJ_Classe")["Codigo_ISIN"].last().to_dict()
    ult = df.groupby("CNPJ_Classe").tail(1)
    limite = (pd.Timestamp(ult["Data_Referencia"].max()) - pd.DateOffset(months=4)).strftime("%Y-%m-%d")
    ult = ult[ult["Data_Referencia"] >= limite]  # só quem segue entregando o informe

    cnpjs = [cnpj_fmt(c) for c in ult["CNPJ_Classe"]]
    tickers = aplicar_manuais(cnpjs, [ticker_do_isin(isin.get(c)) for c in ult["CNPJ_Classe"]])
    fundos = []
    for (_, r), cnpj, tk in zip(ult.iterrows(), cnpjs, tickers):
        cra, cri = num(r["CRA"]), num(r["CRI"])
        bolsa = r["Mercado_Negociacao"] == "BOLSA"
        if not tk and not bolsa and cra + cri <= 0:
            continue  # fora da bolsa e sem CRA/CRI: nada para acompanhar
        pl = num(r["Patrimonio_Liquido"])
        comp = {rot: round(num(r[col]), 2) for rot, col in COMPOSICAO if num(r[col]) > 0}
        prazo = num(r["Total_Ativos_Prazo_Vencimento"])
        fundos.append({
            "cnpj_fundo": cnpj, "ticker": tk, "fundo": limpo(r["Nome_Classe"]),
            "gestor": limpo(r["Nome_Gestor"]), "cnpj_gestor": so_digitos(r["CNPJ_Gestor"]) or None,
            "administrador": limpo(r["Nome_Administrador"]), "mercado": limpo(r["Mercado_Negociacao"]),
            "listado": bool(tk), "pl": round(pl, 2) or None, "data_pl": r["Data_Referencia"][:7],
            "ativo": round(num(r["Valor_Ativo"]), 2) or None, "cra": round(cra, 2), "cri": round(cri, 2),
            "composicao": comp, "cotistas": int(num(r["Numero_Cotistas"])) or None,
            "dy_mes": round(num(r["Dividend_Yield_Mes"]), 6) or None,
            "prazo_total": round(prazo, 2) or None, "vencidos": round(num(r["Vencidos"]), 2),
            "vencidos_90": round(sum(num(r[c]) for c in ("Vencidos_91a120Dias", "Vencidos_121a180Dias", "Vencidos_181a360Dias",
                                                         "Vencidos_361a720Dias", "Vencidos_721a1080Dias", "Vencidos_Acima1080Dias")), 2),
        })
    return fundos


# ---------------------------------------------------------------- relatórios gerenciais

def _data(br):
    try:
        return datetime.strptime((br or "")[:10], "%d/%m/%Y").date()
    except ValueError:
        return None


def atualizar_gerenciais(fundos: list[dict], antigo: dict, hoje: date, consultar: bool = True):
    """Guarda em cada fundo o relatório gerencial mais recente, baixando só os que mudaram."""
    from fnet import BASE as FNET, Fnet  # importa só aqui: o resto do módulo não depende do Fundos.Net
    GER.mkdir(parents=True, exist_ok=True)
    previos = {f["cnpj_fundo"]: f.get("gerencial") for f in antigo.get("fundos", [])}
    alvo = [f for f in fundos if f["cra"] + f["cri"] > 0]
    # quem foi consultado há mais tempo vai primeiro; os demais ficam com o relatório já guardado
    alvo.sort(key=lambda f: (previos.get(f["cnpj_fundo"]) or {}).get("checado", ""))
    for f in fundos:
        f["gerencial"] = previos.get(f["cnpj_fundo"])
    api, inicio, n = None, time.time(), 0
    for f in (alvo if consultar else []):
        g = f.get("gerencial") or {}
        if g.get("checado") and (hoje - date.fromisoformat(g["checado"])).days < RECHECAR_DIAS:
            continue
        if time.time() - inicio > ORCAMENTO_S:
            print("tempo da rodada esgotado; os demais relatórios ficam para a próxima", file=sys.stderr)
            break
        cnpj = so_digitos(f["cnpj_fundo"])
        try:
            api = api or Fnet(pausa=0.5)
            r = api.get(f"{FNET}/pesquisarGerenciadorDocumentosDados", params={
                "d": 1, "s": 0, "l": 12, "o[0][dataEntrega]": "desc", "cnpjFundo": cnpj,
                "idCategoriaDocumento": 7, "isSession": "false"})
            r.raise_for_status()
            itens = [i for i in (r.json().get("data") or []) if not str(i.get("status", "")).startswith("C")]
            doc = next((i for i in itens if "gerencial" in (i.get("tipoDocumento") or "").lower()), None) or (itens[0] if itens else None)
            novo = {"checado": hoje.isoformat()}
            if doc:
                entrega = _data(doc.get("dataEntrega"))
                novo.update({"doc_id": doc["id"], "data_entrega": entrega.isoformat() if entrega else None,
                             "referencia": doc.get("dataReferencia"), "tipo": (doc.get("tipoDocumento") or "").strip()})
                txt = GER / f"{cnpj}.txt"
                if g.get("doc_id") != doc["id"] or not txt.exists():
                    pdf = api.baixar(doc["id"], RAW / "tmp" / f"{doc['id']}.pdf")
                    if pdf.read_bytes()[:5] == b"%PDF-":
                        subprocess.run(["pdftotext", "-layout", "-l", "40", str(pdf), str(txt)], check=False, timeout=90,
                                       stderr=subprocess.DEVNULL)
                    else:
                        txt.write_text(pdf.read_bytes().decode("utf-8", "ignore"))
                    pdf.unlink(missing_ok=True)
                    n += 1
            f["gerencial"] = novo
        except Exception as e:  # segue com os demais; o fundo entra na próxima rodada
            print(f"relatório de {f['ticker'] or cnpj}: {e}", file=sys.stderr)
    print(f"{n} relatórios gerenciais novos", file=sys.stderr)
    for f in fundos:  # relatório velho não liga evento
        g = f["gerencial"] = f.get("gerencial") or {}
        d = g.get("data_entrega")
        g["valido"] = bool(d and (hoje - date.fromisoformat(d)).days <= IDADE_MAX_RELATORIO
                           and (GER / f"{so_digitos(f['cnpj_fundo'])}.txt").exists())


def main():
    hoje = date.today()
    antigo = json.loads(OUT.read_text()) if OUT.exists() else {}
    fundos = montar(hoje)
    atualizar_gerenciais(fundos, antigo, hoje, consultar="--sem-relatorios" not in sys.argv)
    ref = max((f["data_pl"] for f in fundos), default=None)
    res = {"data_referencia": ref, "gerado_em": hoje.isoformat(), "fundos": fundos}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    com = sum(1 for f in fundos if (f.get("gerencial") or {}).get("valido"))
    print(json.dumps({"fiagros": len(fundos), "com_ticker": sum(1 for f in fundos if f["ticker"]),
                      "com_cra": sum(1 for f in fundos if f["cra"] > 0), "relatorios_validos": com,
                      "referencia": ref}, ensure_ascii=False), file=sys.stderr)


if __name__ == "__main__":
    main()
