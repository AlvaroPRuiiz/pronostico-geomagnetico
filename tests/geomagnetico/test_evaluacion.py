import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.pronostico_geomagnetico.evaluacion import leer_wdc, metricas, resumen_comparacion
from src.pronostico_geomagnetico.web import crear_app


def test_wdc_tercios_y_ausentes():
    fila = "21 1 1255610" + "".join(f"{kp:2}" for kp in [3, 7, 10, 33, 57, 90, -1, 0])
    valores = leer_wdc("# fuente GFZ\n" + fila, 2021)
    assert valores.index[0] == pd.Timestamp("2021-01-01T00:00:00Z")
    assert valores.index[-1] == pd.Timestamp("2021-01-01T21:00:00Z")
    assert valores.iloc[:6].tolist() == [0.333, 0.667, 1., 3.333, 5.667, 9.]
    assert pd.isna(valores.iloc[6])


def test_metricas_tormenta_umbral_y_matriz():
    r = metricas([0., 5., 7., 2.], [1., 4., 6., 8.])
    assert r["mae"] == 2.25
    assert r["rmse"] == pytest.approx((39 / 4) ** .5)
    assert r["r2"] == pytest.approx(1 - 39 / 29)
    assert r["mae_tormentas"] == 1
    assert r["precision"] == r["recall"] == r["f1"] == .5
    assert r["matriz"] == [[1, 1], [1, 1]]


def test_metricas_sobre_interseccion_compartida():
    serie = pd.DataFrame({"kp_observado": [1., 7., 3.], "kp_previsto": [1., None, 8.],
                          "kp_persistencia": [2., 0., None]})
    c = resumen_comparacion(serie, 3)
    assert c["bloques"] == 1
    assert c["cobertura"] == pytest.approx(1 / 3)
    assert c["modelo"]["mae"] == 0 and c["persistencia"]["mae"] == 1
    assert c["modelo"]["r2"] is None


def test_api_evaluacion_filtra_intervalo_utc(tmp_path):
    (tmp_path / "evaluacion.json").write_text(json.dumps({"periodos": {"gfz2026": {}}}), encoding="utf-8")
    (tmp_path / "evaluacion_gfz2026.csv").write_text(
        "bloque,kp_observado,kp_previsto,kp_persistencia\n"
        "2026-01-01T21:00:00Z,3.0,2.0,2.0\n"
        "2026-01-02T00:00:00Z,2.0,,1.0\n"
        "2026-01-03T00:00:00Z,1.0,1.0,1.0\n",
        encoding="utf-8",
    )
    app = crear_app(ruta_modelo=tmp_path / "no", ruta_operativo=tmp_path / "no",
                    carpeta_evaluacion=tmp_path)
    with TestClient(app) as cliente:
        assert cliente.get("/api/evaluacion").json()["estado"] == "disponible"
        r = cliente.get("/api/evaluacion/gfz2026?inicio=2026-01-02&dias=1").json()
        assert r["serie"] == [{"objetivo_inicio": "2026-01-02T00:00:00Z", "kp_observado": 2.0,
                               "kp_previsto": None, "kp_persistencia": 1.0}]
        assert cliente.get("/api/evaluacion/otro?inicio=2026-01-02").status_code == 404
