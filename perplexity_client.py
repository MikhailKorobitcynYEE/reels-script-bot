"""Клиент Perplexity Agent API.

Документация: https://docs.perplexity.ai/docs/agent-api/quickstart
Endpoint: POST https://api.perplexity.ai/v1/agent
"""

from __future__ import annotations

import httpx

API_URL = "https://api.perplexity.ai/v1/agent"
MODELS_URL = "https://api.perplexity.ai/v1/models"
DEFAULT_TIMEOUT = httpx.Timeout(300.0, connect=15.0)


class PerplexityError(Exception):
    """Ошибка обращения к Perplexity API с человекочитаемым пояснением."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _friendly_http_error(status_code: int, detail: str) -> str:
    detail = (detail or "").strip()
    if status_code in (401, 403):
        return (
            "Perplexity API отклонил ключ (ошибка "
            f"{status_code}). Проверьте PPLX_API_KEY в файле .env — "
            "ключ должен начинаться с pplx- и быть активным."
        )
    if status_code == 404:
        return (
            f"Модель не найдена (ошибка 404). Проверьте MODEL в файле .env. {detail}"
        )
    if status_code == 429:
        return (
            "Слишком много запросов к Perplexity API (ошибка 429). "
            "Подождите минуту и попробуйте снова."
        )
    if status_code >= 500:
        return (
            f"Perplexity API временно недоступен (ошибка {status_code}). "
            "Попробуйте ещё раз через пару минут."
        )
    return f"Ошибка Perplexity API ({status_code}): {detail}"


class PerplexityClient:
    """Синхронный клиент; вызывать из бота через asyncio.to_thread()."""

    def __init__(
        self,
        api_key: str,
        model: str = "anthropic/claude-sonnet-5",
        max_output_tokens: int = 8000,
        temperature: float | None = None,
        enable_web_search: bool = True,
        max_steps: int = 3,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature
        self.enable_web_search = enable_web_search
        self.max_steps = max_steps

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        """Отправляет диалог (system prompt + история) и возвращает текст ответа.

        messages: список {"role": "user" | "assistant", "content": "..."}
        """
        payload = {
            "model": self.model,
            "instructions": system_prompt,
            "input": [
                {"type": "message", "role": m["role"], "content": m["content"]}
                for m in messages
            ],
            "max_output_tokens": self.max_output_tokens,
            "language_preference": "ru",
        }
        # temperature поддерживается не всеми моделями (Anthropic через
        # этот API возвращает 400), поэтому отправляем его только если задано.
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.enable_web_search:
            # Веб-поиск — чтобы советы про тренды и алгоритмы Instagram
            # были актуальными, а не выдуманными моделью.
            payload["tools"] = [{"type": "web_search"}]
            payload["max_steps"] = self.max_steps
            payload["instructions"] = (
                system_prompt
                + "\n\nУ тебя есть доступ к веб-поиску. Используй его, когда нужны "
                "актуальные данные: тренды, алгоритмы и фишки Instagram, свежие "
                "форматы, статистика. Не выдумывай факты — если что-то не знаешь, "
                "проверь поиском."
            )
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
                response = client.post(API_URL, headers=self._headers(), json=payload)
        except httpx.TimeoutException as exc:
            raise PerplexityError(
                "Модель думала слишком долго и запрос оборвался по таймауту. "
                "Попробуйте ещё раз — обычно со второго раза отвечает быстрее."
            ) from exc
        except httpx.HTTPError as exc:
            raise PerplexityError(
                "Не удалось связаться с Perplexity API. Проверьте интернет-соединение "
                "и попробуйте ещё раз."
            ) from exc

        if response.status_code != 200:
            detail = ""
            try:
                detail = response.json().get("error", {}).get("message", "")
            except Exception:
                detail = response.text[:300]
            raise PerplexityError(
                _friendly_http_error(response.status_code, detail),
                status_code=response.status_code,
            )

        data = response.json()

        if data.get("status") == "failed":
            err = data.get("error") or {}
            raise PerplexityError(
                f"Модель не справилась с запросом: {err.get('message', 'неизвестная причина')}"
            )

        # Собираем текст из всех сообщений ассистента
        parts: list[str] = []
        for item in data.get("output", []):
            if item.get("type") != "message":
                continue
            for chunk in item.get("content", []):
                if chunk.get("type") == "output_text":
                    parts.append(chunk.get("text", ""))

        text = "".join(parts).strip()
        if not text:
            raise PerplexityError(
                "Perplexity API вернул пустой ответ. Попробуйте отправить запрос ещё раз."
            )
        return text

    def list_models(self) -> list[str]:
        """Возвращает список доступных моделей аккаунта."""
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(MODELS_URL, headers=self._headers())
        except httpx.HTTPError as exc:
            raise PerplexityError("Не удалось получить список моделей.") from exc
        if response.status_code != 200:
            raise PerplexityError(
                _friendly_http_error(response.status_code, ""),
                status_code=response.status_code,
            )
        data = response.json()
        return [m.get("id", "") for m in data.get("data", []) if m.get("id")]
