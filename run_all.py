"""
Ejecuta todos los generadores de dashboards en orden.
Correr desde la raíz del proyecto: python run_all.py
"""

import subprocess
import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent

SCRIPTS = [
    ("acciones",              "generate_dashboard.py",    "Acciones ARG"),
    ("dashboard-internacional","generate_dashboard.py",   "S&P 500"),
    ("bcra",                  "generate_dashboard_v2.py", "BCRA Macroeconomía"),
    ("noticias",              "generate_dashboard.py",    "Noticias Financieras"),
]

def run(folder, script, label):
    cwd = ROOT / folder
    print(f"\n{'='*50}")
    print(f"  {label}")
    print(f"{'='*50}")
    result = subprocess.run(
        [sys.executable, script],
        cwd=cwd,
    )
    if result.returncode != 0:
        print(f"  [ERROR] {label} (codigo {result.returncode})")
    else:
        print(f"  [OK] {label} generado")
    return result.returncode == 0

if __name__ == "__main__":
    ok = all(run(f, s, l) for f, s, l in SCRIPTS)
    print(f"\n{'='*50}")
    print("  Todos los dashboards actualizados OK." if ok else "  Algunos dashboards fallaron.")
    print(f"{'='*50}\n")
