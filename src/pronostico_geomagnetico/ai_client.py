import os
from dataclasses import dataclass

from dotenv import load_dotenv
from huggingface_hub import InferenceClient


@dataclass
class AIResponse:
    provider: str
    text: str


def complete(provider: str, prompt: str) -> AIResponse:
    if provider == "mock":
        return AIResponse(provider="mock", text=f"[mock] Recibido: {prompt}")

    if provider == "hf":
        load_dotenv()
        token = os.getenv("HF_TOKEN")
        if not token:
            raise RuntimeError("Falta HF_TOKEN en el archivo .env o en el entorno.")

        client = InferenceClient(api_key=token, provider="auto")
        result = client.chat_completion(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
        )
        texto = result.choices[0].message.content
        if not texto:
            raise RuntimeError("Hugging Face devolvió un resumen vacío.")

        return AIResponse(provider="hf", text=texto)

    raise ValueError(f"Proveedor no soportado: {provider}")