"""Descarga los datasets de la entrega sin incluirlos en Git."""
import argparse
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "ventas.csv": "https://raw.githubusercontent.com/AlvaroPRuiiz/dsia-26-27-alvaro-poveda/08d2c302d06f527c94156327460ce26f0da458fe/3_automatizacion_e_ia/Datos/ventas.csv",
    "raw/omni2_2000.dat": "https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni/omni2_2000.dat",
}


def main() -> None:
    """Guarda los archivos en data; conserva los existentes salvo --force."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Volver a descargar archivos existentes")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    for name, url in SOURCES.items():
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
