import pandas as pd
import pytest

from src.pronostico_geomagnetico.metrics import calculate_metrics


@pytest.fixture
def datos_omni():
    """Prepara dos filas: una completa y otra incompleta."""
    return pd.DataFrame({
        "bz_gsm_nt": [-5.0, float("nan")],
        "proton_density_cm3": [8.0, 6.0],
        "solar_wind_speed_kms": [450.0, 400.0],
        "kp_x10": [30, 20],
    })


def test_calculate_metrics_con_fila_incompleta(datos_omni):
    """Comprueba los recuentos y el porcentaje de filas completas."""
    # Ejecutar
    resultado = calculate_metrics(datos_omni)

    # Comprobar
    assert resultado["total_filas"] == 2
    assert resultado["filas_completas"] == 1
    assert resultado["filas_incompletas"] == 1
    assert resultado["porcentaje_completas"] == 50.0


def test_calculate_metrics_dataframe_vacio():
    """Devuelve métricas a cero cuando no hay filas."""
    
    df = pd.DataFrame(columns=[
        "bz_gsm_nt",
        "proton_density_cm3",
        "solar_wind_speed_kms",
        "kp_x10",
    ])

    # Ejecutar
    resultado = calculate_metrics(df)

    # Comprobar 
    assert resultado["total_filas"] == 0
    assert resultado["filas_completas"] == 0
    assert resultado["filas_incompletas"] == 0
    assert resultado["porcentaje_completas"] == 0.0


def test_calculate_metrics_no_modifica_datos(datos_omni):
    """Comprueba que calcular métricas conserva los datos de entrada."""
    # Preparar
    original = datos_omni.copy()

    # Ejecutar
    calculate_metrics(datos_omni)

    # Comprobar
    pd.testing.assert_frame_equal(datos_omni, original)