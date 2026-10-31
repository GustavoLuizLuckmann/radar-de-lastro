"""Roda o pipeline completo: carteira (CVM) -> documentos (Fundos.Net) -> texto -> classificação -> site/data.json."""
import subprocess
import time
import sys
from datetime import date
from pathlib import Path

AQUI = Path(__file__).resolve().parent


LIMITE = {"holdings.py": 15, "collect.py": 15, "fetch_docs.py": 25, "build.py": 15}  # minutos


def etapa(*args):
    inicio = time.time()
    print("→", " ".join(args), flush=True)
    subprocess.run([sys.executable, *args], cwd=AQUI, check=True, timeout=LIMITE.get(args[0], 15) * 60)
    print(f"  ok em {time.time() - inicio:.0f}s", flush=True)


if __name__ == "__main__":
    dias = sys.argv[1] if len(sys.argv) > 1 else "7"
    carteira = AQUI.parent / "data" / "holdings.json"
    desatualizada = not carteira.exists() or time.time() - carteira.stat().st_mtime > 20 * 3600
    if not desatualizada and '"fundos"' not in carteira.read_text()[-2_000_000:]:
        desatualizada = True  # formato antigo, sem o cadastro de todos os FIIs
    if desatualizada:
        etapa("holdings.py", str(date.today().year))  # informes da CVM mudam pouco: uma vez por dia basta
    else:
        print("→ carteira da CVM atualizada há menos de 20 horas; mantida", flush=True)
    etapa("collect.py", dias)
    etapa("fetch_docs.py")
    etapa("build.py")
