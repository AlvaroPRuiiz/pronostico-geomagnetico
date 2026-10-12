from pathlib import Path

import pytest


from src.pronostico_geomagnetico.exceptions import OmniLoadError
from src.pronostico_geomagnetico.loader import load_omni




def test_load_omni_archivo_inexistente(tmp_path):
    """Comprueba que un archivo inexistente provoca OmniLoadError."""

    path = tmp_path / "no_existe.dat"

    with pytest.raises(OmniLoadError, match="No existe el archivo"):
        load_omni(path)
        
def test_load_omni_archivo_vacio(tmp_path):
    """Comprueba que un archivo vacío provoca OmniLoadError."""
    
    path = tmp_path / "vacio.dat"
    path.touch()

    with pytest.raises(OmniLoadError, match="El archivo está vacío"):
        load_omni(path)

@pytest.mark.parametrize("numero_columnas", [1, 3, 54, 56]) #Para ejecutar 4 veces el mismo test con diferentes datos
def test_load_omni_columnas_incorrectas(tmp_path, numero_columnas):
    """Comprueba que el loader rechaza archivos que no tienen 55 columnas."""
    
    path = tmp_path / "columnas_incorrectas.dat"
    contenido = " ".join(["0"] * numero_columnas) + "\n"
    path.write_text(contenido, encoding="utf-8")

    with pytest.raises(OmniLoadError, match="Se esperaban 55 columnas"):
        load_omni(path)
        
def test_load_omni_archivo_correcto(tmp_path):
    """Comprueba que el loader carga una fila con 55 columnas."""
    
    path = tmp_path / "correcto.dat"
    
    valores = ["0"] * 55
    contenido = " ".join(valores) + "\n"
    path.write_text(contenido, encoding="utf-8")

    df = load_omni(path)

    assert df.shape == (1, 55)
    assert df.loc[0, "year"] == 0