from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QPushButton, QTextEdit, QFrame, QMessageBox
)
from ..config import config
from .styles import DARK_THEME

class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration")
        self.setModal(True)
        
        # Apply dark theme
        self.setStyleSheet(DARK_THEME)
        
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # API Keys
        layout.addWidget(QLabel("OpenAI API Key:"))
        self.openai_key = QLineEdit()
        self.openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key.setText(config.openai_api_key or "")
        layout.addWidget(self.openai_key)

        layout.addWidget(QLabel("Anthropic API Key:"))
        self.anthropic_key = QLineEdit()
        self.anthropic_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.anthropic_key.setText(config.anthropic_api_key or "")
        layout.addWidget(self.anthropic_key)

        # Model Selection
        layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(config.available_models)
        current_index = self.model_combo.findText(config.selected_model)
        if current_index >= 0:
            self.model_combo.setCurrentIndex(current_index)
        layout.addWidget(self.model_combo)

        # System Prompt
        layout.addWidget(QLabel("System Prompt:"))
        self.system_prompt = QTextEdit()
        self.system_prompt.setPlainText(config.system_prompt)
        self.system_prompt.setMaximumHeight(100)
        layout.addWidget(self.system_prompt)

        # Parameters
        params_layout = QHBoxLayout()
        
        # Max Tokens
        tokens_layout = QVBoxLayout()
        tokens_layout.addWidget(QLabel("Max Completion Tokens:"))
        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(1, 100000)
        self.max_tokens.setValue(config._get_model_max_completion_tokens(config.selected_model))
        tokens_layout.addWidget(self.max_tokens)
        params_layout.addLayout(tokens_layout)

        # Batch Size
        batch_layout = QVBoxLayout()
        batch_layout.addWidget(QLabel("Batch Size:"))
        self.batch_size = QSpinBox()
        self.batch_size.setRange(1, 100)
        self.batch_size.setValue(config.batch_size)
        batch_layout.addWidget(self.batch_size)
        params_layout.addLayout(batch_layout)

        # Reasoning Effort (for OpenAI models)
        reasoning_layout = QVBoxLayout()
        reasoning_layout.addWidget(QLabel("Reasoning Effort:"))
        self.reasoning_effort = QComboBox()
        self.reasoning_effort.addItems(config.reasoning_effort_options)
        current_effort = self.reasoning_effort.findText(config.reasoning_effort)
        if current_effort >= 0:
            self.reasoning_effort.setCurrentIndex(current_effort)
        reasoning_layout.addWidget(self.reasoning_effort)
        params_layout.addLayout(reasoning_layout)

        layout.addLayout(params_layout)

        # Add a separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # Model-specific info
        self.model_info = QLabel()
        self.update_model_info()
        layout.addWidget(self.model_info)

        # Buttons
        buttons_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        cancel_button = QPushButton("Cancel")
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)
        layout.addLayout(buttons_layout)

        # Connect signals
        save_button.clicked.connect(self.save_config)
        cancel_button.clicked.connect(self.reject)
        self.model_combo.currentTextChanged.connect(self.on_model_changed)

    def on_model_changed(self, model_name: str):
        """Update max tokens and model info when model selection changes"""
        self.max_tokens.setValue(config._get_model_max_completion_tokens(model_name))
        self.update_model_info()
        # Enable/disable reasoning effort based on model type
        self.reasoning_effort.setEnabled(model_name.startswith("o"))

    def update_model_info(self):
        """Update the model information text based on selected model"""
        model = self.model_combo.currentText()
        max_tokens = config._model_rate_limits[model]["max_completion_tokens"]
        recommended_tokens = config._get_model_max_completion_tokens(model)
        
        if model.startswith("o"):
            self.reasoning_effort.setEnabled(True)
            self.model_info.setText(
                f"OpenAI Reasoning Model\n"
                f"• Max tokens: {max_tokens}\n"
                f"• Recommended completion tokens: {recommended_tokens}\n"
                f"• Uses reasoning tokens for complex problem solving\n"
                f"• Adjust reasoning effort to balance speed vs. thoroughness"
            )
        else:
            self.reasoning_effort.setEnabled(False)
            self.model_info.setText(
                f"Anthropic Claude Model\n"
                f"• Max tokens: {max_tokens}\n"
                f"• Recommended completion tokens: {recommended_tokens}\n"
                f"• Standard completion model\n"
                f"• Rate limits: 4,000 RPM, 200K input TPM, 80K output TPM"
            )

    def save_config(self):
        # Update config
        config.openai_api_key = self.openai_key.text()
        config.anthropic_api_key = self.anthropic_key.text()
        config.selected_model = self.model_combo.currentText()
        config.system_prompt = self.system_prompt.toPlainText()
        config.max_completion_tokens = self.max_tokens.value()
        config.batch_size = self.batch_size.value()
        config.reasoning_effort = self.reasoning_effort.currentText()

        # Save to file
        try:
            config.save_config()
            QMessageBox.information(self, "Success", "Settings saved successfully!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {str(e)}") 