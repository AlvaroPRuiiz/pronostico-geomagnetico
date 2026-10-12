from src.ventas_app.metrics import importe_por_region, top_productos, clientes_recurrentes
from src.ventas_app.validator import validar_ventas


def test_importe_region(ventas):
    validos, _ = validar_ventas(ventas)
    result = importe_por_region(validos).set_index("region")["importe"].to_dict()
    
    assert result == {"Norte": 30.0, "Sur": 15.0}


def test_top_productos(ventas):
    validos, _ = validar_ventas(ventas)
    result = top_productos(validos)
    
    assert result["producto"].tolist() == ["A", "B"]
    assert result["importe"].tolist() == [30.0, 15.0]


def test_clientes_recurrentes(ventas):
    validos, _ = validar_ventas(ventas)
    
    assert clientes_recurrentes(validos).to_dict() == {"C1": 2}
