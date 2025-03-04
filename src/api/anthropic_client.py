import anthropic
from typing import Optional
from ..config import config
from .text_utils import truncate_text

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
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def process_document(self, document: str) -> tuple[str, int]:
        """Process a document through the Anthropic API"""
        if not self.client:
            raise ValueError("API key not set")

        try:
            # Apply text truncation based on configuration
            truncated_document = truncate_text(document)
            
            # Add a note if truncation was applied
            truncation_note = ""
            if truncated_document != document:
                if config.truncation_mode == "characters":
                    truncation_note = f"[Note: Input was truncated to the first {config.truncation_character_limit} characters to reduce token usage]"
                elif config.truncation_mode == "paragraphs":
                    truncation_note = f"[Note: Input was truncated to the first {config.truncation_paragraph_limit} paragraphs to reduce token usage]"
            
            print(f"Sending request to Claude with model: {config.selected_model}")
            print(f"Document length: {len(truncated_document)} characters")
            print(f"Document preview: {truncated_document[:100]}...")
            print(f"System prompt: {config.system_prompt}")
            
            # Ensure document is not empty
            if not truncated_document.strip():
                print("WARNING: Empty document after truncation!")
                truncated_document = "Please provide analysis for this document."
            
            message = await self.client.messages.create(
                model=config.selected_model,
                max_tokens=config.max_completion_tokens,
                messages=[
                    {"role": "user", "content": truncated_document}
                ],
                system=config.system_prompt
            )
            print("Claude response received successfully")
            print(f"Raw response type: {type(message)}")
            print(f"Raw response: {message}")

            try:
                # Check if content exists and has text
                if not hasattr(message, 'content') or not message.content:
                    print("ERROR: No content in Claude response")
                    return "No content was returned from Claude. Please check your API configuration.", 0
                
                if not message.content[0].text:
                    print("ERROR: Empty text in Claude response content")
                    return "Empty response from Claude. Please check your API configuration.", 0
                
                response_text = message.content[0].text
                print(f"Response text length: {len(response_text)}")
                print(f"Response text preview: {response_text[:100]}...")
                
                # Add truncation note to response if applicable
                if truncation_note:
                    response_text = f"{response_text}\n\n{truncation_note}"
                
                # Ensure we have a valid token count
                if not hasattr(message, 'usage'):
                    print("WARNING: No usage information in Claude response")
                    token_count = len(truncated_document.split()) + len(response_text.split())  # Rough estimate
                else:
                    token_count = message.usage.input_tokens + message.usage.output_tokens
                    print(f"Token count: {token_count} (input: {message.usage.input_tokens}, output: {message.usage.output_tokens})")
                
                return response_text, token_count
            except (AttributeError, IndexError) as e:
                print(f"Error parsing Claude response: {str(e)}")
                print(f"Raw response: {message}")
                # Return a fallback response instead of raising an exception
                return f"Error parsing Claude response: {str(e)}\n\nPlease check your API configuration.", 0

        except anthropic.RateLimitError as e:
            print(f"Claude rate limit exceeded: {str(e)}")
            return f"Rate limit exceeded: {str(e)}\n\nPlease try again later.", 0
        except anthropic.APIError as e:
            print(f"Claude API error: {str(e)}")
            return f"API Error: {str(e)}\n\nPlease check your API configuration.", 0
        except anthropic.APIConnectionError as e:
            print(f"Claude connection error: {str(e)}")
            return f"Connection Error: {str(e)}\n\nPlease check your internet connection.", 0
        except Exception as e:
            print(f"Unexpected error with Claude API: {str(e)}")
            import traceback
            traceback.print_exc()
            return f"Unexpected error: {str(e)}\n\nPlease check the logs for more details.", 0

    def get_rate_limits(self, model: str) -> dict:
        """Get rate limits for a specific model"""
        return self.rate_limits.get(model, {
            "requests_per_minute": 4000,
            "input_tokens_per_minute": 200000,
            "output_tokens_per_minute": 80000
        })

# Global client instance
anthropic_client = AnthropicClient() 