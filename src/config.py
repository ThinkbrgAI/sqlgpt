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
        self.llamaparse_api_key: Optional[str] = None
        self.selected_model: str = "o1"  # Default to o1 model
        self.system_prompt: str = "You are a helpful assistant."
        self.max_tokens: int = 4096
        self.batch_size: int = 10
        self.reasoning_effort: str = "high"
        
        # LlamaParse settings
        self.llamaparse_mode: str = "balanced"  # balanced, fast, premium
        self.llamaparse_continuous_mode: bool = False
        self.llamaparse_auto_mode: bool = False
        self.llamaparse_max_pages: int = 0  # 0 means no limit
        self.llamaparse_language: str = "en"
        self.llamaparse_disable_ocr: bool = False
        self.llamaparse_skip_diagonal_text: bool = False
        self.llamaparse_do_not_unroll_columns: bool = False
        self.llamaparse_output_tables_as_html: bool = True
        self.llamaparse_preserve_layout_alignment: bool = True
        
        self._allowed_models = {
            "o1",  # Advanced OpenAI model
            "o3-mini",  # Fast OpenAI model
            "claude-3-7-sonnet-20250219"  # Anthropic model
        }
        self._model_rate_limits = {
            "o1": {  # Advanced model
                "requests_per_minute": 1000,
                "tokens_per_minute": 30000000,
                "tokens_per_day": 10000000000,
                "max_completion_tokens": 4096
            },
            "o3-mini": {  # Faster model
                "requests_per_minute": 30000,
                "tokens_per_minute": 150000000,
                "max_completion_tokens": 4096
            },
            "claude-3-7-sonnet-20250219": {
                "requests_per_minute": 4000,
                "input_tokens_per_minute": 200000,
                "output_tokens_per_minute": 80000,
                "max_completion_tokens": 4096
            }
        }
        # Set initial max_completion_tokens based on default model
        self.max_completion_tokens = self._get_model_max_completion_tokens(self.selected_model)

    def _get_model_max_completion_tokens(self, model: str) -> int:
        """Get the recommended max completion tokens for a model"""
        # Get the model's max completion tokens, default to 2048 if not specified
        max_tokens = self._model_rate_limits.get(model, {}).get("max_completion_tokens", 2048)
        # Leave some room for the completion (use 75% of max)
        return int(max_tokens * 0.75)

    def load_from_env(self):
        """Load configuration from environment variables"""
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.llamaparse_api_key = os.getenv("LLAMA_CLOUD_API_KEY")

    def to_dict(self):
        return {
            "selected_model": self.selected_model,
            "reasoning_effort": self.reasoning_effort,
            "max_completion_tokens": self.max_completion_tokens,
            "max_tokens": self.max_tokens,
            "system_prompt": self.system_prompt,
            "openai_api_key": self.openai_api_key,
            "anthropic_api_key": self.anthropic_api_key,
            "llamaparse_api_key": self.llamaparse_api_key,
            "batch_size": self.batch_size,
            "llamaparse_mode": self.llamaparse_mode,
            "llamaparse_continuous_mode": self.llamaparse_continuous_mode,
            "llamaparse_auto_mode": self.llamaparse_auto_mode,
            "llamaparse_max_pages": self.llamaparse_max_pages,
            "llamaparse_language": self.llamaparse_language,
            "llamaparse_disable_ocr": self.llamaparse_disable_ocr,
            "llamaparse_skip_diagonal_text": self.llamaparse_skip_diagonal_text,
            "llamaparse_do_not_unroll_columns": self.llamaparse_do_not_unroll_columns,
            "llamaparse_output_tables_as_html": self.llamaparse_output_tables_as_html,
            "llamaparse_preserve_layout_alignment": self.llamaparse_preserve_layout_alignment
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
        config.llamaparse_api_key = data.get("llamaparse_api_key", config.llamaparse_api_key)
        config.batch_size = data.get("batch_size", config.batch_size)
        
        # LlamaParse settings
        config.llamaparse_mode = data.get("llamaparse_mode", config.llamaparse_mode)
        config.llamaparse_continuous_mode = data.get("llamaparse_continuous_mode", config.llamaparse_continuous_mode)
        config.llamaparse_auto_mode = data.get("llamaparse_auto_mode", config.llamaparse_auto_mode)
        config.llamaparse_max_pages = data.get("llamaparse_max_pages", config.llamaparse_max_pages)
        config.llamaparse_language = data.get("llamaparse_language", config.llamaparse_language)
        config.llamaparse_disable_ocr = data.get("llamaparse_disable_ocr", config.llamaparse_disable_ocr)
        config.llamaparse_skip_diagonal_text = data.get("llamaparse_skip_diagonal_text", config.llamaparse_skip_diagonal_text)
        config.llamaparse_do_not_unroll_columns = data.get("llamaparse_do_not_unroll_columns", config.llamaparse_do_not_unroll_columns)
        config.llamaparse_output_tables_as_html = data.get("llamaparse_output_tables_as_html", config.llamaparse_output_tables_as_html)
        config.llamaparse_preserve_layout_alignment = data.get("llamaparse_preserve_layout_alignment", config.llamaparse_preserve_layout_alignment)
        
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
                self.llamaparse_api_key = data.get("llamaparse_api_key", self.llamaparse_api_key)
                self.batch_size = data.get("batch_size", self.batch_size)
                
                # LlamaParse settings
                self.llamaparse_mode = data.get("llamaparse_mode", self.llamaparse_mode)
                self.llamaparse_continuous_mode = data.get("llamaparse_continuous_mode", self.llamaparse_continuous_mode)
                self.llamaparse_auto_mode = data.get("llamaparse_auto_mode", self.llamaparse_auto_mode)
                self.llamaparse_max_pages = data.get("llamaparse_max_pages", self.llamaparse_max_pages)
                self.llamaparse_language = data.get("llamaparse_language", self.llamaparse_language)
                self.llamaparse_disable_ocr = data.get("llamaparse_disable_ocr", self.llamaparse_disable_ocr)
                self.llamaparse_skip_diagonal_text = data.get("llamaparse_skip_diagonal_text", self.llamaparse_skip_diagonal_text)
                self.llamaparse_do_not_unroll_columns = data.get("llamaparse_do_not_unroll_columns", self.llamaparse_do_not_unroll_columns)
                self.llamaparse_output_tables_as_html = data.get("llamaparse_output_tables_as_html", self.llamaparse_output_tables_as_html)
                self.llamaparse_preserve_layout_alignment = data.get("llamaparse_preserve_layout_alignment", self.llamaparse_preserve_layout_alignment)
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
        # Update max_completion_tokens based on the new model
        self.max_completion_tokens = self._get_model_max_completion_tokens(model)
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