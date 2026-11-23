"""Pronóstico causal con Kp GFZ de bloques cerrados."""

import math

import pandas as pd

from .features import BLOQUE
from .fuentes import FUENTE_GFZ, LOG, leer_kp_gfz, url_gfz

RETARDOS = (2, 3, 4)
COLUMNAS_KP = [f"kp_hace_{pasos * 3}h" for pasos in RETARDOS]
PERSISTENCIA = COLUMNAS_KP[0]
METODO_KP = "GFZ-Kp-retardos-6-9-12h-v1"


def marcas_entrada(objetivo):
    return [objetivo - pasos * BLOQUE for pasos in RETARDOS]


def matriz_kp(kp: pd.Series, objetivos: pd.DatetimeIndex) -> pd.DataFrame:
    """Usa el mismo orden y los mismos instantes en lote y en directo."""
    return pd.DataFrame(
        {columna: kp.reindex(marcas).to_numpy()
         for columna, marcas in zip(COLUMNAS_KP, marcas_entrada(objetivos), strict=True)},
        index=objetivos,
    )


def proximo_bloque(ahora: pd.Timestamp) -> pd.Timestamp:
    return ahora.floor("3h") + BLOQUE


def _intervalos(objetivo):
    marcas = marcas_entrada(objetivo)
    return {
        "objetivo_inicio": objetivo.isoformat(),
        "objetivo_fin": (objetivo + BLOQUE).isoformat(),
        "ventana_inicio": marcas[-1].isoformat(),
        "ventana_fin": (marcas[0] + BLOQUE).isoformat(),
    }


def emitir_kp(modelo, descargar, reloj) -> dict:
    """Pronostica con mediciones GFZ que ya estaban cerradas al recibirlas."""
    objetivo = proximo_bloque(reloj())
    requeridas = marcas_entrada(objetivo)
    url = url_gfz(objetivo - 6 * BLOQUE, requeridas[0])
    base = {
        "modo": "directo", "fuente": FUENTE_GFZ, "url": url,
        "referencia": "Índice planetario de observatorios terrestres",
        "estado": "sin_pronostico", "kp_previsto": None, "emision": None,
        "bloques_validos": 0, "bloques_esperados": len(RETARDOS),
    } | _intervalos(objetivo)
    try:
        datos = descargar(url)
        recibida = reloj()
        registros = {fecha: registro for fecha, registro in leer_kp_gfz(datos).items()
                     if fecha <= requeridas[0] and fecha + BLOQUE <= recibida}
    except (OSError, ValueError, TypeError, KeyError) as error:
        LOG.warning("Kp operativo GFZ: %s", error)
        return base | {"motivo": "fuente_no_disponible", "decision": reloj().isoformat()}

    conjunto = pd.Series({fecha: registro[0] for fecha, registro in registros.items()}, dtype=float)
    X = matriz_kp(conjunto, pd.DatetimeIndex([objetivo]))
    validos = int(X.notna().sum(axis=1).iloc[0])
    ultimo = max(registros, default=None)

    def estado(ahora):
        edad = (ahora - (ultimo + BLOQUE)).total_seconds() if ultimo is not None else None
        return base | {
            "decision": ahora.isoformat(), "recepcion": recibida.isoformat(),
            "bloques_validos": validos, "antiguedad_segundos": edad,
            "ultimo_bloque_cierre": (ultimo + BLOQUE).isoformat() if ultimo is not None else None,
        }

    decision = reloj()
    diagnostico = estado(decision)
    if decision >= objetivo:
        return diagnostico | _intervalos(proximo_bloque(decision)) | {
            "motivo": "cambio_bloque", "bloques_validos": 0,
        }
    if diagnostico["antiguedad_segundos"] is not None and diagnostico["antiguedad_segundos"] > 10800:
        return diagnostico | {"motivo": "datos_caducados"}
    if validos < len(RETARDOS):
        return diagnostico | {"motivo": "datos_incompletos"}
    if modelo is None:
        return diagnostico | {"motivo": "modelo_no_disponible"}

    previsto = float(modelo.predict(X)[0])
    emision = reloj()
    if emision < recibida:
        return diagnostico | {"motivo": "reloj_inconsistente"}
    if not math.isfinite(previsto) or not 0 <= previsto <= 9:
        return estado(emision) | {"motivo": "inferencia_invalida"}
    if emision >= objetivo:
        return estado(emision) | _intervalos(proximo_bloque(emision)) | {
            "motivo": "cambio_bloque", "bloques_validos": 0,
        }
    return estado(emision) | {
        "estado": "emitido", "emision": emision.isoformat(), "kp_previsto": previsto,
        "anticipacion_segundos": (objetivo - emision).total_seconds(),
        "entradas": X.iloc[0].to_dict(),
        "mediciones": [
            {"inicio": fecha.isoformat(), "fin": (fecha + BLOQUE).isoformat(),
             "kp": registros[fecha][0], "calidad": registros[fecha][1]}
            for fecha in requeridas
        ],
        "kp_persistencia": registros[requeridas[0]][0],
    }
