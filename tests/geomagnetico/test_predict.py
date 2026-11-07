import joblib
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression

from src.pronostico_geomagnetico.predict import predecir_kp


@pytest.mark.integration
def test_predecir_kp_carga_modelo_sin_kp_observado(tmp_path):
    X = pd.DataFrame({
        "bz_gsm_nt_media_3h": [-6.0, -3.0, 0.0],
        "proton_density_cm3_media_3h": [5.0, 5.0, 5.0],
        "solar_wind_speed_kms_media_3h": [400.0, 400.0, 400.0],
    })
    modelo = LinearRegression().fit(X, [3.0, 2.0, 1.0])
    ruta_modelo = tmp_path / "modelo.joblib"
    joblib.dump(modelo, ruta_modelo)

    datos = pd.DataFrame({
        "year": [2024, 2024, 2024],
        "day_of_year": [1, 1, 1],
        "hour": [0, 1, 2],
        "bz_gsm_nt": [-4.0, -3.0, -2.0],
        "proton_density_cm3": [5.0, 5.0, 5.0],
        "solar_wind_speed_kms": [400.0, 400.0, 400.0],
    })
    emision = pd.Timestamp("2024-01-01 03:00", tz="UTC")

    assert predecir_kp(datos, emision, ruta_modelo) == pytest.approx(2.0)