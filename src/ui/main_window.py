import sys
import os
import asyncio
import time
import shutil
from datetime import datetime, timedelta
from collections import deque
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QTableWidget, QTableWidgetItem, 
    QProgressBar, QLabel, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import pandas as pd
from ..config import config
from .config_dialog import ConfigDialog
from ..database.manager import DatabaseManager
from ..api.openai_client import openai_client
from ..api.anthropic_client import anthropic_client
from .styles import DARK_THEME

class RateLimiter:
    def __init__(self, requests_per_minute, tokens_per_minute):
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self.request_timestamps = deque()
        self.token_usage = deque()
        self.window = 60  # 1 minute in seconds

    def can_make_request(self, estimated_tokens=1000):
        now = time.time()
        self._cleanup_old_entries(now)

        # Check request rate
        if len(self.request_timestamps) >= self.requests_per_minute:
            return False

        # Check token rate
        current_token_usage = sum(tokens for _, tokens in self.token_usage)
        if current_token_usage + estimated_tokens > self.tokens_per_minute:
            return False

        return True

    def add_request(self, token_count):
        now = time.time()
        self.request_timestamps.append(now)
        self.token_usage.append((now, token_count))
        self._cleanup_old_entries(now)

    def _cleanup_old_entries(self, now):
        cutoff = now - self.window
        
        while self.request_timestamps and self.request_timestamps[0] < cutoff:
            self.request_timestamps.popleft()
            
        while self.token_usage and self.token_usage[0][0] < cutoff:
            self.token_usage.popleft()

class ProcessingThread(QThread):
    progress = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal()
    error = pyqtSignal(str)
    update_response = pyqtSignal(int, str)  # row, response
    status_update = pyqtSignal(str)  # status message

    def __init__(self, db_manager, documents, model_name):
        super().__init__()
        self.db_manager = db_manager
        self.documents = documents
        self.model_name = model_name
        self.should_stop = False
        
        # Initialize rate limiter based on model
        limits = config.model_rate_limits[model_name]
        if model_name.startswith("claude"):
            self.rate_limiter = RateLimiter(
                limits["requests_per_minute"],
                min(limits["input_tokens_per_minute"], limits["output_tokens_per_minute"])
            )
        else:
            self.rate_limiter = RateLimiter(
                limits["requests_per_minute"],
                limits["tokens_per_minute"]
            )

    async def process_document(self, job, client):
        """Process a single document"""
        try:
            response, token_count = await client.process_document(job["source_doc"])
            await self.db_manager.update_response(job["id"], response, token_count)
            self.update_response.emit(job["row_index"], response)
            self.rate_limiter.add_request(token_count)
            return True
        except Exception as e:
            self.error.emit(f"Error processing job {job['id']}: {str(e)}")
            return False

    async def process_batch(self):
        try:
            # Initialize API client based on model
            if self.model_name.startswith("o"):
                client = openai_client
                client.set_api_key(config.openai_api_key)
            else:
                client = anthropic_client
                client.set_api_key(config.anthropic_api_key)

            # Add batch to database
            batch_id = await self.db_manager.add_batch(self.documents, self.model_name)
            pending_jobs = await self.db_manager.get_pending_jobs(batch_id)

            # Process in parallel batches
            batch_size = min(config.batch_size, 100)
            total_jobs = len(pending_jobs)
            processed = 0

            while pending_jobs and not self.should_stop:
                current_batch = []
                current_size = 0
                
                # Build batch based on rate limits
                while pending_jobs and current_size < batch_size:
                    if self.rate_limiter.can_make_request():
                        current_batch.append(pending_jobs.pop(0))
                        current_size += 1
                    else:
                        # Wait if we hit rate limits
                        self.status_update.emit("Rate limit reached, waiting...")
                        await asyncio.sleep(1)
                        continue

                if not current_batch:
                    continue

                # Process current batch in parallel
                self.status_update.emit(f"Processing batch of {len(current_batch)} documents...")
                tasks = []
                for job in current_batch:
                    if self.should_stop:
                        break
                    tasks.append(self.process_document(job, client))

                # Wait for all tasks to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)
                processed += sum(1 for r in results if r is True)
                self.progress.emit(processed, total_jobs)

            self.finished.emit()

        except Exception as e:
            self.error.emit(f"Batch processing error: {str(e)}")

    def run(self):
        """Run the processing thread"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.process_batch())
        finally:
            loop.close()

    def stop(self):
        """Stop processing"""
        self.should_stop = True


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GPT Batch Processor")
        self.setMinimumSize(800, 600)
        
        # Apply dark theme
        self.setStyleSheet(DARK_THEME)
        
        # Initialize components
        self.db_manager = DatabaseManager()
        self.current_batch_id = None
        self.processing_thread = None
        
        # Create UI
        self.setup_ui()

    def setup_ui(self):
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Toolbar
        toolbar = QHBoxLayout()
        self.config_btn = QPushButton("Configure")
        self.import_excel_btn = QPushButton("Import Excel")
        self.import_folder_btn = QPushButton("Import Folder")
        self.export_btn = QPushButton("Export Excel")
        self.process_btn = QPushButton("Process Batch")
        self.stop_btn = QPushButton("Stop Processing")
        self.save_db_btn = QPushButton("Save Database")
        self.load_db_btn = QPushButton("Load Database")
        
        # Initially disable stop button
        self.stop_btn.setEnabled(False)
        
        toolbar.addWidget(self.config_btn)
        toolbar.addWidget(self.import_excel_btn)
        toolbar.addWidget(self.import_folder_btn)
        toolbar.addWidget(self.export_btn)
        toolbar.addWidget(self.process_btn)
        toolbar.addWidget(self.stop_btn)
        toolbar.addWidget(self.save_db_btn)
        toolbar.addWidget(self.load_db_btn)
        toolbar.addStretch()
        
        # Progress section
        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.status_label = QLabel("Ready")
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Filename", "Source Doc", "Response"])
        self.table.horizontalHeader().setStretchLastSection(True)

        # Add all components to main layout
        layout.addLayout(toolbar)
        layout.addLayout(progress_layout)
        layout.addWidget(self.table)

        # Connect signals
        self.config_btn.clicked.connect(self.show_config_dialog)
        self.import_excel_btn.clicked.connect(self.import_excel)
        self.import_folder_btn.clicked.connect(self.import_folder)
        self.export_btn.clicked.connect(self.export_excel)
        self.process_btn.clicked.connect(self.start_processing)
        self.stop_btn.clicked.connect(self.stop_processing)
        self.save_db_btn.clicked.connect(self.save_database)
        self.load_db_btn.clicked.connect(self.load_database)

    def show_config_dialog(self):
        dialog = ConfigDialog(self)
        dialog.exec()

    def import_folder(self):
        folder_path = QFileDialog.getExistingDirectory(
            self, "Select Folder to Import", "", QFileDialog.Option.ShowDirsOnly
        )
        if folder_path:
            try:
                documents = []
                for ext in ['.txt', '.md']:
                    for file_path in Path(folder_path).rglob(f'*{ext}'):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read().strip()
                                if content:  # Only add non-empty files
                                    documents.append({
                                        "filename": str(file_path.relative_to(folder_path)),
                                        "content": content
                                    })
                        except Exception as e:
                            print(f"Error reading {file_path}: {e}")
                            continue

                if not documents:
                    QMessageBox.warning(self, "Warning", "No valid text files found in the selected folder")
                    return

                # Update table
                self.table.setRowCount(len(documents))
                for i, doc in enumerate(documents):
                    self.table.setItem(i, 0, QTableWidgetItem(doc["filename"]))
                    self.table.setItem(i, 1, QTableWidgetItem(doc["content"]))

                QMessageBox.information(
                    self, "Success", 
                    f"Imported {len(documents)} files successfully"
                )

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import folder: {str(e)}")

    def import_excel(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Import Excel File", "", "Excel Files (*.xlsx *.xls)"
        )
        if file_name:
            try:
                df = pd.read_excel(file_name)
                required_cols = {"Source Doc"}
                if not required_cols.issubset(df.columns):
                    raise ValueError("Excel file must have a 'Source Doc' column")
                
                # Update table
                self.table.setRowCount(len(df))
                for i, row in df.iterrows():
                    # Use Excel filename as default if not specified
                    filename = row.get("Filename", os.path.basename(file_name))
                    self.table.setItem(i, 0, QTableWidgetItem(str(filename)))
                    self.table.setItem(i, 1, QTableWidgetItem(str(row["Source Doc"])))
                    if "Response" in df.columns and pd.notna(row["Response"]):
                        self.table.setItem(i, 2, QTableWidgetItem(str(row["Response"])))
                
                QMessageBox.information(self, "Success", "Data imported successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import: {str(e)}")

    def export_excel(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Warning", "No data to export")
            return

        file_name, _ = QFileDialog.getSaveFileName(
            self, "Export Excel File", "", "Excel Files (*.xlsx)"
        )
        if file_name:
            try:
                data = []
                for row in range(self.table.rowCount()):
                    filename = self.table.item(row, 0)
                    source = self.table.item(row, 1)
                    response = self.table.item(row, 2)
                    data.append({
                        "Filename": filename.text() if filename else "",
                        "Source Doc": source.text() if source else "",
                        "Response": response.text() if response else ""
                    })
                
                df = pd.DataFrame(data)
                df.to_excel(file_name, index=False)
                QMessageBox.information(self, "Success", "Data exported successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export: {str(e)}")

    def start_processing(self):
        if self.processing_thread and self.processing_thread.isRunning():
            QMessageBox.warning(self, "Warning", "Processing is already in progress")
            return

        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Warning", "No data to process")
            return

        if not config.openai_api_key and not config.anthropic_api_key:
            QMessageBox.warning(self, "Warning", "Please configure API keys first")
            return

        # Collect documents
        documents = []
        for row in range(self.table.rowCount()):
            filename = self.table.item(row, 0)
            source = self.table.item(row, 1)
            if source and source.text().strip():
                documents.append({
                    "filename": filename.text() if filename else "",
                    "content": source.text().strip()
                })

        # Start processing
        self.progress_bar.setMaximum(len(documents))
        self.progress_bar.setValue(0)
        self.status_label.setText("Processing...")
        
        # Enable stop button and disable process button
        self.stop_btn.setEnabled(True)
        self.process_btn.setEnabled(False)
        
        self.processing_thread = ProcessingThread(self.db_manager, documents, config.selected_model)
        self.processing_thread.progress.connect(self.update_progress)
        self.processing_thread.error.connect(self.show_error)
        self.processing_thread.finished.connect(self.processing_finished)
        self.processing_thread.update_response.connect(self.update_table_response)
        self.processing_thread.status_update.connect(self.update_status)
        self.processing_thread.start()

    def update_progress(self, current, total):
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Processing: {current}/{total}")

    def show_error(self, error_message):
        QMessageBox.critical(self, "Error", error_message)

    def processing_finished(self):
        """Handle completion of processing"""
        self.status_label.setText("Processing completed")
        self.stop_btn.setEnabled(False)
        self.process_btn.setEnabled(True)
        QMessageBox.information(self, "Success", "Batch processing completed")

    def update_table_response(self, row, response):
        self.table.setItem(row, 2, QTableWidgetItem(response))

    def update_status(self, message: str):
        """Update the status label with a message"""
        self.status_label.setText(message)

    def stop_processing(self):
        """Stop the current processing batch"""
        if self.processing_thread and self.processing_thread.isRunning():
            reply = QMessageBox.question(
                self, 
                "Confirm Stop", 
                "Are you sure you want to stop processing?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.processing_thread.stop()
                self.status_label.setText("Stopping... Please wait...")
                self.stop_btn.setEnabled(False)

    def closeEvent(self, event):
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.stop()
            self.processing_thread.wait()
        event.accept()

    async def load_table_data(self):
        """Load data from database into table"""
        conn = await self.db_manager.get_connection()
        try:
            async with conn.execute(
                """SELECT filename, source_doc, response, status 
                   FROM processing_jobs 
                   ORDER BY id"""
            ) as cursor:
                rows = await cursor.fetchall()
                
                self.table.setRowCount(len(rows))
                for i, row in enumerate(rows):
                    self.table.setItem(i, 0, QTableWidgetItem(row[0] or ""))
                    self.table.setItem(i, 1, QTableWidgetItem(row[1] or ""))
                    self.table.setItem(i, 2, QTableWidgetItem(row[2] or ""))
                    
                    # Color code based on status
                    if row[3] == 'completed':
                        self.table.item(i, 2).setBackground(Qt.GlobalColor.darkGreen)
                    elif row[3] == 'error':
                        self.table.item(i, 2).setBackground(Qt.GlobalColor.darkRed)
        finally:
            await self.db_manager.release_connection(conn)

    def save_database(self):
        """Save current database to a new location"""
        if self.processing_thread and self.processing_thread.isRunning():
            QMessageBox.warning(self, "Warning", "Please wait for processing to complete before saving")
            return

        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save Database", "", "SQLite Database (*.db)"
        )
        if file_name:
            try:
                # Close current database connections
                loop = asyncio.get_event_loop()
                loop.run_until_complete(self.db_manager.close_all_connections())
                
                # Copy database file
                shutil.copy2(self.db_manager.db_path, file_name)
                QMessageBox.information(self, "Success", "Database saved successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save database: {str(e)}")

    def load_database(self):
        """Load a previously saved database"""
        if self.processing_thread and self.processing_thread.isRunning():
            QMessageBox.warning(self, "Warning", "Please wait for processing to complete before loading")
            return

        file_name, _ = QFileDialog.getOpenFileName(
            self, "Load Database", "", "SQLite Database (*.db)"
        )
        if file_name:
            try:
                # Close current database connections
                loop = asyncio.get_event_loop()
                loop.run_until_complete(self.db_manager.close_all_connections())
                
                # Copy selected database to working location
                shutil.copy2(file_name, self.db_manager.db_path)
                
                # Reload data into table
                loop.run_until_complete(self.load_table_data())
                QMessageBox.information(self, "Success", "Database loaded successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load database: {str(e)}") 