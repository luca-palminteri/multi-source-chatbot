import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import ANY, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from assistant.config import Settings
from assistant.providers import chat_provider, embedding_provider, _chat_limiter
from assistant.messages import message_text


class ProviderTests(unittest.TestCase):
    def test_google_defaults_and_environment_key_precedence(self):
        dotenv = SimpleNamespace(dotenv_values=Mock(return_value={"GOOGLE_API_KEY": "file-key"}))
        google = SimpleNamespace(ChatGoogleGenerativeAI=Mock(), GoogleGenerativeAIEmbeddings=Mock())
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "environment-key"}, clear=True), patch.dict(
                sys.modules, {"dotenv": dotenv, "langchain_google_genai": google}):
            settings = Settings.load()
            self.assertEqual(settings.chat_provider, "google")
            self.assertEqual(settings.embedding_provider, "google")
            chat_provider(settings)
            embedding_provider(settings)
            for factory, model in [(google.ChatGoogleGenerativeAI, settings.chat_model),
                                   (google.GoogleGenerativeAIEmbeddings, settings.embedding_model)]:
                options = {"timeout": 45, "max_retries": 0, "thinking_level": "low"} if factory is google.ChatGoogleGenerativeAI else {}
                factory.assert_called_once_with(model=model, google_api_key="environment-key", vertexai=False, **({"rate_limiter": ANY} if options else {}), **options)

    def test_agent_and_pipeline_share_request_pacing(self):
        settings = SimpleNamespace(chat_model="limiter-test-model", chat_requests_per_minute=10)
        self.assertIs(_chat_limiter(settings), _chat_limiter(settings))
        with self.assertRaisesRegex(ValueError, "must be positive"):
            _chat_limiter(SimpleNamespace(chat_model="test", chat_requests_per_minute=0))

    def test_file_key_and_missing_key(self):
        settings = SimpleNamespace(root=Path("."), chat_provider="google", chat_model="test-model")
        dotenv = SimpleNamespace(dotenv_values=Mock(return_value={"GOOGLE_API_KEY": "file-key"}))
        google = SimpleNamespace(ChatGoogleGenerativeAI=Mock())
        with patch.dict(os.environ, {}, clear=True), patch.dict(
                sys.modules, {"dotenv": dotenv, "langchain_google_genai": google}):
            chat_provider(settings)
            google.ChatGoogleGenerativeAI.assert_called_once_with(
                model="test-model", google_api_key="file-key", vertexai=False, timeout=45, max_retries=0, rate_limiter=ANY)
            dotenv.dotenv_values.return_value = {}
            with self.assertRaisesRegex(ValueError, "GOOGLE_API_KEY"):
                chat_provider(settings)

    def test_gemini_text_blocks_exclude_thoughts(self):
        message = SimpleNamespace(content=[{"type": "text", "text": "private", "thought": True},
                                           {"type": "text", "text": "Answer [D1]"},
                                           {"type": "image", "text": "ignored"}])
        self.assertEqual(message_text(message), "Answer [D1]")
        self.assertEqual(message_text(SimpleNamespace(content="plain text")), "plain text")
