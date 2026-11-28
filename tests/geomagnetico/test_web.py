import json
from hashlib import sha256

import joblib
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sklearn.ensemble import HistGradientBoostingRegressor

from src.pronostico_geomagnetico.features import COLUMNAS_VIENTO, ENTRADAS_MODELO, construir_dataset
from src.pronostico_geomagnetico.loader import COLUMN_NAMES
from src.pronostico_geomagnetico.web import crear_app


DIA = "2025-01-02"
INICIO = pd.Timestamp(DIA, tz="UTC")
AHORA = INICIO + pd.Timedelta(days=1)


def datos_omni():
    return pd.DataFrame({
        "year": [2025] * 9,
        "day_of_year": [2] * 9,
        "hour": range(9),
        "bz_gsm_nt": [-1., -2., -3., -12., -12., -12., 0., 0., 0.],
        "proton_density_cm3": [4.] * 9,
        "solar_wind_speed_kms": [400.] * 9,
        "kp_x10": [10] * 3 + [43] * 3 + [99] * 3,
    })


def test_ventana_omni_no_usa_viento_del_bloque_objetivo():
    datos = datos_omni()
    objetivo = INICIO + pd.Timedelta(hours=3)
    original = construir_dataset(datos).loc[objetivo]
    datos.loc[datos.hour >= 3, COLUMNAS_VIENTO] = 9000.0
    resultado = construir_dataset(datos).loc[objetivo]

    assert resultado.equals(original)
    assert resultado["kp_objetivo"] == 4.3
    assert resultado[ENTRADAS_MODELO].tolist() == [-2, 4, 400]


def test_hora_duplicada_no_sustituye_hora_ausente():
    datos = datos_omni()
    datos.loc[2, "hour"] = 1
    entradas = construir_dataset(datos, incluir_objetivo=False)
    assert INICIO + pd.Timedelta(hours=3) not in entradas.index


@pytest.fixture
def historico(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    datos = datos_omni().reindex(columns=COLUMN_NAMES, fill_value=0)
    datos.to_csv(raw / "omni2_2025.dat", index=False, header=False, sep=" ")
    modelo = HistGradientBoostingRegressor(
        early_stopping=False, min_samples_leaf=1, random_state=42
    )
    X = pd.DataFrame([[-12., 4., 400.], [-2., 4., 400.], [2., 4., 400.]], columns=ENTRADAS_MODELO)
    modelo.fit(X, [6., 3., 1.])
    ruta = tmp_path / "modelo.joblib"
    joblib.dump(modelo, ruta)
    auditoria = tmp_path / "predicciones"
    return ruta, raw, auditoria, modelo, X


def test_web_historico_modelo_real_y_auditoria(historico):
    ruta, raw, auditoria, modelo, X = historico
    app = crear_app(ruta, raw, auditoria, reloj=lambda: AHORA)
    with TestClient(app) as cliente:
        assert 'id="historico-form"' in cliente.get("/").text
        assert 'api("/api/historico?dia="' in cliente.get("/assets/monitor.js").text
        salud = cliente.get("/health").json()
        assert salud["estado"] == "ok"
        respuesta = cliente.post(f"/api/historico?dia={DIA}")
        assert respuesta.status_code == 200

    resultado = respuesta.json()
    assert resultado["estado"] == "reproducido"
    assert resultado["modelo"]["version"] == sha256(ruta.read_bytes()).hexdigest()
    primera, segunda, tercera = resultado["serie"][:3]
    assert primera["kp_previsto"] is None
    assert primera["kp_observado"] == 1
    assert segunda["kp_previsto"] == pytest.approx(modelo.predict(X.iloc[[1]])[0])
    assert segunda["kp_observado"] == 4.3
    assert segunda["emision"] is None
    assert segunda["recepcion_original"] is None
    assert segunda["ventana_fin"] == segunda["objetivo_inicio"]
    assert tercera["kp_previsto"] is not None and tercera["kp_observado"] is None
    assert resultado["ia"]["proveedor"] == "mock"
    assert resultado["ia"]["simulada"] is True
    assert resultado["ia"]["texto"].startswith("[mock]")
    archivo = auditoria / (resultado["auditoria_id"] + ".json")
    guardado = json.loads(archivo.read_text(encoding="utf-8"))
    assert guardado["serie"][1]["entradas"] == dict(zip(ENTRADAS_MODELO, [-2, 4, 400]))
    assert guardado["serie"][1]["kp_previsto"] == segunda["kp_previsto"]


def test_modelo_invalido_salud_degradada(tmp_path):
    ruta = tmp_path / "modelo.joblib"
    ruta.write_bytes(b"corrupto")
    with TestClient(crear_app(ruta_modelo=ruta, ruta_operativo=tmp_path / "no-existe")) as cliente:
        assert cliente.get("/health").json()["estado"] == "degradado"
        assert cliente.post(f"/api/historico?dia={DIA}").json()["motivo"] == "modelo_no_disponible"


def test_observacion_endpoint_no_consulta_bloque_abierto(tmp_path):
    def inesperado(url):
        pytest.fail(f"Consulta externa inesperada: {url}")

    app = crear_app(ruta_modelo=tmp_path / "no-existe", descargar=inesperado, reloj=lambda: INICIO)
    with TestClient(app) as cliente:
        assert cliente.get(f"/api/observacion?bloque={DIA}T00:00Z").json()["estado"] == "bloque_abierto"
        assert cliente.get(f"/api/observacion?bloque={DIA}T01:00Z").status_code == 422


def test_directo_api_fuente_caida_sin_modelo(tmp_path):
    def sin_red(url):
        raise TimeoutError("NOAA")

    app = crear_app(ruta_modelo=tmp_path / "no-existe", ruta_operativo=tmp_path / "no-existe",
                    descargar=sin_red, reloj=lambda: AHORA)
    with TestClient(app) as cliente:
        resultado = cliente.post("/api/pronostico").json()
        assert resultado["motivo"] == "fuente_no_disponible"
        assert resultado["kp_previsto"] is None
        assert resultado["modelo"]["estado"] == "no_disponible"
