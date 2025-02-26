import os
import json
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

class Config:
    def __init__(self):
        load_dotenv()
        self.config_file = "config.json"
        self._init_default_values()
        self.load_saved_config()

    def _init_default_values(self):
        """Initialize default configuration values"""
        self.openai_api_key: Optional[str] = None
        self.anthropic_api_key: Optional[str] = None
        self.selected_model: str = "o1"  # Default to o1 model
        self.system_prompt: str = "You are a helpful assistant."
        self.max_tokens: int = 4096
        self.batch_size: int = 10
        self.reasoning_effort: str = "high"
        self.max_completion_tokens: int = 1000
        self._allowed_models = {
            "o1",  # Advanced OpenAI model
            "o3-mini",  # Fast OpenAI model
            "claude-3-7-sonnet-20250219"  # Anthropic model
        }
        self._model_rate_limits = {
            "o1": {  # Advanced model
                "requests_per_minute": 1000,
                "tokens_per_minute": 30000000,
                "tokens_per_day": 10000000000
            },
            "o3-mini": {  # Faster model
                "requests_per_minute": 30000,
                "tokens_per_minute": 150000000
            },
            "claude-3-7-sonnet-20250219": {
                "requests_per_minute": 4000,
                "input_tokens_per_minute": 200000,
                "output_tokens_per_minute": 80000
            }
        }

    def load_from_env(self):
        """Load configuration from environment variables"""
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

    def to_dict(self):
        return {
            "selected_model": self.selected_model,
            "reasoning_effort": self.reasoning_effort,
            "max_completion_tokens": self.max_completion_tokens,
            "max_tokens": self.max_tokens,
            "system_prompt": self.system_prompt,
            "openai_api_key": self.openai_api_key,
            "anthropic_api_key": self.anthropic_api_key,
            "batch_size": self.batch_size
        }

    @classmethod
    def from_dict(cls, data):
        config = cls()
        model = data.get("selected_model", config.selected_model)
        if model not in config._allowed_models:
            raise ValueError(f"Model {model} is not allowed. Must be one of: {', '.join(config._allowed_models)}")
        config.selected_model = model
        config.reasoning_effort = data.get("reasoning_effort", config.reasoning_effort)
        config.max_completion_tokens = data.get("max_completion_tokens", config.max_completion_tokens)
        config.max_tokens = data.get("max_tokens", config.max_tokens)
        config.system_prompt = data.get("system_prompt", config.system_prompt)
        config.openai_api_key = data.get("openai_api_key", config.openai_api_key)
        config.anthropic_api_key = data.get("anthropic_api_key", config.anthropic_api_key)
        config.batch_size = data.get("batch_size", config.batch_size)
        return config

    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.to_dict(), f)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def load_saved_config(self):
        """Load configuration from file"""
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
                # Validate model
                model = data.get("selected_model", self.selected_model)
                if model not in self._allowed_models:
                    raise ValueError(f"Model {model} is not allowed. Must be one of: {', '.join(self._allowed_models)}")
                
                # Update configuration values
                self.selected_model = model
                self.reasoning_effort = data.get("reasoning_effort", self.reasoning_effort)
                self.max_completion_tokens = data.get("max_completion_tokens", self.max_completion_tokens)
                self.max_tokens = data.get("max_tokens", self.max_tokens)
                self.system_prompt = data.get("system_prompt", self.system_prompt)
                self.openai_api_key = data.get("openai_api_key", self.openai_api_key)
                self.anthropic_api_key = data.get("anthropic_api_key", self.anthropic_api_key)
                self.batch_size = data.get("batch_size", self.batch_size)
            return True
        except Exception as e:
            print(f"Error loading config: {e}")
            return False

    @property
    def available_models(self) -> list:
        """List of available models"""
        return sorted(list(self._allowed_models))

    def set_model(self, model: str) -> bool:
        """Set the selected model, ensuring it's in the allowed list"""
        if model not in self._allowed_models:
            raise ValueError(f"Model {model} is not allowed. Must be one of: {', '.join(self._allowed_models)}")
        self.selected_model = model
        return True

    @property
    def reasoning_effort_options(self) -> list:
        """Available reasoning effort options for OpenAI models"""
        return ["high", "medium", "low"]

    @property
    def model_rate_limits(self) -> dict:
        """Rate limits for different models"""
        return self._model_rate_limits

# Global config instance
config = Config() 