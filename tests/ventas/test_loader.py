import pytest
from src.ventas_app.loader import DataLoadError, load


def test_carga_correcta(tmp_path, ventas):
    path = tmp_path / "ventas.csv"
    ventas.to_csv(path, index=False)
    result = load(path)
    
    assert result.shape == (3, 6)
    assert result.loc[0, "unidades"] == 2


def test_archivo_inexistente(tmp_path):
    with pytest.raises(DataLoadError, match="No existe"):
        load(tmp_path / "no_existe.csv")
