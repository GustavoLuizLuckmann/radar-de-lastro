"""Liga documentos de CRI do Fundos.Net às posições dos FIIs no informe trimestral."""
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# De-para revisado à mão: nome curto da securitizadora no Fundos.Net -> termos que aparecem
# no campo de emissor do informe trimestral. Nomes antigos entram junto (ISEC virou Virgo etc.).
SECURITIZADORAS = {
    "OPEA": ["OPEA"],
    "RBCAPITALRES": ["RB CAPITAL", "RBCAPITAL"],
    "CANAL SEC": ["CANAL"],
    "ISEC": ["VIRGO", "ISEC"],
    "VIRGO": ["VIRGO", "ISEC"],
    "PROVINCIA": ["PROVINCIA"],
    "HABITASEC": ["HABITASEC"],
    "FORTE CAP": ["FORTE"],
    "BARI SEC": ["BARI"],
    "BRAZILIAN SC": ["BRAZILIAN"],
    "LEVERAGE SEC": ["LEVERAGE"],
    "LEVER": ["LEVERAGE"],
    "VERTCIASEC": ["VERT"],
    "REIT SEC": ["REIT"],
    "TRAVESSIASEC": ["TRAVESSIA"],
    "CASAPEDRASEC": ["CASA DE PEDRA"],
    "PLAYBANCOSEC": ["PLAYBANCO"],
    "EXES": ["EXES"],
    "BSIP": ["BSI CAPITAL"],
    "OURINVESTSEC": ["OURINVEST", "ORE SECURITIZADORA"],
    "PATRIA SEC": ["PATRIA"],
    "OCTANTE SEC": ["OCTANTE"],
    "REAG SECURIT": ["REAG"],
    "CIBRASEC": ["CIBRASEC"],
    "POLO CAP SEC": ["POLO CAPITAL"],
    "BAMBOO SEC": ["BAMBOO"],
    "BASESEC": ["BASE SECURITIZADORA"],
    "LOGOS CIA": ["LOGOS"],
    "TRUE SEC": ["TRUE SEC"],
    "TRUE": ["TRUE SEC"],
    "RIZA SEC": ["RIZA"],
    "KANASTRA": ["KANASTRA"],
    "ECO SEC": ["ECO SECURITIZADORA"],
}


# Securitizadoras que absorveram outras e têm emissões com o mesmo número em séries de ISIN
# diferentes (ex.: Opea com BRAPCS... e BRRBRA...). Sem código IF no documento, não dá para casar.
NUMERACAO_AMBIGUA = {"OPEA", "ISEC", "VIRGO", "RBCAPITALRES"}

IF_RE = re.compile(r"(?<![0-9A-Z])(\d{2}[A-L]\d{7})(?![0-9])")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9 ]+", " ", s)


def termos(securitizadora: str):
    chave = norm(securitizadora).strip()
    chave = re.sub(r"\s+", " ", chave)
    if chave in SECURITIZADORAS:
        return SECURITIZADORAS[chave]
    # sem de-para: usa a primeira palavra com 4+ letras, que costuma ser a marca
    primeira = next((p for p in chave.split() if len(p) >= 4), chave)
    return [primeira]


class Indice:
    def __init__(self, posicoes):
        self.por_if = defaultdict(list)
        self.por_emissao = defaultdict(list)  # (emissao, serie) -> posições
        for p in posicoes:
            if p["codigo_if"]:
                self.por_if[p["codigo_if"]].append(p)
            if p["emissao"] not in ("", "0") and p["serie"] not in ("", "0"):
                e = p["emissao"].lstrip("0") or "0"
                s = p["serie"].lstrip("0") or "0"
                self.por_emissao[(e, s)].append(p)

    def casar(self, doc, texto: str | None = None):
        """Retorna (posições, método).

        Ordem de confiança:
          'if'            código IF na descrição do Fundos.Net
          'if_texto'      códigos IF citados no próprio documento
          'emissao_serie' securitizadora + emissão + série (só quando o documento não cita código IF
                          e a securitizadora não reaproveita numeração de emissão entre marcas antigas)
        """
        if doc.get("codigo_if") and doc["codigo_if"] in self.por_if:
            return self.por_if[doc["codigo_if"]], "if"
        if texto:
            codigos = set(IF_RE.findall(texto))
            if codigos:
                achados = [p for c in sorted(codigos) for p in self.por_if.get(c, [])]
                return achados, ("if_texto" if achados else None)
        if norm(doc["securitizadora"]).strip() in NUMERACAO_AMBIGUA:
            return [], None
        tts = [norm(t) for t in termos(doc["securitizadora"])]
        series = [str(int(doc["serie"]) + i) for i in range(doc.get("outras_series", 0) + 1)] if doc["serie"].isdigit() else [doc["serie"]]
        achados = []
        for s in series:
            for p in self.por_emissao.get((doc["emissao"], s), []):
                if any(t in norm(p["descricao"]) for t in tts):
                    achados.append(p)
        return achados, ("emissao_serie" if achados else None)


def expor(posicoes):
    """Agrupa posições casadas por fundo, com % do PL."""
    por_fundo = {}
    for p in posicoes:
        f = por_fundo.setdefault(p["cnpj_fundo"], {
            "cnpj_fundo": p["cnpj_fundo"], "ticker": p["ticker"], "fundo": p["fundo"],
            "listado": p["listado"], "gestor": p.get("gestor"), "valor": 0.0, "pl": p["pl"], "codigos_if": set(),
        })
        f["valor"] += p["valor"]
        if p["codigo_if"]:
            f["codigos_if"].add(p["codigo_if"])
    saida = []
    for f in por_fundo.values():
        f["pct_pl"] = round(f["valor"] / f["pl"], 6) if f["pl"] else None
        f["valor"] = round(f["valor"], 2)
        f["codigos_if"] = sorted(f["codigos_if"])
        saida.append(f)
    return sorted(saida, key=lambda x: -(x["pct_pl"] or 0))


if __name__ == "__main__":
    h = json.loads((ROOT / "data" / "holdings.json").read_text())
    docs = json.loads((ROOT / "raw" / "fnet" / "docs.json").read_text())["documentos"]
    idx = Indice(h["posicoes"])
    metodos = defaultdict(int)
    for d in docs:
        pos, m = idx.casar(d)
        metodos[m] += 1
    print(dict(metodos), "de", len(docs))
