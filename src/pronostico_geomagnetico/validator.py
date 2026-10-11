import pandas as pd

from .exceptions import OmniValidationError

MIN_HOUR = 0
MAX_HOUR = 23


def validate_omni(df: pd.DataFrame) -> None:
    """Valida los campos de fecha y hora y rechaza registros duplicados."""
    columnas_necesarias = ["year", "day_of_year", "hour"]

    for columna in columnas_necesarias:
        if columna not in df.columns:
            raise OmniValidationError(
                f"Falta la columna obligatoria: {columna}"
            )

    # Validar el año.
    if df["year"].isna().any():
        raise OmniValidationError(
            "El año no puede contener valores ausentes"
        )

    if not pd.api.types.is_numeric_dtype(df["year"]):
        raise OmniValidationError(
            "El año debe contener valores numéricos"
        )

    if (df["year"] % 1 != 0).any():
        raise OmniValidationError(
            "El año debe ser un número entero"
        )

    # Validar el día del año.
    if df["day_of_year"].isna().any():
        raise OmniValidationError(
            "El día del año no puede contener valores ausentes"
        )

    if not pd.api.types.is_numeric_dtype(df["day_of_year"]):
        raise OmniValidationError(
            "El día del año debe contener valores numéricos"
        )

    if (df["day_of_year"] % 1 != 0).any():
        raise OmniValidationError(
            "El día del año debe ser un número entero"
        )

    if (~df["day_of_year"].between(1, 366)).any():
        raise OmniValidationError(
            "El día del año debe estar entre 1 y 366"
        )

    # El día 366 solo existe en años bisiestos.
    bisiesto = (
        (df["year"] % 4 == 0)
        & (
            (df["year"] % 100 != 0)
            | (df["year"] % 400 == 0)
        )
    )

    if ((df["day_of_year"] == 366) & ~bisiesto).any():
        raise OmniValidationError(
            "El día 366 solo es válido en años bisiestos"
        )

    # Validar la hora.
    if df["hour"].isna().any():
        raise OmniValidationError(
            "La hora no puede contener valores ausentes"
        )

    if not pd.api.types.is_numeric_dtype(df["hour"]):
        raise OmniValidationError(
            "La hora debe contener valores numéricos"
        )

    if (df["hour"] % 1 != 0).any():
        raise OmniValidationError(
            "La hora debe ser un número entero"
        )

    if (~df["hour"].between(MIN_HOUR, MAX_HOUR)).any():
        raise OmniValidationError(
            f"La hora debe estar entre {MIN_HOUR} y {MAX_HOUR}"
        )

    # Rechazar registros del mismo instante.
    if df.duplicated(subset=["year", "day_of_year", "hour"]).any():
        raise OmniValidationError(
            "Hay registros duplicados para el mismo año, día y hora"
        )
    