"""Classificação por regras dos documentos de CRI em eventos de crédito.

O texto é normalizado sem mudar de tamanho (cada letra acentuada vira a letra base), então os
índices encontrados no texto normalizado valem para o original e o trecho exibido é o do documento.

Assembleias são lidas a partir da "ordem do dia", para olhar a pauta e não o texto padrão
(certidões, hipóteses de vencimento antecipado listadas no termo etc.). Fatos relevantes,
comunicados e avisos são lidos no corpo.

Documentos sem tema de crédito (AGO de contas, por exemplo) ficam fora do radar.
"""
import re
import unicodedata

MESES = {m: i for i, m in enumerate(
    ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
     "novembro", "dezembro"], start=1)}
DATA_RE = re.compile(r"(\d{1,2})\s*(?:º|o)?\s+de\s+(" + "|".join(MESES) + r")\s+de\s+(\d{4})")
INFORMATIVOS = {"Fato Relevante", "Comunicado ao Mercado", "Aviso aos Investidores"}


def _base(c: str) -> str:
    b = unicodedata.normalize("NFKD", c)[0].lower()
    return b if len(b) == 1 else c.lower()


def plano(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def norm(texto: str) -> str:
    """Mesmo tamanho do texto de entrada: minúsculo e sem acento."""
    return "".join(_base(c) for c in texto)


# (tipo, severidade, padrões (qualquer um), onde vale: None = todos | "info" = só informativos)
REGRAS = [
    ("Recuperação judicial ou falência do devedor", "crit", [
        r"(ajuizou|ajuizamento|ajuizad[oa]|deferimento|deferiu|deferid[oa]|processamento|requereu|distribuiu) (o |a |de |do |da |pedido de |sua )*recuperacao (judicial|extrajudicial)",
        r"(encontra-se|esta|estao|em processo de) em recuperacao (judicial|extrajudicial)",
        r"(decretacao|decretou|decretada) (a |da )?falencia",
        r"plano de recuperacao judicial",
    ], None),
    ("Vencimento antecipado declarado", "crit", [
        r"(declarad[oa]|declarou|declarara|foi declarado) o vencimento antecipado",
        r"vencimento antecipado (foi|ficou|restou) declarado",
        r"em razao do vencimento antecipado (dos|das) (cri|creditos)",
    ], "info"),
    ("Execução de garantias", "crit", [
        r"(excussao|execucao) (das|da|de) garantia",
        r"consolidacao da propriedade",
        r"leilao (do|dos|de) imove",
    ], None),
    ("Pagamento não realizado", "crit", [
        r"nao foi realizad[oa]",
        r"nao (foi|foram) (pag|efetuad|honrad)",
        r"insuficiencia de recursos",
        r"inadimplemento (total|parcial)",
        r"nao foi identificado o recebimento",
        r"valores inadimplidos",
        r"(nao realizacao|ausencia) (do|de) (pagamento|aporte)",
    ], "info"),
    ("Assembleia sobre vencimento antecipado", "warn", [
        r"(nao )?declaracao (ou nao )?(do|de) vencimento antecipado",
        r"(declarar|declaracao) ou nao (o|do) vencimento antecipado",
        r"nao declarar o vencimento antecipado",
    ], None),
    ("Assembleia sobre inadimplemento", "warn", [
        r"(inadimplemento|inadimplencia|atraso) (no|do|de|da) pagamento",
        r"valores inadimplidos",
        r"encargos moratorios",
    ], None),
    ("Uso do fundo de reserva", "warn", [
        r"fundo de reserva.{0,120}(utilizad|utilizac|recompo|desenquadr|insuficien)",
        r"(utiliz\w*|recompo\w*|desenquadr\w*) .{0,80}fundo de reserva",
    ], None),
    ("Pedido de waiver", "warn", [
        r"\bwaiver\b", r"renuncia previa", r"perdao temporario", r"anuencia previa (para|ao|a)",
    ], None),
    ("Garantia ou covenant desenquadrado", "warn", [
        r"(desenquadramento|descumprimento|reenquadramento) (da|do|das|dos) (razao|indice|covenant|garantia|limite)",
        r"razao (minima )?de garantia.{0,80}(abaixo|inferior|desenquadr|descumpr)",
        r"reforco (de|da|das) garantia",
        r"\bcovenants?\b",
        r"indices? financeiros?.{0,80}(descumpr|desenquadr|nao atend)",
    ], None),
    ("Repactuação ou carência", "warn", [
        r"repactuacao", r"periodo de carencia", r"alteracao do cronograma", r"novo cronograma",
        r"prorrogacao (do|da|das) (data de )?vencimento", r"reperfilamento",
    ], None),
    ("Rebaixamento de rating", "warn", [
        r"rebaix\w+ (do|da|de) (rating|classificacao)", r"\bdowngrade\b",
    ], None),
    ("Amortização extraordinária ou resgate antecipado", "mon", [
        r"amortizacao extraordinaria", r"resgate antecipado", r"pre-?pagamento", r"quitacao integral",
    ], None),
    ("Troca de garantia", "mon", [
        r"substituicao (de|da|das) garantia", r"liberacao (de|da|das|parcial) (de |da |das )?garantia",
    ], None),
    ("Troca de prestador da operação", "mon", [
        r"substituicao (do|da) agente fiduciari", r"substituicao da (emissora|securitizadora)",
        r"substituicao do (servicer|custodiante)",
    ], None),
]


def regiao(doc, texto_plano: str, texto_norm: str):
    """Onde procurar: pauta da assembleia ou corpo do comunicado. Devolve (início, fim)."""
    if doc["categoria"] == "Assembleia":
        m = re.search(r"ordem do dia", texto_norm)
        if m:
            return m.start(), min(len(texto_norm), m.start() + 3500)
        return 0, min(len(texto_norm), 5000)
    return 0, min(len(texto_norm), 9000)


def fase(doc):
    esp = doc.get("especie") or ""
    if esp in ("Edital de Convocação", "Proposta do Administrador"):
        return "convocada"
    if esp in ("Ata da Assembleia", "Sumário das Decisões"):
        return "deliberada"
    return "informada"


def data_assembleia(texto_norm: str):
    for gat in (r"a ser realizada", r"realizar-se-a", r"em primeira convocacao", r"sera realizada"):
        m = re.search(gat, texto_norm)
        if not m:
            continue
        d = DATA_RE.search(texto_norm, m.start(), m.start() + 300)
        if d:
            dia, mes, ano = int(d.group(1)), MESES[d.group(2)], int(d.group(3))
            if 1 <= dia <= 31:
                return f"{ano:04d}-{mes:02d}-{dia:02d}"
    return None


def frase(texto_plano: str, ini: int, fim: int, tamanho: int = 280):
    """Frase do documento em volta do trecho encontrado, cortada com reticências se for longa."""
    a = texto_plano.rfind(". ", 0, ini)
    a = 0 if a == -1 else a + 2
    b = texto_plano.find(". ", fim)
    b = len(texto_plano) if b == -1 else b + 1
    if b - a <= tamanho:
        return texto_plano[a:b].strip()
    a = max(a, ini - tamanho // 3)
    b = min(b, a + tamanho)
    return ("…" if a > 0 else "") + texto_plano[a:b].strip() + "…"


def classificar(doc, texto: str):
    """Retorna dict com tipo, severidade, fase, trecho e data_assembleia, ou None se não for evento."""
    tp = plano(texto)
    if not tp:
        return None
    tn = norm(tp)
    ini, fim = regiao(doc, tp, tn)
    informativo = doc["categoria"] in INFORMATIVOS
    for tipo, sev, padroes, onde in REGRAS:
        if onde == "info" and not informativo:
            continue
        for p in padroes:
            for m in re.finditer(p, tn[ini:fim]):
                a, b = ini + m.start(), ini + m.end()
                contexto = tn[max(0, a - 150): b + 50]
                if "certid" in contexto or "hipoteses de vencimento" in contexto:
                    continue  # texto padrão, não é o evento
                antes = tn[max(0, a - 70): a]
                if not p.startswith(("nao", "(nao")) and re.search(r"\b(nao|sem|nenhuma?|qualquer)\b", antes):
                    continue  # negação: "não foi declarado o vencimento antecipado", "não será adotada excussão"
                f = fase(doc)
                return {
                    "tipo": tipo, "severidade": sev, "fase": f,
                    "trecho": frase(tp, a, b),
                    "data_assembleia": data_assembleia(tn) if f == "convocada" else None,
                }
    return None
