"""Показывает модели, доступные вашему ключу Perplexity API.

Запуск: python list_models.py
"""

from dotenv import load_dotenv

from perplexity_client import PerplexityClient
import os

load_dotenv()

api_key = os.getenv("PPLX_API_KEY", "")
if not api_key:
    raise SystemExit("❌ Сначала задайте PPLX_API_KEY в файле .env")

models = PerplexityClient(api_key=api_key, model="placeholder").list_models()
print("Модели, доступные вашему ключу:")
for model_id in models:
    print(f"  • {model_id}")
print("\nВпишите нужную в .env в переменную MODEL.")
