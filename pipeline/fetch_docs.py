"""Baixa os PDFs dos documentos que casaram com alguma posição de FII e extrai o texto."""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fnet import Fnet


ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "raw" / "fnet" / "pdf"
TXT = ROOT / "raw" / "fnet" / "txt"


def texto(pdf: Path, txt: Path):
    if txt.exists():
        return
    txt.parent.mkdir(parents=True, exist_ok=True)
    head = pdf.read_bytes()[:5]
    if head != b"%PDF-":
        # alguns documentos vêm como HTML ou texto puro
        txt.write_text(pdf.read_bytes().decode("utf-8", "ignore"))
        return
    subprocess.run(["pdftotext", "-layout", "-l", "8", str(pdf), str(txt)], check=False, timeout=60)
    if not txt.exists():
        txt.write_text("")


def main():
    docs = json.loads((ROOT / "raw" / "fnet" / "docs.json").read_text())["documentos"]
    # todos os documentos de CRI: o código IF citado no texto é a melhor chave de cruzamento
    alvo = [d for d in docs if not (TXT / f"{d['id']}.txt").exists()]
    api = Fnet(pausa=0.2)

    def um(d):
        try:
            p = api.baixar(d["id"], PDF / f"{d['id']}.pdf")
            texto(p, TXT / f"{d['id']}.txt")
            p.unlink(missing_ok=True)  # guarda só o texto; os PDFs de assembleia são pesados
            return True
        except Exception as e:  # segue com os demais; o documento entra na próxima rodada
            print(f"falhou {d['id']}: {e}", file=sys.stderr)
            return False

    with ThreadPoolExecutor(max_workers=4) as ex:
        ok = sum(ex.map(um, alvo))
    print(f"{ok}/{len(alvo)} documentos com texto", file=sys.stderr)


if __name__ == "__main__":
    main()
