import pandas as pd

from src.pronostico_geomagnetico.preprocessor import preprocess_omni


def test_preprocess_omni_convierte_codigos_sin_modificar_original():
    """Convierte los códigos a NaN y conserva los valores válidos."""
    # Preparar.
    df = pd.DataFrame({
        "bz_gsm_nt": [999.9, -5.0],
        "proton_density_cm3": [999.9, 8.0],
        "solar_wind_speed_kms": [9999.0, 450.0],
        "kp_x10": [99, 30],
    })
    original = df.copy()

    # Ejecutar el preprocesado
    resultado = preprocess_omni(df)

    # Comprobar 
    assert resultado.iloc[0].isna().all()
    
    #Compara la segunda fila del resultado con la segunda fila original
    pd.testing.assert_series_equal(
        resultado.iloc[1],
        original.iloc[1],
        check_dtype=False,
    )
    pd.testing.assert_frame_equal(df, original)