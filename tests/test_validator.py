import pandas as pd
import pytest

from src.pronostico_geomagnetico.exceptions import OmniValidationError
from src.pronostico_geomagnetico.validator import validate_omni

def test_validate_omni_columna_ausente():
    """Rechaza datos sin una columna obligatoria."""
    df = pd.DataFrame({"year": [1990], "hour": [12]})

    with pytest.raises(
        OmniValidationError,
        match="Falta la columna obligatoria: day_of_year",
    ):validate_omni(df)


def test_validate_omni_year_ausente():
    """Rechaza un año ausente."""
    df = pd.DataFrame({
        "year": [None],
        "day_of_year": [1],
        "hour": [12],
    })

    with pytest.raises(OmniValidationError, match="El año no puede contener valores ausentes"):
        validate_omni(df)


def test_validate_omni_year_no_numerico():
    """Rechaza un año de tipo texto."""
    df = pd.DataFrame({
        "year": ["hola"],
        "day_of_year": [1],
        "hour": [12],
    })

    with pytest.raises(OmniValidationError, match="El año debe contener valores numéricos"):
        validate_omni(df)


def test_validate_omni_year_decimal():
    """Rechaza un año con decimales."""
    df = pd.DataFrame({
        "year": [1990.5],
        "day_of_year": [1],
        "hour": [12],
    })

    with pytest.raises(OmniValidationError, match="El año debe ser un número entero"):
        validate_omni(df)


def test_validate_omni_dia_ausente():
    """Rechaza un día del año ausente."""
    df = pd.DataFrame({
        "year": [1990],
        "day_of_year": [None],
        "hour": [12],
    })

    with pytest.raises(
        OmniValidationError,
        match="El día del año no puede contener valores ausentes",
    ):validate_omni(df)


def test_validate_omni_dia_no_numerico():
    """Rechaza un día del año de tipo texto."""
    df = pd.DataFrame({
        "year": [1990],
        "day_of_year": ["hola"],
        "hour": [12],
    })

    with pytest.raises(
        OmniValidationError,
        match="El día del año debe contener valores numéricos",
    ):validate_omni(df)


def test_validate_omni_dia_decimal():
    """Rechaza un día del año con decimales."""
    df = pd.DataFrame({
        "year": [1990],
        "day_of_year": [1.5],
        "hour": [12],
    })

    with pytest.raises(
        OmniValidationError,
        match="El día del año debe ser un número entero",
    ):validate_omni(df)


def test_validate_omni_dia_fuera_de_rango():
    """Rechaza días inferiores a 1 y superiores a 366."""
    for dia in [0, 367]:
        df = pd.DataFrame({
            "year": [1990],
            "day_of_year": [dia],
            "hour": [12],
        })

        with pytest.raises(
            OmniValidationError,
            match="El día del año debe estar entre 1 y 366",
        ):validate_omni(df)


def test_validate_omni_hora_ausente():
    """Rechaza una hora ausente."""
    df = pd.DataFrame({
        "year": [1990],
        "day_of_year": [1],
        "hour": [None],
    })

    with pytest.raises(
        OmniValidationError,
        match="La hora no puede contener valores ausentes",
    ):validate_omni(df)


def test_validate_omni_hora_no_numerica():
    """Rechaza una hora de tipo texto."""
    df = pd.DataFrame({
        "year": [1990],
        "day_of_year": [1],
        "hour": ["hola"],
    })

    with pytest.raises(
        OmniValidationError,
        match="La hora debe contener valores numéricos",
    ):validate_omni(df)


def test_validate_omni_hora_decimal():
    """Rechaza una hora con decimales."""
    df = pd.DataFrame({
        "year": [1990],
        "day_of_year": [1],
        "hour": [12.5],
    })

    with pytest.raises(
        OmniValidationError,
        match="La hora debe ser un número entero",
    ):validate_omni(df)


def test_validate_omni_hora_negativa():
    """Rechaza una hora inferior a cero."""
    df = pd.DataFrame({
        "year": [1990],
        "day_of_year": [1],
        "hour": [-1],
    })

    with pytest.raises(
        OmniValidationError,
        match="La hora debe estar entre 0 y 23",
    ):validate_omni(df)


def test_validate_omni_regla_bisiestos_siglos():
    """Acepta el día 366 en 2000 y lo rechaza en 1900."""
    df = pd.DataFrame({
        "year": [2000],
        "day_of_year": [366],
        "hour": [12],
    })

    assert validate_omni(df) is None

    df["year"] = 1900

    with pytest.raises(
        OmniValidationError,
        match="El día 366 solo es válido en años bisiestos",
    ):validate_omni(df)
    
@pytest.mark.parametrize("hora", [-1, 24, 100])
def test_validate_omni_hora_fuera_de_rango(hora):
    """Rechaza horas inferiores a 0 o superiores a 23."""
    df = pd.DataFrame({
        "year": [2000],
        "day_of_year": [1],
        "hour": [hora],
    })

    with pytest.raises(
        OmniValidationError,
        match="La hora debe estar entre 0 y 23",
    ):validate_omni(df)