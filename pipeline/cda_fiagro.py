"""CRAs na carteira dos Fiagros, pela Composição da Carteira (CDA) entregue no Fundos.Net.

O CDA do Fiagro não traz o código do CRA: traz a securitizadora (CNPJ), o vencimento, a taxa e o
valor de cada título. O código vem do Informe Mensal de CRA que as securitizadoras entregam à CVM
(dados abertos), que lista cada série com CNPJ da emissora, vencimento, taxa, código CETIP e ISIN.
Cruzando os dois, chegamos ao código do CRA e ao peso dele no PL do Fiagro.

Limites: o CDA sai com atraso (a última carteira costuma ter dois a três meses), e nem toda
securitizadora aparece no informe da CVM; o que não fecha fica de fora, sem chute.
"""
import io
import re
import sys
import time
import zipfile
from datetime import date

import pandas as pd
import requests

URL_SECURIT = "https://dados.cvm.gov.br/dados/SECURIT/DOC/INF_MENSAL_CRA/DADOS/inf_mensal_cra_{ano}.zip"
COD_CRA = "36"           # código do tipo de ativo "CRA" no CDA
RECHECAR_CDA_DIAS = 7    # o CDA de Fiagro sai por trimestre: basta olhar uma vez por semana


def so_digitos(s) -> str:
    return re.sub(r"\D", "", str(s or ""))


def num_br(s):
    try:
        return float(str(s).strip().replace(".", "").replace(",", ".")) if s and str(s).strip() else None
    except ValueError:
        return None


# ------------------------------------------------------------------ informe das securitizadoras

def indice_securitizadoras(raw, hoje: date) -> dict:
    """(CNPJ da emissora, vencimento AAAA-MM-DD) -> séries de CRA com esse vencimento."""
    quadros = []
    for ano in (hoje.year - 1, hoje.year):
        destino = raw / f"inf_mensal_cra_{ano}.zip"
        if not destino.exists() or time.time() - destino.stat().st_mtime > 5 * 86400:
            r = requests.get(URL_SECURIT.format(ano=ano), timeout=120)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            destino.write_bytes(r.content)
        with zipfile.ZipFile(destino) as z:
            def ler(parte):
                nome = next(n for n in z.namelist() if parte in n)
                with z.open(nome) as f:
                    return pd.read_csv(io.TextIOWrapper(f, encoding="latin1"), sep=";", dtype=str)
            classe, geral = ler("_classe_"), ler("_geral_")
        geral = geral.sort_values("Data_Referencia").drop_duplicates("Codigo_Identificacao_Certificado", keep="last")
        quadros.append(classe.merge(geral[["Codigo_Identificacao_Certificado", "Numero_Emissao", "Nome_Emissao"]],
                                    on="Codigo_Identificacao_Certificado", how="left"))
    if not quadros:
        return {}
    df = pd.concat(quadros, ignore_index=True).dropna(subset=["Codigo_CETIP", "Data_Vencimento"])
    df["cn"] = df["CNPJ_Emissora"].map(so_digitos).str.zfill(14)
    df = df.sort_values("Data_Referencia").drop_duplicates(["cn", "Codigo_CETIP"], keep="last")
    txt = lambda v: v.strip() if isinstance(v, str) else ""  # células vazias chegam como NaN
    indice = {}
    for r in df.itertuples():
        indice.setdefault((r.cn, txt(r.Data_Vencimento)[:10]), []).append({
            "cetip": txt(r.Codigo_CETIP), "isin": txt(r.Codigo_ISIN) or None,
            "emissao_id": txt(r.Codigo_Identificacao_Certificado) or None, "emissao": txt(r.Numero_Emissao) or None,
            "serie": txt(r.Numero_Serie), "taxa": txt(r.Taxa_Juros), "nome": txt(r.Nome_Emissao),
        })
    return indice


def _taxas(texto):
    return [float(x.replace(",", ".")) for x in re.findall(r"(\d+(?:[.,]\d+)?)\s*%", texto or "")]


def resolver(cra: dict, indice: dict) -> dict:
    """Acha a série (ou ao menos a emissão) de um CRA do CDA no informe das securitizadoras."""
    cands = indice.get((cra["cnpj_emissor"], cra["venc"]), [])
    if not cands:
        return {}
    if len({c["cetip"] for c in cands}) > 1 and cra.get("cupom") is not None:
        pela_taxa = [c for c in cands if any(abs(t - cra["cupom"]) < 0.06 for t in _taxas(c["taxa"]))]
        cands = pela_taxa or cands
    series = {c["cetip"] for c in cands}
    emissoes = {c["emissao_id"] for c in cands if c["emissao_id"]}
    if len(series) == 1:
        c = cands[0]
        return {"nivel": "serie", "codigos": sorted({c["cetip"]} | ({c["isin"]} if c["isin"] else set())),
                "emissoes": sorted(emissoes), "emissao": c["emissao"], "serie": c["serie"], "nome": c["nome"]}
    if len(emissoes) == 1:  # várias séries com o mesmo vencimento, mas da mesma emissão
        return {"nivel": "emissao", "codigos": sorted({c["cetip"] for c in cands} | {c["isin"] for c in cands if c["isin"]}),
                "emissoes": sorted(emissoes), "emissao": cands[0]["emissao"], "serie": None, "nome": cands[0]["nome"]}
    return {}


# ------------------------------------------------------------------ CDA no Fundos.Net

def ler_cda(texto: str):
    """Lê o XML do CDA com expressões simples (sem parser de XML: o arquivo vem de fora)."""
    pl = num_br((re.search(r"<VL_PL>([^<]*)</VL_PL>", texto) or [None, None])[1])
    cras = []
    for b in re.findall(r"<TIT_AGRO_CRED_PRIV>(.*?)</TIT_AGRO_CRED_PRIV>", texto, re.S):
        campo = lambda t: (re.search(rf"<{t}>([^<]*)</{t}>", b) or [None, ""])[1].strip()
        if campo("COD_TP_ATIV") != COD_CRA:
            continue
        venc = campo("DT_VENC")
        if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", venc):
            continue
        cras.append({
            "emissor": re.sub(r"\s+", " ", campo("NM_EMIS"))[:80], "cnpj_emissor": so_digitos(campo("NR_PF_PJ_EMIS")).zfill(14),
            "venc": f"{venc[6:]}-{venc[3:5]}-{venc[:2]}", "indexador": campo("TIT_POS_FIX_COD_INDEX") or ("PRE" if campo("TIT_PRE_FIX_TAXA_CONTR") else ""),
            "cupom": num_br(campo("TIT_POS_FIX_CUPOM")) if campo("TIT_POS_FIX_CUPOM") else num_br(campo("TIT_PRE_FIX_TAXA_CONTR")),
            "valor": num_br(campo("MERC_POS_FIM")) or 0.0, "qtde": num_br(campo("QTDE_POS_FIM")),
        })
    return pl, cras


def atualizar_cdas(fundos, antigo, hoje: date, api_fabrica, fnet_base, tmp, orcamento_s: float, consultar=True):
    previos = {f["cnpj_fundo"]: f.get("cda") for f in antigo.get("fundos", [])}
    for f in fundos:
        f["cda"] = previos.get(f["cnpj_fundo"])
    alvo = sorted((f for f in fundos if f["cra"] > 0), key=lambda f: (f.get("cda") or {}).get("checado", ""))
    inicio, n, api = time.time(), 0, None
    for f in (alvo if consultar else []):
        c = f.get("cda") or {}
        if c.get("checado") and (hoje - date.fromisoformat(c["checado"])).days < RECHECAR_CDA_DIAS:
            continue
        if time.time() - inicio > orcamento_s:
            print("tempo da rodada esgotado; os demais CDAs ficam para a próxima", file=sys.stderr)
            break
        cnpj = so_digitos(f["cnpj_fundo"])
        try:
            api = api or api_fabrica()
            r = api.get(f"{fnet_base}/pesquisarGerenciadorDocumentosDados", params={
                "d": 1, "s": 0, "l": 10, "o[0][dataEntrega]": "desc", "cnpjFundo": cnpj,
                "idCategoriaDocumento": 6, "isSession": "false"})
            r.raise_for_status()
            doc = next((i for i in (r.json().get("data") or [])
                        if "CDA" in (i.get("tipoDocumento") or "") and not str(i.get("status", "")).startswith("C")), None)
            novo = {**c, "checado": hoje.isoformat()}
            if doc and doc["id"] != c.get("doc_id"):
                destino = api.baixar(doc["id"], tmp / f"cda_{doc['id']}.xml")
                bruto = destino.read_bytes()
                destino.unlink(missing_ok=True)
                texto = bruto.decode("cp1252", "ignore") if b"Windows-1252" in bruto[:100] else bruto.decode("utf-8", "ignore")
                pl, cras = ler_cda(texto)
                novo = {"checado": hoje.isoformat(), "doc_id": doc["id"], "referencia": doc.get("dataReferencia"),
                        "pl": pl, "cras": cras}
                n += 1
            f["cda"] = novo
        except Exception as e:  # o fundo entra na próxima rodada
            print(f"CDA de {f['ticker'] or cnpj}: {e}", file=sys.stderr)
    print(f"{n} CDAs novos", file=sys.stderr)


def aplicar_codigos(fundos, indice):
    """Grava em cada CRA do CDA os códigos encontrados no informe das securitizadoras."""
    por_emissao = {}
    for cands in indice.values():
        for c in cands:
            if c["emissao_id"]:
                por_emissao.setdefault(c["emissao_id"], set()).update({c["cetip"], c["emissao_id"]} | ({c["isin"]} if c["isin"] else set()))
    total = achados = 0
    for f in fundos:
        for cra in (f.get("cda") or {}).get("cras", []):
            total += 1
            cra.update({"nivel": None, "codigos": [], "emissoes": [], "codigos_emissao": [], "emissao": None, "serie": None, "nome": ""})
            r = resolver(cra, indice)
            if r:
                cra.update(r)
                # todos os códigos da emissão: o documento da securitizadora pode citar outra série
                cra["codigos_emissao"] = sorted(set().union(*(por_emissao.get(e, set()) for e in r["emissoes"])) | set(r["codigos"]))
                achados += 1
    print(f"CRAs no CDA dos Fiagros: {total}; com código identificado: {achados}", file=sys.stderr)
    return total, achados
