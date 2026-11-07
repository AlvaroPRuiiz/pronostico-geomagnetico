# Uso de IA

- **ChatGPT:** lo usé como apoyo para diseñar el flujo de predicción de Kp,
  comparar modelos y preparar código y pruebas. Incorporé propuestas para
  la construcción de variables, la CLI y los tests. Verifiqué el entrenamiento,
  la predicción desde la terminal y la ejecución de las pruebas en local.
  
- **Hugging Face Inference Providers:** el cliente está preparado para usar
  `openai/gpt-oss-20b` mediante `chat_completion` y redactar un resumen del
  pronóstico. El Kp lo calcula el modelo local de scikit-learn. Se comprobó
  el modo `mock`; la llamada a la API real no se probó.