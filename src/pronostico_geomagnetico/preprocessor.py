import pandas as pd


FILL_VALUES = {
    "bz_gsm_nt": 999.9,
    "proton_density_cm3": 999.9,
    "solar_wind_speed_kms": 9999.0,
    "kp_x10": 99,
}


def preprocess_omni(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte los códigos vacios de cuatro variables a NaN."""
    df_clean = df.copy()

    for columna, codigo in FILL_VALUES.items():
        df_clean[columna] = df_clean[columna].replace(
            codigo, float("nan")
        )

    return df_clean