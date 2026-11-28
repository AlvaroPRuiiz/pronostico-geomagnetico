# Uso de IA

- **ChatGPT:** lo usé como apoyo para diseñar el flujo de predicción de Kp,
  comparar modelos y preparar código y pruebas. Incorporé propuestas para
  la construcción de variables, la CLI y los tests. Verifiqué el entrenamiento,
  la predicción desde la terminal y la ejecución de las pruebas en local.
  
- **Hugging Face Inference Providers:** el cliente está preparado para usar
  `openai/gpt-oss-20b` mediante `chat_completion` y redactar un resumen del
  pronóstico. El Kp lo calcula el modelo local de scikit-learn. Se comprobó
  el modo `mock`; la llamada a la API real no se probó.

## Proyecto III

- **Codex (OpenAI).** Ayudó a contrastar la documentación de NASA, NOAA y GFZ, diseñar el contrato causal con bloques GFZ cerrados, implementar el entrenamiento, la evaluación y el registro, y rediseñar la web. Las métricas se calcularon a partir de los archivos oficiales. La emisión de ejemplo se verificó en navegador con la fuente y el modelo reales. Las pruebas offline usan respuestas pequeñas para cubrir validez, caducidad, cambios de bloque y revisión de observaciones.
- **Cliente de IA en la app.** Se conserva la interfaz del Proyecto II. La web usa `mock` y rotula la respuesta como simulada. La predicción histórica se calcula en scikit-learn.
