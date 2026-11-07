"""Entrena y guarda el modelo de pronóstico de Kp."""

import argparse
import logging
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from .features import construir_dataset
from .loader import load_omni
from .preprocessor import preprocess_omni
from .validator import validate_omni


def entrenar_modelo(carpeta_datos: Path) -> HistGradientBoostingRegressor:
    """Entrena el modelo final con los archivos OMNI de 2000 a 2023."""
    archivos = []

    for anio in range(2000, 2024):
        ruta = carpeta_datos / f"omni2_{anio}.dat"
        archivos.append(load_omni(ruta))

    datos = pd.concat(archivos, ignore_index=True)
    validate_omni(datos)
    datos_limpios = preprocess_omni(datos)
    dataset = construir_dataset(datos_limpios)

    X = dataset.drop(columns="kp_objetivo")
    y = dataset["kp_objetivo"]

    logging.info("Entrenando con %d emisiones de 2000–2023.", len(dataset))
    modelo = HistGradientBoostingRegressor(early_stopping=False, random_state=42)
    modelo.fit(X, y)
    return modelo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/modelo_kp.joblib")
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    modelo = entrenar_modelo(args.input_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(modelo, args.output)
    logging.info("Modelo guardado en %s", args.output)


if __name__ == "__main__":
    main()