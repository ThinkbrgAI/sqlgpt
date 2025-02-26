from typing import Optional
import aiohttp
import json
import tiktoken
from ..config import config

class OpenAIClient:
    def __init__(self):
        self.api_key: Optional[str] = None
        self.base_url = "https://api.openai.com/v1/chat/completions"

    def set_api_key(self, api_key: str):
        self.api_key = api_key

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken"""
        enc = tiktoken.encoding_for_model("gpt-4")  # Use gpt-4 encoding for o1/o3-mini
        return len(enc.encode(text))

    async def process_document(self, document: str) -> tuple[str, int]:
        """Process a document through the OpenAI API"""
        if not self.api_key:
            raise ValueError("API key not set")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        data = {
            "model": config.selected_model,
            "messages": [
                {"role": "system", "content": config.system_prompt},
                {"role": "user", "content": document}
            ],
            "max_completion_tokens": config.max_completion_tokens,
            "reasoning_effort": config.reasoning_effort
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url, headers=headers, json=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"API Error: {error_text}")
                
                result = await response.json()
                response_text = result["choices"][0]["message"]["content"]
                
                # Get total tokens including reasoning tokens
                usage = result["usage"]
                total_tokens = usage["total_tokens"]
                reasoning_tokens = usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
                
                return response_text, total_tokens

# Global client instance
openai_client = OpenAIClient() 