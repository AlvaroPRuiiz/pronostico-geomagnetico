"""Descarga los datasets de la entrega sin incluirlos en Git."""

import argparse
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
OMNI_BASE_URL = "https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni"

SOURCES = {
    "ventas.csv": (
        "https://raw.githubusercontent.com/AlvaroPRuiiz/"
        "dsia-26-27-alvaro-poveda/08d2c302d06f527c94156327460ce26f0da458fe/"
        "3_automatizacion_e_ia/Datos/ventas.csv"
    ),
}


def main() -> None:
    """Guarda los archivos en data; conserva los existentes salvo --force."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Volver a descargar archivos existentes.",
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data")
    parser.add_argument(
        "--omni-years",
        nargs=2,
        type=int,
        metavar=("INICIO", "FIN"),
        default=(2000, 2000),
        help="Primer y último año de OMNI que se descargarán, ambos incluidos.",
    )
    args = parser.parse_args()

    inicio, fin = args.omni_years
    if inicio > fin:
        parser.error("El año de inicio debe ser menor o igual que el año final.")

    fuentes = SOURCES.copy()
    for anio in range(inicio, fin + 1):
        nombre = f"omni2_{anio}.dat"
        fuentes[f"raw/{nombre}"] = f"{OMNI_BASE_URL}/{nombre}"

    for name, url in fuentes.items():
        path = args.output_dir / name
        if path.is_file() and not args.force:
            print(f"Ya existe: {path}")
            continue

        with urlopen(url, timeout=60) as response:
            content = response.read()

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        print(f"Descargado: {path}")


if __name__ == "__main__":
    main()