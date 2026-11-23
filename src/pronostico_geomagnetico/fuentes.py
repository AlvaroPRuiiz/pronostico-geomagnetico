"""Clientes y controles de los productos públicos NOAA SWPC y GFZ."""

import json
import logging
import math
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from .features import BLOQUE

RTSW = "https://services.swpc.noaa.gov/json/rtsw"
MAG = f"{RTSW}/rtsw_mag_1m.json"
VIENTO = f"{RTSW}/rtsw_wind_1m.json"
GFZ = "https://kp.gfz.de/app/json/"
LOG = logging.getLogger("uvicorn.error")


def ahora_utc() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def descargar_json(url: str):
    with urlopen(url, timeout=8) as respuesta:
        return json.load(respuesta)


def _numero(valor) -> bool:
    return type(valor) in (int, float) and math.isfinite(valor)


def _minutos(filas, recibida, campos, muestras):
    """Un índice por minuto UTC y satélite; descarta minutos ambiguos."""
    if not isinstance(filas, list):
        raise ValueError("Se esperaba una lista de mediciones NOAA.")

    minutos = {}
    activos = {}
    conflictos = set()
    for fila in filas:
        if not isinstance(fila, dict) or not {"time_tag", "source", "active", *campos} <= fila.keys():
            raise ValueError("Esquema NOAA desconocido.")
        if fila["active"] is not True:
            continue
        marca = fila["time_tag"]
        if not isinstance(marca, str):
            continue
        fecha = pd.to_datetime(marca, utc=True, errors="coerce")
        fuente = fila["source"]
        if pd.isna(fecha) or fecha >= recibida.floor("min") or not isinstance(fuente, str) or not fuente:
            continue
        minuto = fecha.floor("min")
        activos.setdefault(minuto, set()).add(fuente)
        valores = tuple(fila[campo] for campo in campos)
        calidad = tuple(fila.get(campo) for campo in sorted(fila) if campo.endswith("_flag"))
        registro = (valores, fila.get("overall_quality"), fila.get(muestras), calidad)
        clave = (minuto, fuente)
        if clave in minutos and minutos[clave] != registro:
            conflictos.add(clave)
        minutos[clave] = registro

    validos = set()
    for clave, (valores, calidad, cantidad, flags) in minutos.items():
        minuto, _ = clave
        if clave in conflictos or len(activos[minuto]) != 1:
            continue
        if type(calidad) is not int or calidad != 0 or any(flag not in (0, None) for flag in flags):
            continue
        if not _numero(cantidad) or cantidad <= 0 or not all(map(_numero, valores)):
            continue
        if len(valores) == 2 and (valores[0] <= 0 or valores[1] <= 0):
            continue
        validos.add(clave)
    return validos


def revisar_viento(descargar=descargar_json, reloj=ahora_utc) -> dict:
    """Mide latencia y cobertura de L1 sin convertir minutos en entradas OMNI."""
    resultado = {"fuente": "NOAA SWPC RTSW · L1", "urls": [MAG, VIENTO]}
    mediciones = {}
    for nombre, url, campos, muestras in (
        ("mag", MAG, ("bz_gsm",), "sample_size"),
        ("plasma", VIENTO, ("proton_density", "proton_speed"), "proton_sample_size"),
    ):
        try:
            filas = descargar(url)
            recibida = reloj()
            resultado[f"recepcion_{nombre}"] = recibida.isoformat()
            mediciones[nombre] = _minutos(filas, recibida, campos, muestras)
        except (OSError, ValueError) as error:
            LOG.warning("Fallo en NOAA %s: %s", nombre, error)

    decision = reloj()
    fin = decision.floor("min")
    inicio = fin - BLOQUE
    objetivo = decision.floor("3h") + BLOQUE
    pares = mediciones.get("mag", set()) & mediciones.get("plasma", set())
    ventana = {(fecha, satelite) for fecha, satelite in pares if inicio <= fecha < fin}
    ultimo = max((fecha for fecha, _ in pares), default=None)
    edad = (decision - ultimo).total_seconds() if ultimo is not None else None
    if len(mediciones) != 2:
        motivo = "fuente_no_disponible"
    elif edad is not None and edad > 10 * 60:
        motivo = "datos_caducados"
    elif len(ventana) < 180:
        motivo = "datos_incompletos"
    else:
        motivo = "fuente_incompatible"

    return resultado | {
        "modo": "directo",
        "estado": "sin_pronostico",
        "motivo": motivo,
        "compatibilidad": "RTSW en L1 no reproduce OMNI propagado a la Tierra.",
        "ventana_modelo_cerrada": False,
        "decision": decision.isoformat(),
        "emision": None,
        "kp_previsto": None,
        "objetivo_inicio": objetivo.isoformat(),
        "objetivo_fin": (objetivo + BLOQUE).isoformat(),
        "ventana_modelo_inicio": (objetivo - BLOQUE).isoformat(),
        "ventana_modelo_fin": objetivo.isoformat(),
        "ventana_l1_inicio": inicio.isoformat(),
        "ventana_l1_fin": fin.isoformat(),
        "minutos_validos": len(ventana),
        "minutos_esperados": 180,
        "ultimo_dato": ultimo.isoformat() if ultimo is not None else None,
        "antiguedad_segundos": edad,
        "satelites": sorted({satelite for _, satelite in ventana}),
    }


def observar_kp(inicio: pd.Timestamp, descargar=descargar_json, reloj=ahora_utc) -> dict:
    """Consulta únicamente el Kp GFZ del bloque UTC cerrado indicado."""
    base = {"fuente": "GFZ Potsdam · CC BY 4.0", "objetivo_inicio": inicio.isoformat()}
    fin = inicio + BLOQUE
    if reloj() < fin:
        return base | {"estado": "bloque_abierto"}

    fecha = inicio.strftime("%Y-%m-%dT%H:%M:%SZ")
    url = GFZ + "?" + urlencode({"start": fecha, "end": fecha, "index": "Kp"})
    try:
        datos = descargar(url)
        recibida = reloj()
        filas = list(zip(datos["datetime"], datos["Kp"], datos["status"], strict=True))
        coincidencias = [(kp, estado) for fecha, kp, estado in filas
                         if pd.to_datetime(fecha, utc=True, errors="coerce") == inicio]
        if len(coincidencias) == 1:
            kp, estado = coincidencias[0]
            if estado in ("pre", "def") and _numero(kp) and 0 <= kp <= 9:
                return base | {
                    "estado": "disponible", "kp_observado": kp, "calidad": estado,
                    "recepcion": recibida.isoformat(), "url": url,
                }
        return base | {"estado": "observacion_pendiente", "url": url}
    except (OSError, ValueError, TypeError, KeyError) as error:
        LOG.warning("Fallo en GFZ: %s", error)
        return base | {"estado": "fuente_no_disponible", "url": url}
