"""Registra el kernel local de la asignatura DSIA."""
import json
from pathlib import Path
import sys
from ipykernel.kernelspec import install

root = Path(__file__).resolve().parents[1]
name = "desarrollo_de_soluciones_de_ia"
display_name = "Python (Desarrollo de Soluciones de IA)"
# Una copia dentro del entorno y otra para que lo descubran los editores.
for options in ({"prefix": sys.prefix}, {"user": True}):
    destination = Path(install(kernel_name=name, display_name=display_name, **options))
    path = destination / "kernel.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    spec["argv"].append("--IPKernelApp.exec_lines=" + repr(["import os; os.chdir(" + repr(str(root)) + ")"]))
    path.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    print(destination)
