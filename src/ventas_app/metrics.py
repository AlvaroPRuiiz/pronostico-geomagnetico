import pandas as pd

TOP_PRODUCTS = 3


def importe_por_region(validos: pd.DataFrame) -> pd.DataFrame:
    """Suma importes por region en orden descendente."""
    return (
        validos.groupby("region", as_index=False)["importe"].sum().sort_values("importe", ascending=False)
    )


def top_productos(validos: pd.DataFrame) -> pd.DataFrame:
    """Devuelve los tres productos con mayor importe."""
    return (
        validos.groupby("producto", as_index=False)["importe"].sum().sort_values("importe", ascending=False).head(TOP_PRODUCTS)
    )


def clientes_recurrentes(validos: pd.DataFrame) -> pd.Series:
    """Cuenta compras de clientes con mas de una compra."""
    compras_por_cliente = validos["cliente_id"].value_counts()

    return compras_por_cliente[compras_por_cliente > 1]