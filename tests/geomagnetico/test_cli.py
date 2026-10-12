import pytest
import json

from src.pronostico_geomagnetico.cli import main
from src.pronostico_geomagnetico.loader import COLUMN_NAMES

def test_cli_archivo_inexistente(tmp_path):
    """Termina con código 1 si el archivo de entrada no existe."""

    entrada = tmp_path / "no_existe.dat"
    salida = tmp_path / "metricas.json"

    argumentos = [
        "--input", str(entrada),
        "--output", str(salida),
    ]

    with pytest.raises(SystemExit) as error:
        main(argumentos)

    assert error.value.code == 1
    assert not salida.exists()
    
@pytest.mark.integration
def test_cli_archivo_valido(tmp_path):
    """Guarda las métricas de un archivo OMNI válido."""

    entrada = tmp_path / "omni.dat"
    salida = tmp_path / "resultados" / "metricas.json"

    valores = ["0"] * len(COLUMN_NAMES)
    valores[COLUMN_NAMES.index("year")] = "2000"
    valores[COLUMN_NAMES.index("day_of_year")] = "1"
    valores[COLUMN_NAMES.index("hour")] = "0"

    entrada.write_text(" ".join(valores) + "\n", encoding="utf-8")

    main([
        "--input", str(entrada),
        "--output", str(salida),
    ])

    assert salida.is_file()

    resultado = json.loads(salida.read_text(encoding="utf-8"))

    assert resultado["total_filas"] == 1
    assert resultado["filas_completas"] == 1
    assert resultado["filas_incompletas"] == 0
    assert resultado["porcentaje_completas"] == 100.0

@pytest.mark.integration
def test_cli_dataset_2000(tmp_path):
    from pathlib import Path
    entrada = Path(__file__).resolve().parents[2] / "data" / "raw" / "omni2_2000.dat"
    salida = tmp_path / "metricas.json"
    main(["--input", str(entrada), "--output", str(salida)])
    resultado = json.loads(salida.read_text())
    assert resultado["total_filas"] == 8784
    assert resultado["filas_completas"] + resultado["filas_incompletas"] == 8784
