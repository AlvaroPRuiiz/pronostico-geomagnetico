import pandas as pd


def calculate_metrics(df: pd.DataFrame) -> dict:
    """Calcula la disponibilidad de las variables seleccionadas."""
    columnas = [
        "bz_gsm_nt",
        "proton_density_cm3",
        "solar_wind_speed_kms",
        "kp_x10",
    ]

    completas = df[columnas].notna().all(axis=1)
    total = len(df)

    return {
        "total_filas": total,
        "filas_completas": int(completas.sum()),
        "filas_incompletas": int((~completas).sum()),
        "porcentaje_completas": (
            float(completas.mean() * 100) if total > 0 else 0.0
        ),
    }