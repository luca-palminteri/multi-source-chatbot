"""Lazy provider factories; importing retrieval never performs API calls."""
import os

from .config import Settings
from .debug import logger


_CHAT_LIMITERS = {}


def _chat_limiter(settings):
    from langchain_core.rate_limiters import InMemoryRateLimiter

    rpm = getattr(settings, "chat_requests_per_minute", 10)
    if rpm <= 0:
        raise ValueError("CHAT_REQUESTS_PER_MINUTE must be positive")
    identity = (settings.chat_model, rpm)
    if identity not in _CHAT_LIMITERS:
        _CHAT_LIMITERS[identity] = InMemoryRateLimiter(
            requests_per_second=rpm / 60, check_every_n_seconds=0.1, max_bucket_size=1)
    return _CHAT_LIMITERS[identity]


def _google_api_key(settings: Settings):
    from dotenv import dotenv_values

    key = os.environ.get("GOOGLE_API_KEY") or dotenv_values(settings.root / ".env").get("GOOGLE_API_KEY")
    if not key:
        raise ValueError("Set GOOGLE_API_KEY before model calls, ingestion, or document search")
    return key


def embedding_provider(settings: Settings):
    if settings.embedding_provider != "google":
        raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")
    key = _google_api_key(settings)
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return GoogleGenerativeAIEmbeddings(model=settings.embedding_model, google_api_key=key,
                                       vertexai=False)


def chat_provider(settings: Settings):
    if settings.chat_provider != "google":
        raise ValueError(f"Unsupported chat provider: {settings.chat_provider}")
    key = _google_api_key(settings)
    from langchain_google_genai import ChatGoogleGenerativeAI

    options = {"timeout": getattr(settings, "chat_request_timeout", 45),
               "max_retries": getattr(settings, "chat_max_retries", 0)}
    if settings.chat_model.startswith("gemini-3"):
        options["thinking_level"] = getattr(settings, "chat_thinking_level", "low")
    logger.debug("Gemini chat configuration: model=%s; options=%s", settings.chat_model, options)
    return ChatGoogleGenerativeAI(model=settings.chat_model, google_api_key=key,
                                 vertexai=False, rate_limiter=_chat_limiter(settings), **options)
