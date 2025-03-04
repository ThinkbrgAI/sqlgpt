from typing import Optional
import aiohttp
import json
import tiktoken
from ..config import config
from .text_utils import truncate_text

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

            print(f"Sending request to OpenAI with model: {config.selected_model}")
            print(f"Document length: {len(truncated_document)} characters")
            print(f"Document preview: {truncated_document[:100]}...")
            print(f"System prompt: {config.system_prompt}")
            print(f"Force full document: {config.force_full_document}")
            
            # Ensure document is not empty
            if not truncated_document.strip():
                print("WARNING: Empty document after truncation!")
                truncated_document = "Please provide analysis for this document."
                
            # Check if document is too large and force truncation, unless force_full_document is enabled
            token_estimate = self.count_tokens(truncated_document) + self.count_tokens(config.system_prompt)
            max_allowed_tokens = 100000  # OpenAI models have a context limit
            
            if token_estimate > max_allowed_tokens and not config.force_full_document:
                print(f"WARNING: Document is too large ({token_estimate} tokens). Forcing truncation to {max_allowed_tokens} tokens.")
                # Truncate to approximately 80% of max tokens to leave room for system prompt
                max_chars = int((max_allowed_tokens * 0.8) * 4)  # Rough estimate: 1 token ≈ 4 chars
                truncated_document = truncated_document[:max_chars]
                truncation_note = f"[Note: Document was automatically truncated to fit within token limits]"
            elif token_estimate > max_allowed_tokens and config.force_full_document:
                print(f"WARNING: Document is very large ({token_estimate} tokens) and exceeds the model's context limit.")
                print(f"Attempting to process anyway because force_full_document is enabled.")
                print(f"This may result in an API error or incomplete processing.")

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }

            data = {
                "model": config.selected_model,
                "messages": [
                    {"role": "system", "content": config.system_prompt},
                    {"role": "user", "content": truncated_document}
                ],
                "max_completion_tokens": config.max_completion_tokens,  # Use the configured value directly
                "reasoning_effort": config.reasoning_effort
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=data) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"OpenAI API Error: {error_text}")
                        return f"API Error: {error_text}\n\nPlease check your API configuration.", 0
                    
                    result = await response.json()
                    print(f"OpenAI response received successfully")
                    print(f"Raw response: {result}")
                    
                    # Check if the response contains the expected fields
                    if "choices" not in result or not result["choices"]:
                        print("ERROR: No choices in OpenAI response")
                        return "No content was returned from OpenAI. Please check your API configuration.", 0
                    
                    if "message" not in result["choices"][0] or "content" not in result["choices"][0]["message"]:
                        print("ERROR: No message content in OpenAI response")
                        return "Empty response from OpenAI. Please check your API configuration.", 0
                    
                    response_text = result["choices"][0]["message"]["content"]
                    
                    # Check if response is empty or just whitespace
                    if not response_text or not response_text.strip():
                        print("ERROR: Empty response text from OpenAI")
                        finish_reason = result["choices"][0].get("finish_reason", "unknown")
                        print(f"Finish reason: {finish_reason}")
                        
                        if finish_reason == "length":
                            return "The response was cut off due to token limits. Try using a smaller input document or adjusting the token settings.", 0
                        else:
                            return "OpenAI returned an empty response. This might be due to content filtering or other API issues.", 0
                    
                    print(f"Response text length: {len(response_text)}")
                    print(f"Response text preview: {response_text[:100]}...")
                    
                    # Add truncation note to response if applicable
                    if truncation_note:
                        response_text = f"{response_text}\n\n{truncation_note}"
                    
                    # Ensure we have a valid token count
                    if "usage" not in result:
                        print("WARNING: No usage information in OpenAI response")
                        total_tokens = len(truncated_document.split()) + len(response_text.split())  # Rough estimate
                    else:
                        # Get total tokens including reasoning tokens
                        usage = result["usage"]
                        total_tokens = usage["total_tokens"]
                        reasoning_tokens = usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
                        print(f"Token count: {total_tokens} (reasoning tokens: {reasoning_tokens})")
                    
                    return response_text, total_tokens
        except aiohttp.ClientError as e:
            print(f"OpenAI connection error: {str(e)}")
            import traceback
            traceback.print_exc()
            return f"Connection Error: {str(e)}\n\nPlease check your internet connection.", 0
        except Exception as e:
            print(f"Unexpected error with OpenAI API: {str(e)}")
            import traceback
            traceback.print_exc()
            return f"Unexpected error: {str(e)}\n\nPlease check the logs for more details.", 0

# Global client instance
openai_client = OpenAIClient() 