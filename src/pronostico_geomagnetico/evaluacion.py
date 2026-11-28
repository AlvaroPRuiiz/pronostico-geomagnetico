"""Entrena el modelo operativo y genera la evaluación retrospectiva reproducible."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import confusion_matrix, mean_absolute_error, r2_score, root_mean_squared_error

from .features import BLOQUE, ENTRADAS_MODELO, construir_dataset
from .loader import load_omni
from .operativo import COLUMNAS_KP, METODO_KP, PERSISTENCIA, matriz_kp
from .preprocessor import preprocess_omni
from .validator import validate_omni

ARCHIVO_GFZ = "https://datapub.gfz.de/download/10.5880.Kp.0001"
GFZ_DIRECCIONES = {"now": "Kp_nowcast", "def": "Kp_definitive"}
AJUSTE = ("2021-01-01", "2023-01-01")
VALIDACION = ("2023-01-01", "2024-01-01")
EVALUACION = ("2026-01-01", "2026-10-01")
PROYECTO_II = ("2024-01-01", "2026-01-01")
UMBRAL = 5.0


def bloques(periodo):
    return pd.date_range(*periodo, freq=BLOQUE, tz="UTC", inclusive="left")


def leer_wdc(texto: str, anio: int) -> pd.Series:
    """Lee los ocho Kp de las columnas 13–28 del WDC oficial."""
    valores = {}
    fracciones = {0: 0.0, 3: 1 / 3, 7: 2 / 3}
    for fila in texto.splitlines():
        if not fila or fila.startswith("#"):
            continue
        if len(fila) < 28 or int(fila[:2]) != anio % 100:
            raise ValueError(f"Fecha o longitud inválida en WDC {anio}.")
        dia = pd.Timestamp(year=anio, month=int(fila[2:4]), day=int(fila[4:6]), tz="UTC")
        for indice, columna in enumerate(range(12, 28, 2)):
            fecha = dia + indice * BLOQUE
            if fecha in valores:
                raise ValueError(f"Bloque WDC duplicado: {fecha}.")
            codigo = int(fila[columna:columna + 2])
            entero, fraccion = divmod(codigo, 10)
            if codigo == -1:
                valores[fecha] = float("nan")
            elif 0 <= codigo <= 90 and fraccion in fracciones:
                valores[fecha] = round(entero + fracciones[fraccion], 3)
            else:
                raise ValueError(f"Código Kp WDC inválido: {codigo}.")
    if not valores:
        raise ValueError(f"Archivo WDC vacío para {anio}.")
    return pd.Series(valores, dtype=float).sort_index()


def archivo_gfz(carpeta, tipo, anio, descargar):
    nombre = f"Kp_{tipo}{anio}.wdc"
    ruta = carpeta / nombre
    if not ruta.exists() and descargar:
        url = f"{ARCHIVO_GFZ}/{GFZ_DIRECCIONES[tipo]}/{nombre}"
        with urlopen(url, timeout=20) as respuesta:
            contenido = respuesta.read()
        leer_wdc(contenido.decode("ascii"), anio)
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(contenido)
        print(f"Descargado {url}", flush=True)
    contenido = ruta.read_bytes()
    return leer_wdc(contenido.decode("ascii"), anio), hashlib.sha256(contenido).hexdigest()


def metricas(observado, previsto) -> dict:
    y, p = pd.Series(observado).reset_index(drop=True), pd.Series(previsto).reset_index(drop=True)
    tormenta = y >= UMBRAL
    vn, fp, fn, vp = map(int, confusion_matrix(tormenta, p >= UMBRAL, labels=[False, True]).ravel())
    return {
        "mae": float(mean_absolute_error(y, p)),
        "rmse": float(root_mean_squared_error(y, p)),
        "r2": float(r2_score(y, p)) if y.nunique() > 1 else None,
        "mae_tormentas": float(mean_absolute_error(y[tormenta], p[tormenta])) if vp + fn else None,
        "tormentas": vp + fn, "precision": vp / (vp + fp) if vp + fp else 0.0,
        "recall": vp / (vp + fn) if vp + fn else 0.0,
        "f1": 2 * vp / (2 * vp + fp + fn) if 2 * vp + fp + fn else 0.0,
        "matriz": [[vn, fp], [fn, vp]],
    }


def resumen_comparacion(serie: pd.DataFrame, esperados: int) -> dict:
    """Mide ambos métodos solo sobre la intersección de bloques disponibles."""
    comun = serie[["kp_observado", "kp_previsto", "kp_persistencia"]].dropna()
    resultado = {"bloques": len(comun), "esperados": esperados,
                 "cobertura": len(comun) / esperados if esperados else None}
    if not comun.empty:
        y = comun["kp_observado"]
        resultado["modelo"] = metricas(y, comun["kp_previsto"])
        resultado["persistencia"] = metricas(y, comun["kp_persistencia"])
    return resultado


def evaluar_periodo(periodo, nowcast, definitivo, modelo):
    objetivos = bloques(periodo)
    X = matriz_kp(nowcast, objetivos)
    validas = X.dropna()
    previsto = pd.Series(modelo.predict(validas) if len(validas) else [], index=validas.index, dtype=float)
    return pd.DataFrame({
        "kp_observado": definitivo.reindex(objetivos),
        "kp_previsto": previsto,
        "kp_persistencia": X[PERSISTENCIA].where(X.notna().all(axis=1)),
    }, index=objetivos)


def evaluar_omni(carpeta, ruta_modelo):
    datos = pd.concat([load_omni(carpeta / f"omni2_{anio}.dat")
                       for anio in (2023, 2024, 2025)], ignore_index=True)
    validate_omni(datos)
    dataset = construir_dataset(preprocess_omni(datos), exigir_objetivo=False)
    objetivos = bloques(PROYECTO_II)
    X = dataset.reindex(objetivos)[ENTRADAS_MODELO].dropna()
    modelo = joblib.load(ruta_modelo)
    observado = dataset["kp_objetivo"]
    previsto = pd.Series(modelo.predict(X) if len(X) else [], index=X.index, dtype=float)
    return pd.DataFrame({
        "kp_observado": observado.reindex(objetivos),
        "kp_previsto": previsto,
        "kp_persistencia": observado.reindex(objetivos - 2 * BLOQUE).to_numpy(),
    }, index=objetivos)


def generar(carpeta, salida, carpeta_omni, modelo_omni, descargar):
    series, huellas = {}, {}
    for tipo, anios in (("now", (2020, 2021, 2022, 2023, 2025, 2026)),
                       ("def", (2021, 2022, 2023, 2026))):
        trozos = []
        for anio in anios:
            datos, hash_archivo = archivo_gfz(carpeta, tipo, anio, descargar)
            trozos.append(datos)
            huellas[f"Kp_{tipo}{anio}.wdc"] = hash_archivo
        series[tipo] = pd.concat(trozos)

    nowcast, definitivo = series["now"], series["def"]
    fechas_ajuste = bloques(AJUSTE)
    ajuste = matriz_kp(nowcast, fechas_ajuste).assign(kp=definitivo.reindex(fechas_ajuste)).dropna()
    modelo = HistGradientBoostingRegressor(early_stopping=False, random_state=42)
    modelo.fit(ajuste[COLUMNAS_KP], ajuste["kp"])

    periodos = [
        ("validacion", "Validación GFZ 2023", VALIDACION, evaluar_periodo(VALIDACION, nowcast, definitivo, modelo)),
        ("gfz2026", "Evaluación GFZ 2026", EVALUACION, evaluar_periodo(EVALUACION, nowcast, definitivo, modelo)),
    ]
    if modelo_omni.is_file():
        periodos.append(("omni", "Proyecto II · OMNI 2024–2025", PROYECTO_II,
                         evaluar_omni(carpeta_omni, modelo_omni)))

    salida.mkdir(parents=True, exist_ok=True)
    ruta_modelo = salida / "modelo_operativo.joblib"
    joblib.dump(modelo, ruta_modelo)
    informe = {
        "metodo": METODO_KP, "umbral_tormenta": UMBRAL,
        "ajuste": {"inicio": AJUSTE[0], "fin_exclusivo": AJUSTE[1],
                   "bloques": len(ajuste), "esperados": len(fechas_ajuste)},
        "modelo_sha256": hashlib.sha256(ruta_modelo.read_bytes()).hexdigest(),
        "archivos_gfz_sha256": huellas, "periodos": {},
    }
    for clave, titulo, (inicio, fin), serie in periodos:
        ruta = salida / f"evaluacion_{clave}.csv"
        serie.to_csv(ruta, index_label="bloque", date_format="%Y-%m-%dT%H:%M:%SZ")
        observados = serie["kp_observado"].dropna()
        primero = pd.Timestamp(inicio, tz="UTC")
        dia_demo = max(primero, observados.idxmax().floor("D") - pd.Timedelta(days=2)) if len(observados) else primero
        informe["periodos"][clave] = {
            "titulo": titulo, "inicio": inicio, "fin_exclusivo": fin, "dia_demo": str(dia_demo.date()),
            **resumen_comparacion(serie, len(serie)),
        }
    (salida / "evaluacion.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    return informe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--descargar", action="store_true", help="Descarga archivos GFZ que falten.")
    parser.add_argument("--gfz-dir", type=Path, default=Path("data/raw/gfz"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--omni-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--omni-model", type=Path, default=Path("data/processed/modelo_kp.joblib"))
    args = parser.parse_args()
    informe = generar(args.gfz_dir, args.output_dir, args.omni_dir, args.omni_model, args.descargar)
    for periodo in informe["periodos"].values():
        print(f"{periodo['titulo']}: {periodo['bloques']}/{periodo['esperados']} bloques, "
              f"MAE modelo {periodo['modelo']['mae']:.3f}, persistencia {periodo['persistencia']['mae']:.3f}")


if __name__ == "__main__":
    main()
