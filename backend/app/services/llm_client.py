import os
import json
import re
from typing import Dict, Any, Optional, Type, TypeVar
from pydantic import BaseModel
from app.core.config import settings

T = TypeVar("T", bound=BaseModel)

class LLMClient:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
        self.model_name = settings.GEMINI_MODEL or "gemini-1.5-flash"
        self._gemini_client = None
        self._init_gemini()

    def _init_gemini(self):
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                # Try preferred model, fallback to gemini-1.5-flash or gemini-pro
                target_model = self.model_name
                if "gemini-2.0" in target_model:
                    target_model = "gemini-1.5-flash"
                self._gemini_client = genai.GenerativeModel(
                    model_name=target_model,
                    generation_config={
                        "temperature": 0.3,
                        "response_mime_type": "application/json"
                    }
                )
            except Exception as e:
                print(f"[LLMClient] Warning: Failed to initialize Google GenAI SDK: {e}")
                self._gemini_client = None

    def _clean_json_str(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def generate_structured(self, prompt: str, system_instruction: str, schema_class: Type[T]) -> Optional[T]:
        """
        Executes prompt against Gemini Flash with structured JSON enforcement,
        falling back to None if unavailable.
        """
        if not self._gemini_client:
            return None

        try:
            full_prompt = f"SYSTEM INSTRUCTION:\n{system_instruction}\n\nUSER PROMPT:\n{prompt}\n\nStrictly return ONLY a valid JSON object conforming to the required schema."
            response = self._gemini_client.generate_content(full_prompt)
            if response and response.text:
                cleaned = self._clean_json_str(response.text)
                data = json.loads(cleaned)
                return schema_class(**data)
        except Exception as e:
            print(f"[LLMClient] Gemini call error: {e}. Falling back to deterministic engine.")
            return None

llm_client = LLMClient()
