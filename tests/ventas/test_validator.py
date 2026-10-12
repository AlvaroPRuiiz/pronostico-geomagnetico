from pathlib import Path
import pytest
from src.ventas_app.loader import load
from src.ventas_app.validator import validar_ventas


@pytest.mark.parametrize("campo", ["unidades", "precio_unitario"])
@pytest.mark.parametrize("valor", [0, -1, None, "texto"])
def test_valores_invalidos(ventas, campo, valor):
    ventas[campo] = ventas[campo].astype(object)
    ventas.loc[0, campo] = valor
    validos, errores = validar_ventas(ventas)
    
    assert len(validos) == 2
    assert len(errores) == 1


def test_ventas_validas(ventas):
    original = ventas.copy()
    validos, errores = validar_ventas(ventas)
    
    assert errores.empty
    assert validos["importe"].tolist() == [20.0, 15.0, 10.0]
    assert ventas.equals(original)


@pytest.mark.integration
def test_csv_curso_140_validas_10_invalidas():
    path = Path(__file__).resolve().parents[2] / "data" / "ventas.csv"
    validos, errores = validar_ventas(load(path))
    
    assert len(validos) == 140
    assert len(errores) == 10


@pytest.mark.parametrize("precio, valido", [(0, False), (-1, False), (1, True)])
def test_bordes_precio(ventas, precio, valido):
    ventas.loc[0, "precio_unitario"] = precio
    validos, errores = validar_ventas(ventas)
    
    assert (0 in validos.index) == valido
    assert (0 in errores.index) != valido


def test_columnas_ausentes(ventas):
    from src.ventas_app.validator import ValidationError
    with pytest.raises(ValidationError, match="precio_unitario"):
        validar_ventas(ventas.drop(columns="precio_unitario"))
