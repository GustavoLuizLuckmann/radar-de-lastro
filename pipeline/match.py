"""Liga documentos de CRI e CRA do Fundos.Net aos fundos.

FIIs: posições do informe trimestral (código IF, ou emissão e série).
Fiagros: nome da operação citado no relatório gerencial mais recente do fundo (a CVM não divulga
os códigos dos CRAs na carteira dos Fiagros).
"""
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
    "ISEC": ["VIRGO", "ISEC", "RIZA"],
    "VIRGO": ["VIRGO", "ISEC", "RIZA"],
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
    "RIZA SEC": ["RIZA", "VIRGO", "ISEC"],
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
        if doc.get("tipo") == "CRA" or norm(doc["securitizadora"]).strip() in NUMERACAO_AMBIGUA:
            # os informes de FII só trazem CRI; um CRA com a mesma emissão e série seria outro título
            return [], None
        tts = [norm(t) for t in termos(doc["securitizadora"])]
        series = [str(int(doc["serie"]) + i) for i in range(doc.get("outras_series", 0) + 1)] if doc["serie"].isdigit() else [doc["serie"]]
        achados = []
        for s in series:
            for p in self.por_emissao.get((doc["emissao"], s), []):
                if any(t in norm(p["descricao"]) for t in tts):
                    achados.append(p)
        return achados, ("emissao_serie" if achados else None)


# palavras que não identificam um devedor sozinhas
GENERICOS = set("""
DIVERSIFICADO DIVERSIFICADA PULVERIZADO PULVERIZADA MULTIPLOS MULTIPLAS DIVERSOS VARIOS CARTEIRA PORTFOLIO
REVENDA REVENDAS PRODUTOR PRODUTORES RURAL RURAIS AGRO AGROPECUARIA AGROPECUARIO AGRONEGOCIO AGRONEGOCIOS
AGRICOLA AGRICOLAS AGROINDUSTRIAL ALIMENTOS ALIMENTO INSUMOS COOPERATIVA COOP COOPERATIVAS GRUPO CIA COMPANHIA
LTDA EIRELI HOLDING PARTICIPACOES INDUSTRIA INDUSTRIAS COMERCIO COMERCIAL DISTRIBUIDORA FAZENDA FAZENDAS
CORP CORPORATIVO CORPORATIVA BRASIL BRASILEIRA NACIONAL ENERGIA BIOENERGIA SERVICOS EMPREENDIMENTOS
CRA CRI SERIE SERIES EMISSAO SENIOR SUBORDINADA MEZANINO UNICA NOVA NOVO SAO SANTA SANTO
IMOBILIARIO IMOBILIARIA LOGISTICA FINANCEIRA CREDITO CREDITOS RECEBIVEIS SECURITIZADORA SECURITIZACAO
USINA USINAS FIDC FUNDO FIAGRO ESTADO MUNICIPIO TRADING CEREAIS GRAOS
""".split())
SUFIXOS = {"SA", "S", "A", "LTDA", "ME", "EPP", "EIRELI", "DE", "DA", "DO", "DAS", "DOS", "E", "EM"}
LINHA_TABELA = re.compile(r"%|R\$|\d{1,3}(?:\.\d{3}){2,}|\d{2}/\d{2}/\d{4}")  # linha de tabela: valor, taxa ou data
CRA_RE = re.compile(r"(?<![0-9A-Z])(CRA0\d{2}[0-9A-Z]{5})(?![0-9A-Z])")


def _nome_devedor(operacao: str) -> list[str]:
    """'São Salvador Aliment 11/2020' -> ['SAO', 'SALVADOR'] (o Fundos.Net corta o nome em 20 letras)."""
    bruto = re.sub(r"\s+\d{2}/\d{4}\s*$", "", operacao or "").strip()
    cortado = len(bruto) >= 20
    toks = [t for t in norm(bruto).split() if not t.isdigit()]
    if cortado and len(toks) > 1:
        toks = toks[:-1]  # última palavra provavelmente pela metade
    while toks and toks[-1] in SUFIXOS:
        toks.pop()
    return toks[:3]


def padroes_operacao(operacao: str):
    """Expressões que, achadas no relatório gerencial, indicam esta operação.

    Devolve (fortes, comuns): 'fortes' exigem o nome logo depois de CRA/CRI ('CRA Boa Safra');
    'comuns' valem sozinhas, mas só para nomes que não se confundem com palavras do dia a dia.
    """
    toks = _nome_devedor(operacao)
    if not toks or all(t in GENERICOS for t in toks):
        return [], []
    frase = " ".join(toks)
    uteis = [t for t in toks if t not in GENERICOS]
    # só a primeira palavra ("CRA Jalles" para "Jalles Machado") quando ela não é uma sigla curta:
    # "CRA SLC" serviria tanto para SLC Agrícola quanto para SLC Máquinas
    fortes = [frase] + ([toks[0]] if len(toks) > 1 and toks[0] not in GENERICOS and len(toks[0]) >= 4 else [])
    comuns = []
    if len(frase) >= 8 and any(len(t) >= 4 for t in uteis):
        comuns.append(frase)
    if len(toks) > 1 and len(uteis[0]) >= 7 and uteis[0] == toks[0]:
        comuns.append(uteis[0])
    return fortes, comuns


class IndiceGerencial:
    """Procura o nome de cada operação nos relatórios gerenciais dos Fiagros."""

    def __init__(self, fiagros: list[dict], pasta: Path):
        self.textos = []
        for f in fiagros:
            g = f.get("gerencial") or {}
            arq = pasta / (re.sub(r"\D", "", f["cnpj_fundo"]) + ".txt")
            if not g.get("valido") or not arq.exists():
                continue
            linhas = [" ".join(norm(l).split()) for l in arq.read_text(errors="ignore").splitlines()]
            originais = [" ".join(l.split()) for l in arq.read_text(errors="ignore").splitlines()]
            self.textos.append((f, linhas, originais))
        self._cache = {}

    def casar(self, doc, texto: str | None = None) -> list[dict]:
        """Fiagros cujo relatório gerencial cita a operação.

        Primeiro pelo código IF do CRA citado no documento (confiança alta); se o documento não
        trouxer código, pelo nome do devedor (pode ser outra série do mesmo devedor).
        """
        tipo = doc.get("tipo") or "CRI"
        campo = "cra" if tipo == "CRA" else "cri"
        codigos = set(CRA_RE.findall(texto or "")) if tipo == "CRA" else set(IF_RE.findall(texto or ""))
        if doc.get("codigo_if"):
            codigos.add(doc["codigo_if"])
        achados, vistos = [], set()
        if codigos:
            re_cod = re.compile(r"(?<![0-9A-Z])(?:" + "|".join(sorted(codigos)) + r")(?![0-9A-Z])")
            for f, linhas, originais in self.textos:
                if not f.get(campo):
                    continue
                i = next((i for i, l in enumerate(linhas) if re_cod.search(l)), None)
                if i is not None:
                    achados.append({"fiagro": f, "trecho": originais[i][:180], "metodo": "codigo",
                                    "codigo": re_cod.search(linhas[i]).group(0)})
                    vistos.add(f["cnpj_fundo"])
        chave = (tipo, doc.get("operacao"))
        if chave not in self._cache:
            self._cache[chave] = self._por_nome(tipo, campo, doc.get("operacao"))
        for a in self._cache[chave]:
            if a["fiagro"]["cnpj_fundo"] in vistos:
                continue
            # a linha do relatório traz o código de outro CRA do mesmo devedor: é outra série, não esta
            na_linha = set(CRA_RE.findall(a["trecho"].upper())) | set(IF_RE.findall(a["trecho"]))
            if codigos and na_linha and not (na_linha & codigos):
                continue
            achados.append(a)
        return achados

    def _por_nome(self, tipo, campo, operacao):
        fortes, comuns = padroes_operacao(operacao)
        if not (fortes or comuns):
            return []
        re_forte = re.compile(r"\b" + tipo + r"S? (?:" + "|".join(map(re.escape, fortes)) + r")\b") if fortes else None
        re_comum = re.compile(r"\b(?:" + "|".join(map(re.escape, comuns)) + r")\b") if comuns else None
        achados = []
        for f, linhas, originais in self.textos:
            if not f.get(campo):
                continue  # o informe mensal diz que o fundo não tem esse tipo de título
            for i, l in enumerate(linhas):
                if re.match(r"(\d+ )?CPR", l) and tipo not in l:
                    continue  # linha de CPR do mesmo devedor: é outro título
                if (re_forte and re_forte.search(l)) or (re_comum and re_comum.search(l) and LINHA_TABELA.search(l)):
                    achados.append({"fiagro": f, "trecho": originais[i][:180], "metodo": "nome"})
                    break
        return achados


class IndiceCarteiraFiagro:
    """CRAs da carteira (CDA) dos Fiagros, já com código, para ligar documentos com valor e % do PL."""

    def __init__(self, fiagros: list[dict]):
        self.por_codigo = {}
        for f in fiagros:
            cda = f.get("cda") or {}
            for cra in cda.get("cras", []):
                for cod in cra.get("codigos_emissao") or []:
                    self.por_codigo.setdefault(cod, []).append((f, cda, cra))

    def casar(self, doc, texto: str | None = None) -> list[dict]:
        if doc.get("tipo") != "CRA":
            return []
        chaves = set(CRA_RE.findall(texto or "")) | {c for c in (doc.get("isin"), doc.get("codigo_if")) if c}
        por_fundo = {}
        for cod in chaves:
            for f, cda, cra in self.por_codigo.get(cod, []):
                x = por_fundo.setdefault(f["cnpj_fundo"], {"fiagro": f, "cda": cda, "cras": {}})
                x["cras"][id(cra)] = cra
        achados = []
        for x in por_fundo.values():
            valor = sum(c["valor"] for c in x["cras"].values())
            pl = x["cda"].get("pl") or x["fiagro"].get("pl")
            cods = sorted({c for cra in x["cras"].values() for c in cra.get("codigos", []) if c.startswith("CRA")})
            achados.append({"fiagro": x["fiagro"], "metodo": "carteira", "valor": round(valor, 2),
                            "pct_pl": round(valor / pl, 6) if pl else None, "ref": x["cda"].get("referencia"),
                            "trecho": f"Carteira de {x['cda'].get('referencia')}: {', '.join(cods) or 'CRA desta emissão'}"})
        return achados


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
