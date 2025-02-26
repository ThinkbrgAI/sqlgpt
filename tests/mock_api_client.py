import asyncio
from typing import Optional

class MockAPIClient:
    def __init__(self):
        self.api_key: Optional[str] = None
        self.call_count = 0
        self.last_call_time = 0

    def set_api_key(self, api_key: str):
        self.api_key = api_key

    async def process_document(self, document: str) -> tuple[str, int]:
        """Mock document processing with simulated delay and token counting"""
        if not self.api_key:
            raise ValueError("API key not set")

        # Simulate API processing
        await asyncio.sleep(0.1)
        
        # Simple mock response generation
        response = f"Mock response for: {document[:50]}..."
        token_count = len(document.split()) * 2  # Simple token estimation
        
        self.call_count += 1
        return response, token_count

# Global mock client instances
mock_openai_client = MockAPIClient()
mock_anthropic_client = MockAPIClient() 