from pathlib import Path
from typing import Protocol

import pandas as pd


class DataLoadError(Exception):
    """Error al cargar datos de origen."""


class SalesRepository(Protocol):
    """Contrato de lectura usado por la CLI, como en el ejemplo de clase."""

    def load(self) -> pd.DataFrame: ...


class CsvSalesRepository:
    """Lee ventas desde un CSV."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> pd.DataFrame:
        """Carga el CSV o lanza un error de dominio."""
        return load(self._path)


def load(path: Path) -> pd.DataFrame:
    """Lee un CSV y traduce errores de lectura a DataLoadError."""
    if not path.is_file():
        raise DataLoadError(f"No existe el fichero: {path}")
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeError) as error:
        raise DataLoadError(f"No se puede leer el fichero: {path}") from error
