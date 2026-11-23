from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest

from src.pronostico_geomagnetico.fuentes import MAG, observar_kp, revisar_viento


AHORA = pd.Timestamp("2026-11-23T23:58:18Z")


def filas_noaa(ahora=AHORA):
    fechas = pd.date_range(ahora.floor("min") - pd.Timedelta(hours=3), periods=180, freq="min")
    comun = [{"time_tag": fecha.strftime("%Y-%m-%dT%H:%M:%S"), "source": "SOLAR1",
              "active": True, "overall_quality": 0} for fecha in fechas]
    mag = [fila | {"bz_gsm": -3.0, "sample_size": 60} for fila in comun]
    plasma = [fila | {"proton_density": 4.2, "proton_speed": 430, "proton_sample_size": 1} for fila in comun]
    return mag, plasma


def revisar(mag, plasma, reloj=lambda: AHORA):
    return revisar_viento(lambda url: mag if url == MAG else plasma, reloj)


def test_datos_recientes_noaa_diagnostico_independiente():
    mag, plasma = filas_noaa()
    mag += [mag[0].copy(), mag[-1] | {"active": False, "source": "ACE"}]
    resultado = revisar(mag, plasma)

    assert resultado["estado"] == "datos_validos"
    assert resultado["motivo"] is None
    assert "kp_previsto" not in resultado
    assert resultado["minutos_validos"] == 180
    assert resultado["satelites"] == ["SOLAR1"]
    assert resultado["antiguedad_segundos"] == 78


def test_recepcion_antes_de_decision_y_exclusion_del_minuto_abierto():
    mag, plasma = filas_noaa()
    mag.append(mag[-1] | {"time_tag": "2026-11-23T23:58:00"})
    plasma.append(plasma[-1] | {"time_tag": "2026-11-23T23:58:00"})
    mag.append(mag[-1] | {"time_tag": "2026-11-24T00:01:00"})
    plasma.append(plasma[-1] | {"time_tag": "2026-11-24T00:01:00"})
    tiempos = iter([AHORA, AHORA + pd.Timedelta(seconds=1), AHORA + pd.Timedelta(minutes=2)])
    resultado = revisar(mag, plasma, lambda: next(tiempos))
    assert resultado["ultimo_dato"] == "2026-11-23T23:57:00+00:00"
    assert resultado["recepcion_mag"] < resultado["recepcion_plasma"] < resultado["consulta"]


@pytest.mark.parametrize("cambios", [
    {"source": "ACE"}, {"proton_density": None}, {"overall_quality": 2},
    {"max_data_flag": 1}, {"proton_speed": float("inf")},
])
def test_minutos_incompatibles_o_malos_reducen_cobertura(cambios):
    mag, plasma = filas_noaa()
    plasma[8].update(cambios)
    resultado = revisar(mag, plasma)
    assert resultado["motivo"] == "datos_incompletos"
    assert resultado["minutos_validos"] == 179


def test_conflictos_entre_duplicados_y_naves_activas():
    mag, plasma = filas_noaa()
    mag.append(mag[0] | {"bz_gsm": -4.0})
    mag.append(mag[1] | {"source": "ACE"})
    resultado = revisar(mag, plasma)
    assert resultado["minutos_validos"] == 178


def test_mediciones_caducadas():
    mag, plasma = filas_noaa(AHORA - pd.Timedelta(minutes=30))
    resultado = revisar(mag, plasma)
    assert resultado["motivo"] == "datos_caducados"
    assert resultado["antiguedad_segundos"] > 1800


def test_gfz_devuelve_solo_el_bloque_cerrado_y_su_calidad():
    inicio = pd.Timestamp("2026-11-23T18:00Z")

    def descargar(url):
        args = parse_qs(urlparse(url).query)
        assert args["start"] == args["end"] == ["2026-11-23T18:00:00Z"]
        return {"datetime": ["2026-11-23T15:00:00Z", "2026-11-23T18:00:00Z"],
                "Kp": [4.333, 1.667], "status": ["def", "pre"]}

    resultado = observar_kp(inicio, descargar, lambda: AHORA)
    assert resultado["kp_observado"] == 1.667
    assert resultado["calidad"] == "pre"


def test_gfz_sin_observacion_valida():
    inicio = pd.Timestamp("2026-11-23T18:00Z")
    resultado = observar_kp(inicio, lambda _: {"datetime": [], "Kp": [], "status": []}, lambda: AHORA)
    assert resultado["estado"] == "observacion_pendiente"
    assert "kp_observado" not in resultado
