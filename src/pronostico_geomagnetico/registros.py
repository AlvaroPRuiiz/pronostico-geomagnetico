"""Auditoría local append-only de las emisiones y sus observaciones GFZ."""

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

import pandas as pd

from .evaluacion import resumen_comparacion


def guardar_auditoria(carpeta: Path, resultado: dict) -> str:
    carpeta.mkdir(parents=True, exist_ok=True)
    identificador = uuid4().hex
    ruta = carpeta / f"{identificador}.json"
    temporal = None
    try:
        with NamedTemporaryFile(dir=carpeta, delete=False, mode="w", encoding="utf-8") as archivo:
            temporal = Path(archivo.name)
            json.dump(resultado, archivo, ensure_ascii=False, indent=2, allow_nan=False)
        temporal.replace(ruta)
    finally:
        if temporal is not None:
            temporal.unlink(missing_ok=True)
    return identificador


def leer_auditoria(ruta: Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def carpeta_bloque(carpeta: Path, bloque: pd.Timestamp) -> Path:
    return carpeta / "observaciones" / bloque.strftime("%Y%m%d%H")


def mejor_observacion(carpeta: Path, bloque: pd.Timestamp) -> dict | None:
    registros = (leer_auditoria(ruta) for ruta in carpeta_bloque(carpeta, bloque).glob("*.json"))
    return max(registros, key=lambda r: (r["calidad"] == "def", r["recepcion"]), default=None)


def con_observacion(pronostico: dict, observacion: dict) -> dict:
    return observacion | {
        "error_absoluto": abs(pronostico["kp_previsto"] - observacion["kp_observado"]),
        "error_persistencia": abs(pronostico["kp_persistencia"] - observacion["kp_observado"]),
    }


def seguimiento(carpeta: Path, version: str | None, desde: pd.Timestamp, ahora: pd.Timestamp) -> dict:
    primeras = {}
    emisiones = 0
    vigente = None
    for ruta in (carpeta / "directo").glob("*.json"):
        r = leer_auditoria(ruta)
        if r["modelo"]["version"] != version or pd.Timestamp(r["objetivo_inicio"]) < desde:
            continue
        emisiones += 1
        bloque = r["objetivo_inicio"]
        r |= {"auditoria_id": ruta.stem}
        if bloque not in primeras or r["emision"] < primeras[bloque]["emision"]:
            primeras[bloque] = r
        if pd.Timestamp(bloque) > ahora and (vigente is None or r["emision"] > vigente["emision"]):
            vigente = r

    serie = []
    for bloque, pronostico in sorted(primeras.items()):
        observacion = mejor_observacion(carpeta, pd.Timestamp(bloque))
        serie.append(pronostico | {
            "kp_observado": observacion["kp_observado"] if observacion else None,
            "observacion": con_observacion(pronostico, observacion) if observacion else None,
            "cerrado": pd.Timestamp(pronostico["objetivo_fin"]) <= ahora,
        })

    comparacion = (resumen_comparacion(pd.DataFrame(serie), len(serie))
                   if serie else {"bloques": 0, "esperados": 0, "cobertura": None})
    cerrados = sum(fila["cerrado"] for fila in serie)
    definitivos = sum((fila["observacion"] or {}).get("calidad") == "def" for fila in serie)
    return {
        "serie": serie, "emisiones": emisiones, "cerrados": cerrados, "definitivos": definitivos,
        "vigente": vigente,
        "desde": desde.isoformat(), "comparacion": comparacion,
        "estado": "evaluacion_pendiente" if comparacion["bloques"] < 30 else "muestra_operativa",
    }
