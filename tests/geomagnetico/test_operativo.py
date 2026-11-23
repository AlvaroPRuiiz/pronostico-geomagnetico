import json
from urllib.parse import parse_qs, urlparse

import joblib
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sklearn.ensemble import HistGradientBoostingRegressor

from src.pronostico_geomagnetico.features import BLOQUE
from src.pronostico_geomagnetico.operativo import COLUMNAS_KP, emitir_kp, marcas_entrada, matriz_kp
from src.pronostico_geomagnetico.web import crear_app


B = pd.Timestamp("2026-11-23T21:00:00Z")
D = pd.Timestamp("2026-11-23T19:10:00Z")


def respuesta(fechas, kp, calidad="pre"):
    return {"datetime": [fecha.isoformat() for fecha in fechas], "Kp": list(kp),
            "status": [calidad] * len(fechas)}


def test_emision_usa_formato_de_entrenamiento_y_excluye_datos_futuros():
    requeridas = marcas_entrada(B)
    valores = [3.333, 2.667, 1.333]
    datos = respuesta(requeridas + [B - BLOQUE, B], valores + [9, 9])
    tiempos = iter([D, D + pd.Timedelta(seconds=2), D + pd.Timedelta(seconds=3),
                    D + pd.Timedelta(seconds=4)])

    class Modelo:
        def predict(self, X):
            esperado = matriz_kp(pd.Series(valores, index=requeridas), pd.DatetimeIndex([B]))
            pd.testing.assert_frame_equal(X, esperado)
            return [2.5]

    r = emitir_kp(Modelo(), lambda url: datos, lambda: next(tiempos))
    assert r["estado"] == "emitido"
    assert r["kp_previsto"] == 2.5
    assert r["kp_persistencia"] == valores[0]
    assert pd.Timestamp(r["recepcion"]) < pd.Timestamp(r["emision"]) < B
    assert all(pd.Timestamp(m["fin"]) <= pd.Timestamp(r["recepcion"]) for m in r["mediciones"])
    assert r["anticipacion_segundos"] == (B - D).total_seconds() - 4
    assert pd.Timestamp(r["objetivo_fin"]) == B + BLOQUE


@pytest.mark.parametrize("caso, motivo", [
    ("sin_ultimo", "datos_caducados"), ("hueco", "datos_incompletos"),
    ("duplicado", "datos_incompletos"), ("calidad", "datos_incompletos"),
    ("esquema", "fuente_no_disponible"),
])
def test_abstiene_sin_ventana_compatible(caso, motivo):
    marcas = marcas_entrada(B)
    datos = respuesta(marcas, [1., 2., 3.])
    if caso == "sin_ultimo":
        datos = respuesta(marcas[1:], [2., 3.])
    elif caso == "hueco":
        datos["Kp"][1] = None
    elif caso == "duplicado":
        datos = respuesta(marcas + [marcas[1]], [1., 2., 3., 4.])
    elif caso == "calidad":
        datos["status"][1] = "forecast"
    else:
        datos["status"] = True
    r = emitir_kp(object(), lambda url: datos, lambda: D)
    assert r["motivo"] == motivo
    assert r["emision"] is None and r["kp_previsto"] is None


def test_cambio_de_bloque_durante_inferencia_descarta_resultado():
    class Modelo:
        def predict(self, X):
            return [2]
    tiempos = iter([D, D, D, B])
    r = emitir_kp(Modelo(), lambda url: respuesta(marcas_entrada(B), [1., 2., 3.]), lambda: next(tiempos))
    assert r["motivo"] == "cambio_bloque"
    assert r["objetivo_inicio"] == (B + BLOQUE).isoformat()
    assert r["kp_previsto"] is None


def test_reloj_inconsistente_impide_emitir():
    class Modelo:
        def predict(self, X):
            return [2]
    tiempos = iter([D, D, D, D - pd.Timedelta(seconds=1)])
    r = emitir_kp(Modelo(), lambda url: respuesta(marcas_entrada(B), [1., 2., 3.]), lambda: next(tiempos))
    assert r["motivo"] == "reloj_inconsistente" and r["emision"] is None


def test_operativo_api_auditoria_revision_y_persistencia_real(tmp_path):
    ruta = tmp_path / "gfz.joblib"
    X = pd.DataFrame([[1., 2., 3.], [3., 4., 5.], [5., 6., 7.]], columns=COLUMNAS_KP)
    modelo = HistGradientBoostingRegressor(min_samples_leaf=1, random_state=42).fit(X, [2., 3., 6.])
    joblib.dump(modelo, ruta)
    tiempo = D
    calidad = "pre"
    llamadas = []

    def descargar(url):
        args = parse_qs(urlparse(url).query)
        llamadas.append(args)
        if args["start"] != args["end"]:
            return respuesta(marcas_entrada(B), [3., 4., 5.])
        return respuesta([B], [5.0 if calidad == "pre" else 4.667], calidad)

    auditoria = tmp_path / "auditoria"
    app = crear_app(ruta_modelo=tmp_path / "omni-no", carpeta_omni=tmp_path,
                    carpeta_auditoria=auditoria, ruta_operativo=ruta, carpeta_evaluacion=tmp_path,
                    descargar=descargar, reloj=lambda: tiempo)
    with TestClient(app) as cliente:
        assert cliente.get("/health").json()["modelo_operativo"]["estado"] == "cargado"
        r = cliente.post("/api/pronostico").json()
        tiempo = D + pd.Timedelta(seconds=1)
        segunda = cliente.post("/api/pronostico").json()
        assert r["auditoria_id"] != segunda["auditoria_id"]
        assert r["kp_previsto"] == pytest.approx(modelo.predict(X.iloc[[1]])[0])
        assert r["entradas"] == dict(zip(COLUMNAS_KP, [3., 4., 5.]))
        evidencia = auditoria / "directo" / (r["auditoria_id"] + ".json")
        registro = json.loads(evidencia.read_text(encoding="utf-8"))
        assert registro["kp_persistencia"] == 3.0 and registro["modelo"]["version"]
        serie_vigente = cliente.get("/api/seguimiento").json()
        assert serie_vigente["vigente"]["auditoria_id"] == segunda["auditoria_id"]
        assert serie_vigente["serie"][0]["auditoria_id"] == r["auditoria_id"]
        ruta_obs = "/api/pronosticos/" + r["auditoria_id"] + "/observacion"
        assert cliente.post(ruta_obs).json()["estado"] == "bloque_abierto"
        assert len(llamadas) == 2
        tiempo = B + BLOQUE + pd.Timedelta(minutes=10)
        obs = cliente.post(ruta_obs).json()
        assert obs["calidad"] == "pre"
        assert obs["error_absoluto"] == pytest.approx(abs(r["kp_previsto"] - 5))
        assert obs["error_persistencia"] == 2
        calidad = "def"
        assert cliente.post(ruta_obs).json()["calidad"] == "def"
        assert cliente.post(ruta_obs).json()["kp_observado"] == 4.667
        assert len(llamadas) == 4
        resumen = cliente.get("/api/seguimiento").json()
        assert resumen["emisiones"] == 2
        assert resumen["comparacion"]["bloques"] == 1
        assert resumen["comparacion"]["persistencia"]["mae"] == pytest.approx(1.667)
        assert resumen["definitivos"] == 1
        assert resumen["estado"] == "evaluacion_pendiente"
        assert cliente.get("/api/evaluacion").json()["estado"] == "informe_no_disponible"


def test_modelo_omni_no_compatible_con_gfz(tmp_path):
    ruta = tmp_path / "modelo.joblib"
    X = pd.DataFrame({"otra_variable": [1, 2, 3]})
    joblib.dump(HistGradientBoostingRegressor().fit(X, [2., 3., 4.]), ruta)
    app = crear_app(ruta_modelo=tmp_path / "omni-no", ruta_operativo=ruta,
                    descargar=lambda _: respuesta(marcas_entrada(B), [2., 3., 4.]), reloj=lambda: D)
    with TestClient(app) as cliente:
        assert cliente.get("/health").json()["modelo_operativo"]["estado"] == "no_disponible"
        assert cliente.post("/api/pronostico").json()["motivo"] == "modelo_no_disponible"
