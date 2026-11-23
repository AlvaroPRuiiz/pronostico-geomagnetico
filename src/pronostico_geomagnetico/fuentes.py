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
FUENTE_GFZ = "GFZ Potsdam · CC BY 4.0"
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

    consulta = reloj()
    fin = consulta.floor("min")
    inicio = fin - BLOQUE
    pares = mediciones.get("mag", set()) & mediciones.get("plasma", set())
    ventana = {(fecha, satelite) for fecha, satelite in pares if inicio <= fecha < fin}
    ultimo = max((fecha for fecha, _ in pares), default=None)
    edad = (consulta - ultimo).total_seconds() if ultimo is not None else None
    if len(mediciones) != 2:
        motivo = "fuente_no_disponible"
    elif edad is not None and edad > 10 * 60:
        motivo = "datos_caducados"
    elif len(ventana) < 180:
        motivo = "datos_incompletos"
    else:
        motivo = None

    return resultado | {
        "modo": "diagnostico_l1",
        "estado": "datos_validos" if motivo is None else "datos_no_validos",
        "motivo": motivo,
        "consulta": consulta.isoformat(),
        "ventana_l1_inicio": inicio.isoformat(),
        "ventana_l1_fin": fin.isoformat(),
        "minutos_validos": len(ventana),
        "minutos_esperados": 180,
        "ultimo_dato": ultimo.isoformat() if ultimo is not None else None,
        "antiguedad_segundos": edad,
        "satelites": sorted({satelite for _, satelite in ventana}),
    }


def url_gfz(inicio: pd.Timestamp, fin: pd.Timestamp) -> str:
    formato = "%Y-%m-%dT%H:%M:%SZ"
    return GFZ + "?" + urlencode(
        {"start": inicio.strftime(formato), "end": fin.strftime(formato), "index": "Kp"}
    )


def leer_kp_gfz(datos: dict) -> dict:
    """Valida la escala, calidad y unicidad de cada bloque devuelto por GFZ."""
    campos = [datos[clave] for clave in ("datetime", "Kp", "status")]
    if not all(isinstance(campo, list) for campo in campos):
        raise ValueError("Esquema Kp de GFZ desconocido.")
    registros, vistos = {}, set()
    for marca, kp, calidad in zip(*campos, strict=True):
        if not isinstance(marca, str):
            continue
        fecha = pd.to_datetime(marca, utc=True, errors="coerce")
        if pd.isna(fecha) or fecha != fecha.floor("3h"):
            continue
        if fecha in vistos:
            registros.pop(fecha, None)
            continue
        vistos.add(fecha)
        if calidad in ("pre", "def") and _numero(kp) and 0 <= kp <= 9:
            # GFZ redondea su JSON a tres cifras decimales; WDC codifica tercios.
            registros[fecha] = (float(kp), calidad)
    return registros


def observar_kp(inicio: pd.Timestamp, descargar=descargar_json, reloj=ahora_utc) -> dict:
    """Consulta únicamente el Kp GFZ del bloque UTC cerrado indicado."""
    base = {"fuente": FUENTE_GFZ, "objetivo_inicio": inicio.isoformat()}
    fin = inicio + BLOQUE
    if reloj() < fin:
        return base | {"estado": "bloque_abierto"}

    url = url_gfz(inicio, inicio)
    try:
        datos = descargar(url)
        recibida = reloj()
        coincidencia = leer_kp_gfz(datos).get(inicio)
        if coincidencia is not None:
            kp, estado = coincidencia
            return base | {
                "estado": "disponible", "kp_observado": kp, "calidad": estado,
                "recepcion": recibida.isoformat(), "url": url,
            }
        return base | {"estado": "observacion_pendiente", "url": url}
    except (OSError, ValueError, TypeError, KeyError) as error:
        LOG.warning("Fallo en GFZ: %s", error)
        return base | {"estado": "fuente_no_disponible", "url": url}
