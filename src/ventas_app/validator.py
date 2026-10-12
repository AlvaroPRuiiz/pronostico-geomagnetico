import pandas as pd


class ValidationError(Exception):
    """Datos que no cumplen las reglas de validación."""
    
def validar_ventas(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa filas invalidas y calcula el importe de las validas."""
    required = {"region", "producto", "unidades", "precio_unitario", "cliente_id"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValidationError(f"Faltan columnas: {', '.join(sorted(missing))}")
    work = frame.copy()

    work["unidades"] = pd.to_numeric(work["unidades"], errors="coerce")
    work["precio_unitario"] = pd.to_numeric(work["precio_unitario"], errors="coerce")

    ok = (
        work["unidades"].notna()
        & (work["unidades"] > 0)
        & work["precio_unitario"].notna()
        & (work["precio_unitario"] > 0)
    )

    validos = work.loc[ok].copy()
    errores = work.loc[~ok].copy()
    
    validos["importe"] = validos["unidades"] * validos["precio_unitario"]
   
    return validos, errores


