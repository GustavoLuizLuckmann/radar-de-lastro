"""Cliente mínimo da consulta pública do Fundos.Net (B3/CVM) para documentos de CRI/CRA."""
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

BASE = "https://fnet.bmfbovespa.com.br/fnet/publico"
# O firewall do Fundos.Net muda as regras de tempos em tempos (já recusou o User-Agent padrão do
# requests e já recusou identificações próprias). Começamos com um navegador comum e, se vier 403,
# tentamos as alternativas abaixo.
AGENTES = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "curl/8.5.0",
    None,  # padrão do requests
]
HEADERS = {"X-Requested-With": "XMLHttpRequest", "User-Agent": AGENTES[0]}

# Categorias da página de certificados (CRI/CRA) que podem carregar eventos de crédito
CATEGORIAS = {
    1: "Fato Relevante",
    2: "Assembleia",
    3: "Comunicado ao Mercado",
    20: "Aviso aos Investidores",
    35: "Recuperação Judicial",
    36: "Relatório de agência classificadora de risco",
}

DESC_RE = re.compile(
    r"^(?P<sec>.+?)\s+(?P<tipo>CRI|CRA)\s+Emiss[aã]o:\s*(?P<emissao>\d+)\s+S[ée]rie(?:\(s\))?:\s*(?P<serie>\d+)"
    r"(?:\s*\(\+(?P<mais>\d+)\))?\s*(?P<nome>.*?)\s*(?P<codigo>BR[A-Z0-9]{10}|\d{2}[A-L]\d{7})?\s*$"
)


class Fnet:
    def __init__(self, pausa: float = 0.4):
        self.s = requests.Session()
        self.s.headers.update(HEADERS)
        self.pausa = pausa
        self.get(f"{BASE}/abrirGerenciadorDocumentosCVM?paginaCertificados=true")

    def trocar_agente(self):
        atual = self.s.headers.get("User-Agent")
        i = AGENTES.index(atual) if atual in AGENTES else 0
        novo = AGENTES[(i + 1) % len(AGENTES)]
        if novo:
            self.s.headers["User-Agent"] = novo
        else:
            self.s.headers["User-Agent"] = requests.utils.default_user_agent()
        self.s.cookies.clear()
        self.s.get(f"{BASE}/abrirGerenciadorDocumentosCVM?paginaCertificados=true", timeout=(15, 60))

    def get(self, url, params=None, leitura=60, tentativas=5):
        """GET com tempo limite de conexão e de leitura, e novas tentativas se o Fundos.Net demorar."""
        for i in range(tentativas):
            try:
                r = self.s.get(url, params=params, timeout=(15, leitura))
                if r.status_code == 403 and i < tentativas - 1:
                    self.trocar_agente()
                    raise requests.HTTPError("HTTP 403")
                if r.status_code >= 500 and i < tentativas - 1:
                    raise requests.HTTPError(f"HTTP {r.status_code}")
                return r
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
                if i == tentativas - 1:
                    raise
                print(f"Fundos.Net recusou ou demorou ({e}); tentando de novo", file=sys.stderr, flush=True)
                time.sleep(8 * (i + 1))  # o firewall do Fundos.Net às vezes recusa por alguns segundos

    def pesquisar(self, categoria: int, inicio: date, fim: date, por_pagina: int = 200):
        s = 0
        while True:
            params = {
                "d": 1, "s": s, "l": por_pagina, "o[0][dataEntrega]": "desc",
                "idCategoriaDocumento": categoria, "paginaCertificados": "true", "isSession": "false",
                "dataInicial": inicio.strftime("%d/%m/%Y"), "dataFinal": fim.strftime("%d/%m/%Y"),
            }
            r = self.get(f"{BASE}/pesquisarGerenciadorDocumentosDados", params=params)
            r.raise_for_status()
            dados = r.json()
            itens = dados.get("data") or []
            yield from itens
            s += len(itens)
            if not itens or s >= dados.get("recordsFiltered", 0):
                break
            time.sleep(self.pausa)

    def baixar(self, doc_id: int, destino: Path) -> Path:
        if destino.exists() and destino.stat().st_size > 0:
            return destino
        r = self.get(f"{BASE}/downloadDocumento", params={"id": doc_id}, leitura=90)
        r.raise_for_status()
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(r.content)
        time.sleep(self.pausa)
        return destino


def ler_descricao(texto: str):
    m = DESC_RE.match(" ".join((texto or "").split()))
    if not m:
        return None
    g = m.groupdict()
    codigo = g.get("codigo") or ""
    return {
        "securitizadora": g["sec"].strip(),
        "tipo": g["tipo"],
        "emissao": g["emissao"].lstrip("0") or "0",
        "serie": g["serie"].lstrip("0") or "0",
        "outras_series": int(g["mais"] or 0),
        "operacao": g["nome"].strip(),
        "isin": codigo if codigo.startswith("BR") else None,
        "codigo_if": codigo if codigo and not codigo.startswith("BR") else None,
    }
