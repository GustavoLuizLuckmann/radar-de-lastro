"""Carteira de CRIs dos FIIs a partir dos dados abertos da CVM.

Fontes:
  - Informe Trimestral Estruturado de FII (tabela 'ativo'): cada CRI/CRA na carteira, com valor.
  - Informe Mensal de FII (tabelas 'geral' e 'complemento'): nome, ISIN, listagem em bolsa e PL.

Saída: data/holdings.json com um registro por (fundo, operação).
"""
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests

BASE = "https://dados.cvm.gov.br/dados/FII/DOC"
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw" / "cvm"
OUT = ROOT / "data"

# Código IF da B3/Cetip para CRI: 2 dígitos (ano) + letra (mês A-L) + 7 dígitos. Ex.: 22K1159009
IF_RE = re.compile(r"(?<![0-9A-Z])(\d{2}[A-L]\d{7})(?![0-9])")
# Código de CRA costuma vir como CRA + 9 caracteres. Ex.: CRA02300EI9
CRA_RE = re.compile(r"\b(CRA0\d{2}[0-9A-Z]{5})\b")


def baixar(caminho: str, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(f"{BASE}/{caminho}", timeout=120)
    r.raise_for_status()
    destino.write_bytes(r.content)
    return destino


def ler_zip(zpath: Path, nome: str) -> pd.DataFrame:
    with zipfile.ZipFile(zpath) as z:
        alvo = next(n for n in z.namelist() if n.startswith(nome))
        with z.open(alvo) as f:
            return pd.read_csv(io.TextIOWrapper(f, encoding="latin1"), sep=";", dtype=str)


def ultima_versao(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Versao"] = pd.to_numeric(df["Versao"], errors="coerce").fillna(1)
    mx = df.groupby(["CNPJ_Fundo_Classe", "Data_Referencia"])["Versao"].transform("max")
    return df[df["Versao"] == mx]


def ticker_do_isin(isin):
    # ISIN de cota de FII: BR + 4 letras do código de negociação + CTF + dígitos. Ex.: BRHGLGCTF004 -> HGLG11
    # também aceita o formato BRxxxxR01..., usado por algumas classes (ex.: BRARXDR01M19 -> ARXD11)
    if not isinstance(isin, str) or len(isin) < 12 or isin[6:9] not in ("CTF", "R01"):
        return None
    raiz = isin[2:6]
    return raiz + "11" if re.fullmatch(r"[A-Z]{4}", raiz) else None


def limpo(v):
    return None if v is None or (not isinstance(v, str) and pd.isna(v)) else v


def chave_reserva(cnpj, emissao, serie):
    # só serve de chave quando emissão e série existem de fato; "0" ou vazio agruparia CRIs diferentes
    if emissao in ("", "0") or serie in ("", "0"):
        return None
    return f"X:{cnpj}:{emissao}:{serie}"


def extrair_codigo(row):
    texto = " ".join(str(row[c]) for c in ("Emissor", "Nome_Ativo", "Codigo_Acao") if pd.notna(row[c]))
    m = IF_RE.search(texto) or CRA_RE.search(texto)
    return m.group(1) if m else None


def so_digitos(s):
    return re.sub(r"\D", "", s) if isinstance(s, str) else ""


def montar(ano: int, data_ref: str | None = None) -> dict:
    ztri = RAW / f"inf_trimestral_fii_{ano}.zip"
    zmen = RAW / f"inf_mensal_fii_{ano}.zip"
    if "--offline" not in sys.argv:
        baixar(f"INF_TRIMESTRAL/DADOS/inf_trimestral_fii_{ano}.zip", ztri)
        baixar(f"INF_MENSAL/DADOS/inf_mensal_fii_{ano}.zip", zmen)

    ativo = ultima_versao(ler_zip(ztri, "inf_trimestral_fii_ativo_"))
    cri = ativo[ativo["Tipo"] == "CRI/CRA"].copy()
    # trimestre mais recente com cobertura ampla (evita datas com poucos fundos já entregues)
    cont = cri.groupby("Data_Referencia")["CNPJ_Fundo_Classe"].nunique()
    data_ref = data_ref or cont[cont >= 0.5 * cont.max()].index.max()
    cri = cri[cri["Data_Referencia"] == data_ref]

    cri["valor"] = pd.to_numeric(cri["Valor"], errors="coerce").fillna(0.0)
    cri["codigo_if"] = [extrair_codigo(r) for _, r in cri.iterrows()]
    cri["codigo_if"] = cri["codigo_if"].astype(object).where(cri["codigo_if"].notna(), None)
    cri["cnpj_emissor"] = cri["CNPJ_Emissor"].map(so_digitos).str.zfill(14)
    cri["emissao"] = cri["Emissao"].fillna("").str.strip()
    cri["serie"] = cri["Serie"].fillna("").str.strip()
    # chave da operação: código IF; na falta dele, CNPJ do emissor + emissão + série
    reserva = [chave_reserva(c, e, s) for c, e, s in zip(cri["cnpj_emissor"], cri["emissao"], cri["serie"])]
    tem_if = [isinstance(c, str) for c in cri["codigo_if"]]
    cri["metodo"] = ["if" if t else ("reserva" if r else "sem_chave") for t, r in zip(tem_if, reserva)]
    cri["descricao"] = cri["Emissor"].fillna("").str.strip()
    # sem chave confiável: mantém a linha isolada para não somar CRIs diferentes
    cri["chave"] = [
        c if t else (r if r else f"N:{f}:{i}")
        for i, (c, t, r, f) in enumerate(zip(cri["codigo_if"], tem_if, reserva, cri["CNPJ_Fundo_Classe"]))
    ]

    pos = (
        cri.groupby(["CNPJ_Fundo_Classe", "chave"], as_index=False)
        .agg(valor=("valor", "sum"), codigo_if=("codigo_if", "first"), metodo=("metodo", "first"),
             cnpj_emissor=("cnpj_emissor", "first"),
             emissao=("emissao", "first"), serie=("serie", "first"), descricao=("descricao", "first"),
             vencimento=("Data_Vencimento", "first"))
    )

    # PL e dados do fundo no mês de referência do trimestre
    mes = data_ref[:7]
    geral = ultima_versao(ler_zip(zmen, "inf_mensal_fii_geral_"))
    comp = ultima_versao(ler_zip(zmen, "inf_mensal_fii_complemento_"))
    geral = geral[geral["Data_Referencia"].str[:7] <= mes].sort_values("Data_Referencia").groupby("CNPJ_Fundo_Classe").tail(1)
    comp = comp[comp["Data_Referencia"].str[:7] == mes]
    comp = comp.assign(pl=pd.to_numeric(comp["Patrimonio_Liquido"], errors="coerce"))[["CNPJ_Fundo_Classe", "pl"]]
    fundos = geral[["CNPJ_Fundo_Classe", "Nome_Fundo_Classe", "Codigo_ISIN", "Mercado_Negociacao_Bolsa",
                    "Segmento_Atuacao", "Nome_Administrador"]].merge(comp, on="CNPJ_Fundo_Classe", how="left")
    fundos["ticker"] = fundos["Codigo_ISIN"].map(ticker_do_isin)
    # tickers conferidos à mão para ISINs fora do padrão (CNPJ -> código de negociação)
    manuais = Path(__file__).with_name("tickers_manuais.json")
    if manuais.exists():
        mapa = {k: v for k, v in json.loads(manuais.read_text()).items() if not k.startswith("_") and v}
        fundos["ticker"] = [mapa.get(c, t) for c, t in zip(fundos["CNPJ_Fundo_Classe"], fundos["ticker"])]

    pos = pos.merge(fundos, on="CNPJ_Fundo_Classe", how="left")
    pos["pct_pl"] = (pos["valor"] / pos["pl"]).where(pos["pl"] > 0)

    tot_linhas = len(cri)
    resumo = {
        "data_referencia": data_ref,
        "fundos_com_cri": int(pos["CNPJ_Fundo_Classe"].nunique()),
        "operacoes": int(pos["chave"].nunique()),
        "valor_total": float(pos["valor"].sum()),
        "valor_por_metodo": {m: round(float(v / cri["valor"].sum()), 4) for m, v in cri.groupby("metodo")["valor"].sum().items()},
        "linhas_por_metodo": {m: int(n) for m, n in cri["metodo"].value_counts().items()},
    }

    registros = []
    for r in pos.itertuples(index=False):
        registros.append({
            "cnpj_fundo": r.CNPJ_Fundo_Classe, "ticker": limpo(r.ticker), "fundo": limpo(r.Nome_Fundo_Classe),
            "listado": r.Mercado_Negociacao_Bolsa == "S", "administrador": limpo(r.Nome_Administrador),
            "chave": r.chave, "metodo": r.metodo, "codigo_if": limpo(r.codigo_if), "cnpj_emissor": r.cnpj_emissor,
            "emissao": r.emissao, "serie": r.serie, "descricao": r.descricao, "vencimento": limpo(r.vencimento),
            "valor": round(float(r.valor), 2),
            "pl": None if pd.isna(r.pl) else round(float(r.pl), 2),
            "pct_pl": None if pd.isna(r.pct_pl) else round(float(r.pct_pl), 6),
        })
    return {"resumo": resumo, "posicoes": registros}


if __name__ == "__main__":
    ano = int(next((a for a in sys.argv[1:] if a.isdigit()), 2026))
    res = montar(ano)
    OUT.mkdir(exist_ok=True)
    (OUT / "holdings.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res["resumo"], ensure_ascii=False, indent=1))
