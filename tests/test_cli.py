import pytest
import json

from src.pronostico_geomagnetico.cli import main
from src.pronostico_geomagnetico.loader import COLUMN_NAMES

def test_cli_archivo_inexistente(tmp_path):
    """Termina con código 1 si el archivo de entrada no existe."""
    # Preparar.
    entrada = tmp_path / "no_existe.dat"
    salida = tmp_path / "metricas.json"

    argumentos = [
        "--input", str(entrada),
        "--output", str(salida),
    ]

    # Ejecutar.
    with pytest.raises(SystemExit) as error:
        main(argumentos)

    # Comprobar.
    assert error.value.code == 1
    assert not salida.exists()
    
@pytest.mark.integration
def test_cli_archivo_valido(tmp_path):
    """Guarda las métricas de un archivo OMNI válido."""

    # Preparar una fila con las 55 columnas.
    entrada = tmp_path / "omni.dat"
    salida = tmp_path / "resultados" / "metricas.json"

    valores = ["0"] * len(COLUMN_NAMES)
    valores[COLUMN_NAMES.index("year")] = "2000"
    valores[COLUMN_NAMES.index("day_of_year")] = "1"
    valores[COLUMN_NAMES.index("hour")] = "0"

    entrada.write_text(" ".join(valores) + "\n", encoding="utf-8")

    # Ejecutar.
    main([
        "--input", str(entrada),
        "--output", str(salida),
    ])

    # Comprobar.
    assert salida.is_file()

    resultado = json.loads(salida.read_text(encoding="utf-8"))

    assert resultado["total_filas"] == 1
    assert resultado["filas_completas"] == 1
    assert resultado["filas_incompletas"] == 0
    assert resultado["porcentaje_completas"] == 100.0