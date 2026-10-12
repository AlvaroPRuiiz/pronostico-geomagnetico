import json
import pytest
import subprocess
import sys
from pathlib import Path
import pandas as pd

from src.ventas_app.cli import main


def test_cli_como_modulo(tmp_path, ventas):
    entrada = tmp_path / "ventas.csv"
    salida = tmp_path / "resultados" / "ventas_validas.csv"
    
    ventas.to_csv(entrada, index=False)
    result = subprocess.run(
        [sys.executable, "-m", "src.ventas_app.cli", "--input", str(entrada), "--output", str(salida)],
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True,
    )
    
    assert result.returncode == 0, result.stderr
    assert pd.read_csv(salida)["importe"].sum() == 45.0


def test_main_argumentos_controlados(tmp_path, ventas):

    entrada = tmp_path / "ventas.csv"
    salida = tmp_path / "validas.csv"
    
    ventas.to_csv(entrada, index=False)
    main(["--input", str(entrada), "--output", str(salida)])
    
    assert pd.read_csv(salida)["importe"].tolist() == [20.0, 15.0, 10.0]


@pytest.mark.integration
def test_exportacion_csv_curso(tmp_path):
    from src.ventas_app.cli import main
    entrada = Path(__file__).resolve().parents[2] / "data" / "ventas.csv"
    salida = tmp_path / "limpias.csv"
    
    main(["--input", str(entrada), "--output", str(salida)])
    calidad = json.loads((tmp_path / "calidad_datos.json").read_text())
    
    assert calidad["filas_totales"] == 150
    assert calidad["filas_validas"] == 140
    assert calidad["filas_invalidas"] == 10
    assert calidad["importe_total"] == pytest.approx(pd.read_csv(salida)["importe"].sum())
    metricas = json.loads((tmp_path / "metricas_ventas.json").read_text())
    assert len(metricas["top_productos"]) == 3
    assert sum(r["importe"] for r in metricas["importe_por_region"]) == pytest.approx(calidad["importe_total"])


@pytest.mark.parametrize("contenido", [None, "", "otra\n1\n"])
def test_cli_error(tmp_path, capsys, contenido):
    entrada = tmp_path / "ventas.csv"
    
    if contenido is not None:
        entrada.write_text(contenido)
    with pytest.raises(SystemExit) as error:
        main(["--input", str(entrada), "--output", str(tmp_path / "salida.csv")])
    assert error.value.code == 1
    assert "Error:" in capsys.readouterr().err
