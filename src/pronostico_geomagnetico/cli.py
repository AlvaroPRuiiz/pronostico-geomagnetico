import argparse
import json
import sys
from pathlib import Path

from .loader import load_omni
from .validator import validate_omni
from .preprocessor import preprocess_omni
from .metrics import calculate_metrics
from .exceptions import OmniLoadError, OmniValidationError

#Se ejecuta como: python -m src.pronostico_geomagnetico.cli --input data/raw/omni2_2000.dat --output data/processed/metrics_2000.json
def main(argv: list[str] | None = None) -> None:
    """Valida un archivo OMNI y guarda sus métricas en JSON."""
    parser = argparse.ArgumentParser(
        description="Analiza un archivo horario de OMNI."
    )

    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Ruta del archivo OMNI de entrada.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Ruta donde guardar las métricas en JSON.",
    )

    args = parser.parse_args(argv)
    try:
        df = load_omni(args.input)
        validate_omni(df)
        df_clean = preprocess_omni(df)
        resultado = calculate_metrics(df_clean)

        args.output.parent.mkdir(parents=True, exist_ok=True)

        with args.output.open("w", encoding="utf-8") as archivo:
            json.dump(resultado, archivo, indent=4, ensure_ascii=False)

    except (OmniLoadError, OmniValidationError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    print(f"Métricas guardadas en: {args.output}")


if __name__ == "__main__":
    main()