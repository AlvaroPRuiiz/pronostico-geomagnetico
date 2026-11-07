# Proyecto I: ventas y datos geomagnéticos

Este proyecto reúne el pipeline de ventas del curso y otro con datos de NASA OMNI. En ambos cargo y valido los datos, calculo métricas y guardo los resultados desde la terminal. Elegí OMNI por mi interés en una futura predicción de Kp; aquí trabajo con la calidad de los datos.

## Organización

El código está en `src/ventas_app/` y `src/pronostico_geomagnetico/`, y sus pruebas en `tests/ventas/` y `tests/geomagnetico/`. Los datasets se descargan en `data/` (excluida de Git) y los notebooks en `notebooks/`.

En ventas utilizo `SalesRepository` y `CsvSalesRepository`, siguiendo el ejemplo de clase. Los principios SOLID aplicados están explicados en [DESIGN.md](src/ventas_app/DESIGN.md).

## Ejecución

Desde la raíz del repositorio, con Python 3.12:

```bash
python -m pip install -r requirements.txt
python scripts/download_data.py
python -m src.ventas_app.cli --input data/ventas.csv --output data/processed/ventas_validas.csv
python -m src.pronostico_geomagnetico.cli --input data/raw/omni2_2000.dat --output data/processed/metrics_2000.json
```

Ventas genera el CSV limpio, `calidad_datos.json` con recuentos e importe total y `metricas_ventas.json` con importe por región, los tres productos con mayor importe y clientes recurrentes.

OMNI genera un JSON con total de filas, filas completas e incompletas y porcentaje de completas, considerando Bz, densidad de protones, velocidad del viento solar y Kp. Para abrir los notebooks hace falta Jupyter.

## Validación

- **Ventas:** unidades y precio numéricos y mayores que cero. Se separan las filas inválidas y se calcula el importe de las válidas. El CSV del curso tiene **140 válidas y 10 inválidas**.
- **OMNI:** 55 columnas, fecha y hora válidas, años bisiestos y ausencia de instantes duplicados. Los códigos de datos ausentes se convierten a `NaN` en las cuatro variables seleccionadas.

Ambas aplicaciones utilizan excepciones propias para los errores de carga y validación.

## Tests y CI

```bash
python -m pytest -q
python -m pytest -q -m "not integration"
python -m pytest tests --cov=src.ventas_app --cov=src.pronostico_geomagnetico --cov-report=term-missing --cov-fail-under=60
```

Las pruebas usan datos en memoria, archivos temporales y los datasets descargados. Los tests no usan red; la descarga inicial sí la necesita. El 12 de octubre de 2026 pasaron **55 tests con un 98,15 % de cobertura** en local, con Python 3.14.

El workflow `.github/workflows/ci.yml` comprueba ambas partes con Python 3.12 en pushes a `main` y pull requests, con cobertura mínima del 60 %.

[Ver Actions](https://github.com/AlvaroPRuiiz/pronostico-geomagnetico/actions) ·
![CI](https://github.com/AlvaroPRuiiz/pronostico-geomagnetico/actions/workflows/ci.yml/badge.svg)

## Datos

Ventas procede de `3_automatizacion_e_ia/Datos/ventas.csv` del repositorio del curso.

OMNI procede de NASA/GSFC SPDF: [documentación](https://omniweb.gsfc.nasa.gov/html/ow_data.html), [archivo de 2000](https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni/omni2_2000.dat) y [condiciones de citación](https://omniweb.gsfc.nasa.gov/html/citing.html). Se pide reconocer OMNIWeb y citar *OMNI Hourly Data*, DOI `10.48322/1shr-ht18`, con fecha de acceso. La licencia del código no se aplica automáticamente al dataset.

Fecha de descarga original: aproximadamente entre el 5 y el 7 de octubre de 2026.

El script descarga el archivo completo `data/raw/omni2_2000.dat`: **8784 filas y 55 columnas**, con los registros horarios del año 2000. Ocupa unos 2,9 MB y cumple el tamaño indicado en clase. Todos los datasets y resultados generados quedan excluidos de Git. El script también descarga el CSV de ventas desde una versión fija del repositorio del curso.


## Proyecto II: pronóstico geomagnético

El modelo estima el Kp del siguiente bloque de tres horas UTC. Usa las
medias de Bz, densidad de protones y velocidad del viento solar de las
tres horas previas a la emisión. El Kp del bloque pronosticado se usa
como etiqueta en entrenamiento y evaluación.

Desde la raíz del repositorio, con el entorno virtual activo:

```bash
python -m pip install -r requirements.txt
python scripts/download_data.py --omni-years 2000 2025
python -m src.pronostico_geomagnetico.train
python -m src.pronostico_geomagnetico.predict --input data/raw/omni2_2023.dat --model data/processed/modelo_kp.joblib --emision "2024-01-01 00:00" --provider mock
```

La configuración del modelo se eligió en validación (2022–2023).
El Boosting final se entrenó con 2000–2023 y se evaluó en 2024–2025.
El test comparó los tres métodos sobre 5.703 emisiones, de las cuales
249 tenían Kp observado ≥ 5.

| Método | MAE global | MAE con Kp ≥ 5 |
| --- | ---: | ---: |
| Persistencia | 0,863 | 1,551 |
| Regresión lineal | 0,745 | 1,780 |
| Gradient Boosting | 0,675 | 1,335 |

La persistencia supone un margen de tres horas tras el cierre del bloque
para disponer de su Kp. La evaluación es retrospectiva sobre OMNI.

Scikit-learn calcula el Kp. El cliente de IA recibe el resultado y el
intervalo para redactar un resumen. El modo `mock`, usado en los tests,
devuelve la instrucción recibida sin llamar a la API. El modo `hf` está
preparado para Hugging Face Inference Providers con `openai/gpt-oss-20b`;
la llamada real no se ha probado.

Los datos horarios de NASA OMNI están identificados como CC0 1.0 en su
[ficha de metadatos](https://spase-metadata.org/NASA/NumericalData/OMNI/PT1H).

En el Proyecto III, el backend reutilizará el modelo entrenado y la
función de predicción. Una interfaz web permitirá elegir una hora de
emisión UTC y consultar el Kp previsto para el siguiente bloque.