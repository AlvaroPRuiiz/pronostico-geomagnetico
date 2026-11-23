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
from uuid import UUID

import joblib
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.exceptions import InconsistentVersionWarning
from sklearn.utils.validation import check_is_fitted

from .ai_client import complete
from .exceptions import OmniLoadError, OmniValidationError
from .features import BLOQUE, ENTRADAS_MODELO, construir_dataset
from .fuentes import LOG, ahora_utc, descargar_json, observar_kp, revisar_viento
from .loader import load_omni
from .operativo import COLUMNAS_KP, METODO_KP, emitir_kp
from .preprocessor import preprocess_omni
from .registros import (carpeta_bloque, con_observacion, guardar_auditoria, leer_auditoria,
                       mejor_observacion, seguimiento)
from .validator import validate_omni


def cargar_modelo(ruta: Path, columnas=ENTRADAS_MODELO):
    contenido = ruta.read_bytes()
    with warnings.catch_warnings():
        warnings.simplefilter("error", InconsistentVersionWarning)
        modelo = joblib.load(io.BytesIO(contenido))
    if not isinstance(modelo, HistGradientBoostingRegressor):
        raise ValueError("Se esperaba HistGradientBoostingRegressor.")
    check_is_fitted(modelo)
    if list(getattr(modelo, "feature_names_in_", [])) != columnas:
        raise ValueError("Las entradas del modelo no coinciden con su contrato.")
    return modelo, hashlib.sha256(contenido).hexdigest()


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
              descargar=descargar_json, reloj=ahora_utc, *, ruta_operativo=None,
              carpeta_evaluacion=None) -> FastAPI:
    load_dotenv()
    ruta_modelo = Path(ruta_modelo or os.getenv("KP_MODEL_PATH", "data/processed/modelo_kp.joblib"))
    carpeta_omni = Path(carpeta_omni or os.getenv("KP_OMNI_DIR", "data/raw"))
    carpeta_auditoria = Path(carpeta_auditoria or os.getenv("KP_AUDIT_DIR", "data/processed/predicciones"))
    carpeta_evaluacion = Path(carpeta_evaluacion or os.getenv("KP_EVAL_DIR", "data/processed"))
    ruta_operativo = Path(ruta_operativo or os.getenv(
        "KP_OPERATIVE_MODEL_PATH", str(carpeta_evaluacion / "modelo_operativo.joblib")
    ))

    def cargar(ruta, columnas, metodo):
        info = {"estado": "no_disponible", "version": None, "metodo": metodo}
        try:
            modelo, version = cargar_modelo(ruta, columnas)
            LOG.info("Modelo %s cargado: %s", metodo, version)
            return modelo, info | {
                "estado": "cargado", "version": version, "tipo": "HistGradientBoostingRegressor",
            }
        except (OSError, ValueError, TypeError, ImportError, AttributeError, EOFError,
                pickle.UnpicklingError, InconsistentVersionWarning) as error:
            LOG.warning("Modelo %s no disponible: %s", metodo, error)
            return None, info

    @asynccontextmanager
    async def iniciar(app):
        app.state.modelo, app.state.info = cargar(ruta_modelo, ENTRADAS_MODELO, "OMNI2 histórico")
        app.state.operativo, app.state.info_operativo = cargar(ruta_operativo, COLUMNAS_KP, METODO_KP)
        yield

    app = FastAPI(title="Pronóstico geomagnético", lifespan=iniciar)
    app.mount("/assets", StaticFiles(directory=Path(__file__).with_name("web_assets")), name="assets")

    @app.get("/", include_in_schema=False)
    def pagina():
        return FileResponse(Path(__file__).with_name("web.html"), media_type="text/html")

    @app.get("/health")
    def health():
        disponible = app.state.operativo is not None or app.state.modelo is not None
        return {"estado": "ok" if disponible else "degradado", "modelo": app.state.info,
                "modelo_operativo": app.state.info_operativo}

    @app.post("/api/pronostico")
    def pronostico():
        resultado = emitir_kp(app.state.operativo, descargar, reloj) | {"modelo": app.state.info_operativo}
        if resultado["estado"] == "emitido":
            try:
                resultado["auditoria_id"] = guardar_auditoria(carpeta_auditoria / "directo", resultado)
            except OSError as error:
                LOG.error("No se pudo guardar la emisión: %s", error)
                raise HTTPException(503, "No se pudo registrar el pronóstico.") from error
        LOG.info("Directo %s: %s", resultado["objetivo_inicio"],
                 resultado.get("motivo", resultado["estado"]))
        return resultado

    @app.get("/api/viento")
    def viento():
        return revisar_viento(descargar, reloj)

    @app.get("/api/seguimiento")
    def emisiones(dias: int = Query(7, ge=1, le=90)):
        ahora = reloj()
        return seguimiento(carpeta_auditoria, app.state.info_operativo["version"],
                           ahora - pd.Timedelta(days=dias), ahora)

    @app.post("/api/pronosticos/{identificador}/observacion")
    def actualizar_observacion(identificador: UUID):
        ruta = carpeta_auditoria / "directo" / f"{identificador.hex}.json"
        if not ruta.is_file():
            raise HTTPException(404, "No existe ese pronóstico.")
        pronostico = leer_auditoria(ruta)
        bloque = pd.Timestamp(pronostico["objetivo_inicio"])
        anterior = mejor_observacion(carpeta_auditoria, bloque)
        if anterior and anterior["calidad"] == "def":
            return con_observacion(pronostico, anterior)

        nueva = observar_kp(bloque, descargar, reloj)
        if nueva["estado"] == "disponible":
            try:
                guardar_auditoria(carpeta_bloque(carpeta_auditoria, bloque), nueva)
            except OSError as error:
                raise HTTPException(503, "No se pudo conservar la observación.") from error
            mejor = mejor_observacion(carpeta_auditoria, bloque)
            return con_observacion(pronostico, mejor)
        if anterior is not None:
            return con_observacion(pronostico, anterior) | {"actualizacion": nueva["estado"]}
        return nueva

    @app.get("/api/evaluacion")
    def evaluacion():
        ruta = carpeta_evaluacion / "evaluacion.json"
        if not ruta.is_file():
            return {"estado": "informe_no_disponible", "periodos": {}}
        informe = leer_auditoria(ruta)
        return informe | {
            "estado": "disponible",
            "corresponde_modelo_cargado": (
                informe.get("modelo_sha256") is not None
                and informe["modelo_sha256"] == app.state.info_operativo["version"]
            ),
        }

    @app.get("/api/evaluacion/{periodo}")
    def serie_evaluacion(periodo: str, inicio: date, dias: int = Query(7, ge=1, le=31)):
        if periodo not in {"validacion", "gfz2026", "omni"}:
            raise HTTPException(404, "Periodo de evaluación desconocido.")
        ruta = carpeta_evaluacion / f"evaluacion_{periodo}.csv"
        if not ruta.is_file():
            raise HTTPException(404, "Ese informe aún no está disponible.")
        datos = pd.read_csv(ruta)
        desde = pd.Timestamp(inicio, tz="UTC")
        marcas = pd.to_datetime(datos["bloque"], utc=True)
        seleccion = marcas.between(desde, desde + pd.Timedelta(days=dias), inclusive="left")
        serie = datos.loc[seleccion].rename(columns={"bloque": "objetivo_inicio"})
        return {"serie": json.loads(serie.to_json(orient="records"))}

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
