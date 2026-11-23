import pandas as pd


COLUMNAS_VIENTO = [
    "bz_gsm_nt",
    "proton_density_cm3",
    "solar_wind_speed_kms",
]
ENTRADAS_MODELO = [f"{columna}_media_3h" for columna in COLUMNAS_VIENTO]
BLOQUE = pd.Timedelta(hours=3)


def construir_dataset(
    df: pd.DataFrame, incluir_objetivo: bool = True, *, exigir_objetivo: bool = True
) -> pd.DataFrame:
    
    """Indexa las medias del bloque OMNI anterior por el inicio del objetivo."""
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
    horas_completas = grupos.size().eq(3) & grupos["timestamp"].nunique().eq(3)

    # Entradas: las tres horas del bloque anterior deben estar completas.
    viento = datos[COLUMNAS_VIENTO].replace([float("inf"), float("-inf")], float("nan"))
    viento = viento.groupby(datos["bloque_kp"])
    ventana_valida = horas_completas & viento.count().eq(3).all(axis=1)
    entradas = viento.mean().loc[ventana_valida].add_suffix("_media_3h")
    entradas.index = entradas.index + BLOQUE
    entradas.index.name = "emision"

    if not incluir_objetivo:
        return entradas.sort_index()
    
    # Etiqueta: un único Kp válido por bloque.
    kp = grupos["kp_x10"]
    objetivo_valido = (
        horas_completas & kp.count().eq(3) & kp.nunique().eq(1) & kp.first().between(0, 90)
    )
    objetivo = (
        kp.first().where(objetivo_valido).div(10)
        .rename("kp_objetivo").rename_axis("emision")
    )

    resultado = entradas.join(objetivo, how="outer").sort_index()
    if exigir_objetivo:
        resultado = resultado.dropna()
    return resultado[["kp_objetivo", *ENTRADAS_MODELO]]
