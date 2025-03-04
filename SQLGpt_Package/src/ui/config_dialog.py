from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QPushButton, QTextEdit, QFrame, QMessageBox, QCheckBox,
    QTabWidget, QWidget, QRadioButton, QButtonGroup
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

        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Create tabs
        self.general_tab = QWidget()
        self.document_conversion_tab = QWidget()
        
        # Add tabs to widget
        self.tab_widget.addTab(self.general_tab, "General")
        self.tab_widget.addTab(self.document_conversion_tab, "Document Conversion")
        
        # Setup each tab
        self.setup_general_tab()
        self.setup_document_conversion_tab()
        
        layout.addWidget(self.tab_widget)

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
        self.llamaparse_mode.currentTextChanged.connect(self.update_llamaparse_info)
        self.conversion_method_group.buttonClicked.connect(self.on_conversion_method_changed)

    def setup_general_tab(self):
        layout = QVBoxLayout(self.general_tab)
        
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

        layout.addWidget(QLabel("LlamaParse API Key:"))
        self.llamaparse_key = QLineEdit()
        self.llamaparse_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.llamaparse_key.setText(config.llamaparse_api_key or "")
        layout.addWidget(self.llamaparse_key)

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

        # Model-specific info
        self.model_info = QLabel()
        self.update_model_info()
        layout.addWidget(self.model_info)

    def setup_document_conversion_tab(self):
        layout = QVBoxLayout(self.document_conversion_tab)
        
        # Document Conversion Method
        layout.addWidget(QLabel("Document Conversion Method:"))
        
        # Create radio buttons for conversion method
        method_layout = QHBoxLayout()
        self.conversion_method_group = QButtonGroup(self)
        
        self.llamaparse_radio = QRadioButton("LlamaParse (Premium)")
        self.markitdown_radio = QRadioButton("MarkItDown (Local)")
        
        self.conversion_method_group.addButton(self.llamaparse_radio)
        self.conversion_method_group.addButton(self.markitdown_radio)
        
        # Set the current selection based on config
        if config.document_conversion_method == "llamaparse":
            self.llamaparse_radio.setChecked(True)
        else:
            self.markitdown_radio.setChecked(True)
        
        method_layout.addWidget(self.llamaparse_radio)
        method_layout.addWidget(self.markitdown_radio)
        layout.addLayout(method_layout)
        
        # Create a stacked widget for the different conversion methods
        self.llamaparse_widget = QWidget()
        self.markitdown_widget = QWidget()
        
        # Setup LlamaParse settings
        self.setup_llamaparse_settings()
        
        # Setup MarkItDown settings
        self.setup_markitdown_settings()
        
        # Add the widgets to the layout
        layout.addWidget(self.llamaparse_widget)
        layout.addWidget(self.markitdown_widget)
        
        # Show/hide based on current selection
        self.on_conversion_method_changed()

    def setup_llamaparse_settings(self):
        llamaparse_layout = QVBoxLayout(self.llamaparse_widget)
        
        # Add a separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        llamaparse_layout.addWidget(line)
        
        llamaparse_layout.addWidget(QLabel("LlamaParse Settings"))
        
        # Mode selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Parse Mode:"))
        self.llamaparse_mode = QComboBox()
        self.llamaparse_mode.addItems(["balanced", "fast", "premium"])
        current_mode = self.llamaparse_mode.findText(config.llamaparse_mode)
        if current_mode >= 0:
            self.llamaparse_mode.setCurrentIndex(current_mode)
        mode_layout.addWidget(self.llamaparse_mode)
        llamaparse_layout.addLayout(mode_layout)

        # Checkboxes for boolean options
        self.llamaparse_continuous = QCheckBox("Continuous Mode (better for multi-page tables)")
        self.llamaparse_continuous.setChecked(config.llamaparse_continuous_mode)
        llamaparse_layout.addWidget(self.llamaparse_continuous)

        self.llamaparse_auto = QCheckBox("Auto Mode (upgrade to premium for complex pages)")
        self.llamaparse_auto.setChecked(config.llamaparse_auto_mode)
        llamaparse_layout.addWidget(self.llamaparse_auto)

        # Max pages and language
        pages_lang_layout = QHBoxLayout()
        
        pages_layout = QVBoxLayout()
        pages_layout.addWidget(QLabel("Max Pages (0 = no limit):"))
        self.llamaparse_max_pages = QSpinBox()
        self.llamaparse_max_pages.setRange(0, 1000)
        self.llamaparse_max_pages.setValue(config.llamaparse_max_pages)
        pages_layout.addWidget(self.llamaparse_max_pages)
        pages_lang_layout.addLayout(pages_layout)

        lang_layout = QVBoxLayout()
        lang_layout.addWidget(QLabel("Language:"))
        self.llamaparse_language = QLineEdit()
        self.llamaparse_language.setText(config.llamaparse_language)
        lang_layout.addWidget(self.llamaparse_language)
        pages_lang_layout.addLayout(lang_layout)
        
        llamaparse_layout.addLayout(pages_lang_layout)

        # Advanced options
        advanced_layout = QVBoxLayout()
        self.llamaparse_disable_ocr = QCheckBox("Disable OCR")
        self.llamaparse_disable_ocr.setChecked(config.llamaparse_disable_ocr)
        advanced_layout.addWidget(self.llamaparse_disable_ocr)

        self.llamaparse_skip_diagonal = QCheckBox("Skip Diagonal Text")
        self.llamaparse_skip_diagonal.setChecked(config.llamaparse_skip_diagonal_text)
        advanced_layout.addWidget(self.llamaparse_skip_diagonal)

        self.llamaparse_no_unroll = QCheckBox("Do Not Unroll Columns")
        self.llamaparse_no_unroll.setChecked(config.llamaparse_do_not_unroll_columns)
        advanced_layout.addWidget(self.llamaparse_no_unroll)

        self.llamaparse_html_tables = QCheckBox("Output Tables as HTML")
        self.llamaparse_html_tables.setChecked(config.llamaparse_output_tables_as_html)
        advanced_layout.addWidget(self.llamaparse_html_tables)

        self.llamaparse_preserve_layout = QCheckBox("Preserve Layout Alignment")
        self.llamaparse_preserve_layout.setChecked(config.llamaparse_preserve_layout_alignment)
        advanced_layout.addWidget(self.llamaparse_preserve_layout)

        llamaparse_layout.addLayout(advanced_layout)

    def setup_markitdown_settings(self):
        markitdown_layout = QVBoxLayout(self.markitdown_widget)
        
        # Add a separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        markitdown_layout.addWidget(line)
        
        markitdown_layout.addWidget(QLabel("MarkItDown Settings"))
        
        # Max pages
        pages_layout = QHBoxLayout()
        pages_layout.addWidget(QLabel("Max Pages (0 = no limit):"))
        self.markitdown_max_pages = QSpinBox()
        self.markitdown_max_pages.setRange(0, 1000)
        self.markitdown_max_pages.setValue(config.markitdown_max_pages)
        pages_layout.addWidget(self.markitdown_max_pages)
        markitdown_layout.addLayout(pages_layout)
        
        # Information about MarkItDown
        markitdown_info = QLabel(
            "MarkItDown is a local document conversion tool that supports:\n"
            "• PDF\n"
            "• PowerPoint\n"
            "• Word\n"
            "• Excel\n"
            "• Images (EXIF metadata and OCR)\n"
            "• Audio (EXIF metadata and speech transcription)\n"
            "• HTML\n"
            "• Text-based formats (CSV, JSON, XML)\n"
            "• ZIP files\n\n"
            "Using MarkItDown processes files locally on your machine without sending data to external services."
        )
        markitdown_layout.addWidget(markitdown_info)

    def on_conversion_method_changed(self):
        # Show/hide the appropriate settings based on the selected conversion method
        if self.llamaparse_radio.isChecked():
            self.llamaparse_widget.setVisible(True)
            self.markitdown_widget.setVisible(False)
        else:
            self.llamaparse_widget.setVisible(False)
            self.markitdown_widget.setVisible(True)

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

    def update_llamaparse_info(self):
        """Update the model information text based on LlamaParse mode"""
        mode = self.llamaparse_mode.currentText()
        if mode == "fast":
            self.model_info.setText(
                "LlamaParse Fast Mode (parse_page_without_llm)\n"
                "• Cost: 0.1¢ per page (min 0.3¢ per document)\n"
                "• Best for: Quick text extraction\n"
                "• Basic layout parsing without LLM enhancement\n"
                "• Fastest processing time"
            )
        elif mode == "balanced":
            self.model_info.setText(
                "LlamaParse Balanced Mode (parse_page_with_llm)\n"
                "• Cost: 0.3¢ per page\n"
                "• Best for: Most documents\n"
                "• Uses LLM to enhance parsing quality\n"
                "• Good balance of speed and accuracy"
            )
        elif mode == "premium":
            self.model_info.setText(
                "LlamaParse Premium Mode (parse_document_with_llm)\n"
                "• Cost: 4.5¢ per page\n"
                "• Best for: Complex documents\n"
                "• Uses multimodal models for document-level understanding\n"
                "• Highest accuracy for complex layouts"
            )

    def save_config(self):
        # Update config
        config.openai_api_key = self.openai_key.text()
        config.anthropic_api_key = self.anthropic_key.text()
        config.llamaparse_api_key = self.llamaparse_key.text()
        config.selected_model = self.model_combo.currentText()
        config.system_prompt = self.system_prompt.toPlainText()
        config.max_completion_tokens = self.max_tokens.value()
        config.batch_size = self.batch_size.value()
        config.reasoning_effort = self.reasoning_effort.currentText()

        # Document conversion method
        config.document_conversion_method = "llamaparse" if self.llamaparse_radio.isChecked() else "markitdown"
        
        # LlamaParse settings
        config.llamaparse_mode = self.llamaparse_mode.currentText()
        config.llamaparse_continuous_mode = self.llamaparse_continuous.isChecked()
        config.llamaparse_auto_mode = self.llamaparse_auto.isChecked()
        config.llamaparse_max_pages = self.llamaparse_max_pages.value()
        config.llamaparse_language = self.llamaparse_language.text()
        config.llamaparse_disable_ocr = self.llamaparse_disable_ocr.isChecked()
        config.llamaparse_skip_diagonal_text = self.llamaparse_skip_diagonal.isChecked()
        config.llamaparse_do_not_unroll_columns = self.llamaparse_no_unroll.isChecked()
        config.llamaparse_output_tables_as_html = self.llamaparse_html_tables.isChecked()
        config.llamaparse_preserve_layout_alignment = self.llamaparse_preserve_layout.isChecked()
        
        # MarkItDown settings
        config.markitdown_max_pages = self.markitdown_max_pages.value()

        # Save to file
        try:
            config.save_config()
            QMessageBox.information(self, "Success", "Settings saved successfully!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {str(e)}") 