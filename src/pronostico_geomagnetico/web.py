"""API y página del pronóstico geomagnético."""

import hashlib
import io
import json
import os
import pickle
import warnings
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

import joblib
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.exceptions import InconsistentVersionWarning
from sklearn.utils.validation import check_is_fitted

from .ai_client import complete
from .exceptions import OmniLoadError, OmniValidationError
from .features import BLOQUE, ENTRADAS_MODELO, construir_dataset
from .fuentes import LOG, ahora_utc, descargar_json, observar_kp, revisar_viento
from .loader import load_omni
from .preprocessor import preprocess_omni
from .validator import validate_omni


def cargar_modelo(ruta: Path):
    contenido = ruta.read_bytes()
    with warnings.catch_warnings():
        warnings.simplefilter("error", InconsistentVersionWarning)
        modelo = joblib.load(io.BytesIO(contenido))
    if not isinstance(modelo, HistGradientBoostingRegressor):
        raise ValueError("Se esperaba el HistGradientBoostingRegressor del Proyecto II.")
    check_is_fitted(modelo)
    if list(getattr(modelo, "feature_names_in_", [])) != ENTRADAS_MODELO:
        raise ValueError("Las entradas del modelo no coinciden con el pipeline OMNI.")
    return modelo, hashlib.sha256(contenido).hexdigest()


def guardar_auditoria(carpeta: Path, resultado: dict) -> str:
    carpeta.mkdir(parents=True, exist_ok=True)
    identificador = uuid4().hex
    ruta = carpeta / f"{identificador}.json"
    with NamedTemporaryFile(dir=carpeta, delete=False, mode="w", encoding="utf-8") as archivo:
        temporal = Path(archivo.name)
        try:
            json.dump(resultado, archivo, ensure_ascii=False, indent=2, allow_nan=False)
        except BaseException:
            archivo.close()
            temporal.unlink(missing_ok=True)
            raise
    try:
        temporal.replace(ruta)
    finally:
        temporal.unlink(missing_ok=True)
    return identificador


def reproducir_dia(dia, carpeta, modelo, reloj):
    inicio = pd.Timestamp(dia, tz="UTC")
    dias_busqueda = [(inicio - BLOQUE).year, inicio.year]
    rutas = [carpeta / f"omni2_{anio}.dat" for anio in dict.fromkeys(dias_busqueda)]
    if not rutas[-1].is_file():
        return [], []
    rutas = [ruta for ruta in rutas if ruta.is_file()]
    datos = pd.concat([load_omni(ruta) for ruta in rutas], ignore_index=True)
    validate_omni(datos)
    dataset = construir_dataset(preprocess_omni(datos), exigir_objetivo=False)
    bloques = pd.date_range(inicio, periods=8, freq=BLOQUE)
    bloques_cerrados = bloques[bloques + BLOQUE <= reloj()]
    dataset = dataset.reindex(bloques_cerrados)
    entradas = dataset[ENTRADAS_MODELO].dropna()
    predicciones = dict(zip(entradas.index, modelo.predict(entradas))) if len(entradas) else {}

    serie = []
    for bloque, fila in dataset.iterrows():
        observacion = fila["kp_objetivo"]
        prediccion = predicciones.get(bloque)
        serie.append({
            "objetivo_inicio": bloque.isoformat(),
            "objetivo_fin": (bloque + BLOQUE).isoformat(),
            "ventana_inicio": (bloque - BLOQUE).isoformat(),
            "ventana_fin": bloque.isoformat(),
            "referencia_retrospectiva": bloque.isoformat(),
            "emision": None,
            "recepcion_original": None,
            "horas_validas": 3 if prediccion is not None else None,
            "entradas": entradas.loc[bloque].to_dict() if prediccion is not None else None,
            "kp_previsto": float(prediccion) if prediccion is not None else None,
            "kp_observado": float(observacion) if pd.notna(observacion) else None,
        })
    return serie, [ruta.name for ruta in rutas]


def crear_app(ruta_modelo=None, carpeta_omni=None, carpeta_auditoria=None,
              descargar=descargar_json, reloj=ahora_utc) -> FastAPI:
    load_dotenv()
    ruta_modelo = Path(ruta_modelo or os.getenv("KP_MODEL_PATH", "data/processed/modelo_kp.joblib"))
    carpeta_omni = Path(carpeta_omni or os.getenv("KP_OMNI_DIR", "data/raw"))
    carpeta_auditoria = Path(carpeta_auditoria or os.getenv("KP_AUDIT_DIR", "data/processed/predicciones"))

    @asynccontextmanager
    async def iniciar(app):
        app.state.modelo = None
        app.state.info = {"estado": "no_disponible", "version": None}
        try:
            app.state.modelo, version = cargar_modelo(ruta_modelo)
            app.state.info = {"estado": "cargado", "version": version, "tipo": "HistGradientBoostingRegressor"}
            LOG.info("Modelo Kp cargado: %s", version)
        except (OSError, ValueError, TypeError, ImportError, AttributeError, EOFError,
                pickle.UnpicklingError, InconsistentVersionWarning) as error:
            LOG.warning("Modelo Kp no disponible: %s", error)
        yield

    app = FastAPI(title="Pronóstico geomagnético", lifespan=iniciar)

    @app.get("/", include_in_schema=False)
    def pagina():
        return FileResponse(Path(__file__).with_name("web.html"), media_type="text/html")

    @app.get("/health")
    def health():
        return {"estado": "ok" if app.state.modelo is not None else "degradado", "modelo": app.state.info}

    @app.post("/api/pronostico")
    def pronostico():
        resultado = revisar_viento(descargar, reloj)
        LOG.info("Directo %s: %s (%s/180 min)", resultado["objetivo_inicio"],
                 resultado["motivo"], resultado["minutos_validos"])
        return resultado | {"modelo": app.state.info}

    @app.post("/api/historico")
    def historico(dia: date):
        resultado = {"modo": "historico", "fuente": "NASA OMNI2 horario",
                     "modelo": app.state.info, "dia": dia.isoformat(), "serie": []}
        if app.state.modelo is None:
            return resultado | {"estado": "sin_pronostico", "motivo": "modelo_no_disponible"}
        if not 1963 <= dia.year <= reloj().year or dia > reloj().date():
            raise HTTPException(422, "Elige un día histórico UTC válido.")
        try:
            serie, archivos = reproducir_dia(dia, carpeta_omni, app.state.modelo, reloj)
        except (OmniLoadError, OmniValidationError, pd.errors.ParserError, ValueError, OSError) as error:
            LOG.warning("Error al reproducir %s: %s", dia, error)
            return resultado | {"estado": "sin_pronostico", "motivo": "archivo_omni_invalido"}
        resultado |= {"serie": serie, "archivos": archivos, "consulta_archivo": reloj().isoformat()}
        predichos = [fila for fila in serie if fila["kp_previsto"] is not None]
        if not predichos:
            return resultado | {"estado": "sin_pronostico", "motivo": "ventanas_omni_incompletas"}

        resultado["estado"] = "reproducido"
        try:
            resultado["auditoria_id"] = guardar_auditoria(carpeta_auditoria, resultado)
        except OSError as error:
            LOG.error("No se pudo guardar la auditoría histórica: %s", error)
            raise HTTPException(503, "No se pudo guardar la auditoría de la predicción.") from error
        resumen = complete("mock", f"Resume la reproducción OMNI de {dia} con {len(predichos)} bloques calculados.")
        LOG.info("Histórico %s: %d bloques, auditoría %s", dia, len(predichos), resultado["auditoria_id"])
        return resultado | {"ia": {"proveedor": resumen.provider, "texto": resumen.text, "simulada": True}}

    @app.get("/api/observacion")
    def observacion(bloque: str | None = None):
        if bloque is None:
            inicio = reloj().floor("3h") - BLOQUE
        else:
            inicio = pd.to_datetime(bloque, utc=True, errors="coerce")
            if pd.isna(inicio) or inicio != inicio.floor("3h"):
                raise HTTPException(422, "Indica el inicio UTC de un bloque de tres horas.")
        return observar_kp(inicio, descargar, reloj)

    return app
