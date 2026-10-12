import pandas as pd
import pytest


@pytest.fixture
def ventas():
    """Ventas pequenas en memoria con resultados conocidos."""
    return pd.DataFrame({
        "fecha": ["2026-01-01"] * 3,
        "region": ["Norte", "Sur", "Norte"],
        "producto": ["A", "B", "A"],
        "unidades": [2, 3, 1],
        "precio_unitario": [10.0, 5.0, 10.0],
        "cliente_id": ["C1", "C2", "C1"],
    })
