import pandas as pd


COLUMNAS_VIENTO = [
    "bz_gsm_nt",
    "proton_density_cm3",
    "solar_wind_speed_kms",
]


def construir_dataset(
    df: pd.DataFrame, incluir_objetivo: bool = True
) -> pd.DataFrame:
    
    """Une las medias del viento del bloque anterior con el Kp objetivo."""
    datos = df.copy()

    inicio_anio = pd.to_datetime(
        datos["year"].astype(int).astype(str), format="%Y", utc=True
    )
    datos["timestamp"] = (
        inicio_anio
        + pd.to_timedelta(datos["day_of_year"] - 1, unit="D")
        + pd.to_timedelta(datos["hour"], unit="h")
    )
    datos["bloque_kp"] = datos["timestamp"].dt.floor("3h")

    grupos = datos.groupby("bloque_kp")

    # Entradas: las tres horas del bloque anterior deben estar completas.
    viento = grupos[COLUMNAS_VIENTO]
    ventana_valida = grupos.size().eq(3) & viento.count().eq(3).all(axis=1)
    entradas = viento.mean().loc[ventana_valida].add_suffix("_media_3h")
    entradas.index = entradas.index + pd.Timedelta(hours=3)
    entradas.index.name = "emision"

    if not incluir_objetivo:
        return entradas.sort_index()
    
    # Etiqueta: un único Kp válido por bloque.
    kp = grupos["kp_x10"]
    objetivo_valido = grupos.size().eq(3) & kp.count().eq(3) & kp.nunique().eq(1)
    objetivo = (
        kp.first().where(objetivo_valido).div(10)
        .rename("kp_objetivo").rename_axis("emision")
    )

    return objetivo.to_frame().join(entradas).dropna().sort_index()
