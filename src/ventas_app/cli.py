import argparse
import json
import sys
from pathlib import Path

from .loader import CsvSalesRepository, DataLoadError, SalesRepository
from .validator import ValidationError, validar_ventas
from .metrics import importe_por_region, top_productos, clientes_recurrentes


def main(argv: list[str] | None = None) -> None:
    """Exporta ventas validas, calidad de datos y agregaciones de negocio."""
    parser = argparse.ArgumentParser(description="Valida y analiza ventas.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        repo: SalesRepository = CsvSalesRepository(args.input)
        frame = repo.load()
        validos, errores = validar_ventas(frame)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        validos.to_csv(args.output, index=False)
        calidad = {
            "filas_totales": len(frame),
            "filas_validas": len(validos),
            "filas_invalidas": len(errores),
            "importe_total": float(validos["importe"].sum()),
        }
        metricas = {
            "importe_por_region": importe_por_region(validos).to_dict(orient="records"),
            "top_productos": top_productos(validos).to_dict(orient="records"),
            "clientes_recurrentes": {str(k): int(v) for k, v in clientes_recurrentes(validos).items()},
        }
        for name, data in (("calidad_datos.json", calidad), ("metricas_ventas.json", metricas)):
            (args.output.parent / name).write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            
    except (DataLoadError, ValidationError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
