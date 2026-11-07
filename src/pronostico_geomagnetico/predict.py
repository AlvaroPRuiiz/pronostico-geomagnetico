"""Predice el Kp del siguiente bloque de tres horas."""

import argparse
from pathlib import Path

import joblib
import pandas as pd

from .features import construir_dataset
from .loader import load_omni
from .preprocessor import preprocess_omni
from .validator import validate_omni
from .ai_client import complete


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--emision", required=True, help="Fecha y hora UTC de emisión.")
    parser.add_argument("--provider", choices=["mock", "hf"], default="mock")
    args = parser.parse_args()

    emision = pd.to_datetime(args.emision, utc=True, errors="coerce")
    if pd.isna(emision) or emision != emision.floor("3h"):
        parser.error("--emision debe indicar el inicio de un bloque de 3 horas UTC.")

    datos = load_omni(args.input)
    validate_omni(datos)
    datos_limpios = preprocess_omni(datos)
   
    try:
        kp_predicho = predecir_kp(datos_limpios, emision, args.model)
    except ValueError as error:
        parser.error(str(error))
        
    fin = emision + pd.Timedelta(hours=3)

    print(f"Bloque UTC: {emision:%Y-%m-%d %H:%M} a {fin:%Y-%m-%d %H:%M}")
    print(f"Kp predicho: {kp_predicho:.2f}")

    prompt = (
        f"Resume en una frase el pronóstico de Kp {kp_predicho:.2f} "
        f"para el bloque de {emision:%Y-%m-%d %H:%M} "
        f"a {fin:%Y-%m-%d %H:%M} UTC."
    )
    respuesta = complete(args.provider, prompt)    
    print(respuesta.text)
    
def predecir_kp(datos_limpios: pd.DataFrame, emision: pd.Timestamp, ruta_modelo: Path) -> float:
    """Carga el modelo y predice con las tres horas previas a la emisión."""
    entradas = construir_dataset(datos_limpios, incluir_objetivo=False)

    if emision not in entradas.index:
        raise ValueError("Faltan mediciones de viento solar en las tres horas anteriores.")

    modelo = joblib.load(ruta_modelo)
    return float(modelo.predict(entradas.loc[[emision]])[0])

if __name__ == "__main__":
    main()