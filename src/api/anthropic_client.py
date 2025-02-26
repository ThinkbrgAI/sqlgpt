import anthropic
from typing import Optional
from ..config import config

class AnthropicClient:
    def __init__(self):
        self.api_key: Optional[str] = None
        self.client = None
        self.rate_limits = {
            "claude-3-7-sonnet-20250219": {
                "requests_per_minute": 4000,
                "input_tokens_per_minute": 200000,
                "output_tokens_per_minute": 80000
            }
        }

    def set_api_key(self, api_key: str):
        self.api_key = api_key
        self.client = anthropic.Anthropic(api_key=api_key)

    async def process_document(self, document: str) -> tuple[str, int]:
        """Process a document through the Anthropic API"""
        if not self.client:
            raise ValueError("API key not set")

        try:
            message = self.client.messages.create(
                model=config.selected_model,
                max_tokens=config.max_tokens,
                messages=[
                    {"role": "user", "content": document}
                ],
                system=config.system_prompt
            )

            response_text = message.content[0].text
            # Anthropic provides usage in the response
            token_count = message.usage.input_tokens + message.usage.output_tokens
            
            return response_text, token_count

        except anthropic.RateLimitError as e:
            raise Exception(f"Rate limit exceeded: {str(e)}")
        except Exception as e:
            raise Exception(f"API Error: {str(e)}")

    def get_rate_limits(self, model: str) -> dict:
        """Get rate limits for a specific model"""
        return self.rate_limits.get(model, {
            "requests_per_minute": 4000,
            "input_tokens_per_minute": 200000,
            "output_tokens_per_minute": 80000
        })

# Global client instance
anthropic_client = AnthropicClient() 