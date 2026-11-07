from src.pronostico_geomagnetico.ai_client import complete


def test_complete_mock_devuelve_el_prompt():
    prompt = "Resume el pronóstico de Kp para el bloque 00:00–03:00 UTC."

    respuesta = complete("mock", prompt)

    assert respuesta.provider == "mock"
    assert respuesta.text == f"[mock] Recibido: {prompt}"