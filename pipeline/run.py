"""Roda o pipeline completo: carteira (CVM) -> documentos (Fundos.Net) -> texto -> classificação -> site/data.json."""
import subprocess
import sys
from datetime import date
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def etapa(*args):
    print("→", " ".join(args), flush=True)
    subprocess.run([sys.executable, *args], cwd=AQUI, check=True)


if __name__ == "__main__":
    dias = sys.argv[1] if len(sys.argv) > 1 else "30"
    etapa("holdings.py", str(date.today().year))
    etapa("collect.py", dias)
    etapa("fetch_docs.py")
    etapa("build.py")
