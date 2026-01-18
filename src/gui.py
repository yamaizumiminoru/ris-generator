import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QCheckBox, QComboBox, 
    QProgressBar, QTextEdit, QFileDialog, QMessageBox, QDialog, QSpinBox
)
from PySide6.QtCore import Qt, Signal, Slot
from .config import load_config, save_config
from .worker import ProcessingWorker

# User-friendly Error Mapping
ERROR_MAP = {
    "OCR_REQUIRED": "OCR Required / Failed to read text (画像PDFのため文字読取不可)",
    "TIMEOUT": "Timeout / Deadline exceeded (通信/混雑で時間切れ)",
    "RATE_LIMIT": "Rate Limit Exceeded (API利用制限/少し待って再実行)",
    "AI_NULL": "AI Response Empty (AI返答なし/再実行推奨)",
    "AI_EMPTY_RESPONSE": "AI Response Empty/Blocked (AI返答拒否or空/再実行推奨)",
    "PARSE_FAILED": "Parse Failed (形式エラー/再実行推奨)",
    "WRITE_FAILED": "File Write Failed (ファイル書き込み失敗/権限確認)"
}

class ResultDialog(QDialog):
    def __init__(self, summary, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generation Complete")
        self.resize(600, 500)
        
        layout = QVBoxLayout(self)
        
        # Status Header
        status = "Cancelled" if summary["cancelled"] else "Complete"
        
        # Calculate rates
        total = summary['total']
        success = summary['success']
        rescued = summary.get('filename_only_success', 0)
        skipped = summary.get('skipped', 0)
        failed = summary['failed']
        
        header = f"Status: {status}\n\n" \
                 f"Total Files: {total}\n" \
                 f"Success (Full): {success}\n" \
                 f"Success (Filename Only): {rescued}\n" \
                 f"Skipped (Existing): {skipped}\n" \
                 f"Failed: {failed}\n"
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setText(header)
        
        self.text_edit.append("--------------------------------------------------")
        
        if summary["failed_files"]:
            self.text_edit.append("【Failed Files Summary】\n")
            
            # Group by error type
            error_groups = {}
            for fname, reason in summary["failed_files"]:
                # user friendly msg
                msg = ERROR_MAP.get(reason, f"予期しないエラー: {reason}")
                if msg not in error_groups:
                    error_groups[msg] = []
                error_groups[msg].append(fname)
            
            # Display groups
            for msg, fnames in error_groups.items():
                self.text_edit.append(f"■ {msg} ({len(fnames)}件)")
                for f in fnames:
                    self.text_edit.append(f"   - {f}")
                self.text_edit.append("")
        else:
            self.text_edit.append("\n(No errors encountered)")

        layout.addWidget(self.text_edit)
        
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)

class ProgressDialog(QDialog):
    cancel_requested = Signal()
    pause_requested = Signal() # New signal

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generating RIS...")
        self.setModal(True)
        self.resize(400, 150)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint | Qt.CustomizeWindowHint | Qt.WindowTitleHint) 
        
        layout = QVBoxLayout(self)
        
        self.status_label = QLabel("Initializing...")
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        self.cancel_btn = QPushButton("Stop / Cancel")
        self.cancel_btn.clicked.connect(self.on_cancel)
        
        # Pause Button
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self.on_pause_clicked)
        
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.pause_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        
    def on_pause_clicked(self):
        self.pause_requested.emit()

    def set_paused_state(self, is_paused):
        if is_paused:
            self.pause_btn.setText("Resume")
            current_text = self.status_label.text()
            if not current_text.startswith("(Paused)"):
                self.status_label.setText(f"(Paused) {current_text}")
        else:
            self.pause_btn.setText("Pause")
            current_text = self.status_label.text().replace("(Paused) ", "")
            self.status_label.setText(current_text)

        
    def update_progress(self, current, total, filename):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Processing: {filename}")
        
    def on_cancel(self):
        self.status_label.setText("Stopping (waiting for current file)...")
        self.cancel_btn.setEnabled(False)
        self.cancel_requested.emit()

    def closeEvent(self, event):
        self.on_cancel()
        event.ignore() 

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RIS Generator (MVP) - Improved")
        self.resize(500, 350)
        
        # Load Config
        self.config = load_config()
        
        # Central Widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        
        # 1. Folder Selection
        folder_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Select folder containing PDFs...")
        self.browse_btn = QPushButton("Browse Folder")
        self.browse_btn.clicked.connect(self.browse_folder)
        folder_layout.addWidget(self.path_edit)
        folder_layout.addWidget(self.browse_btn)
        
        layout.addWidget(QLabel("Target Folder (Subfolders ignored):"))
        layout.addLayout(folder_layout)
        
        # 2. API Key
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("Enter Gemini API Key")
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        if "api_key" in self.config:
            self.api_key_edit.setText(self.config["api_key"])
            
        self.save_key_cb = QCheckBox("Save API Key to this PC")
        self.save_key_cb.setChecked(self.config.get("save_key", False))
        
        layout.addWidget(QLabel("Google Gemini API Key:"))
        layout.addWidget(self.api_key_edit)
        layout.addWidget(self.save_key_cb)
        
        # 3. Model Selection
        model_layout = QHBoxLayout()
        self.model_combo = QComboBox()
        self.model_combo.addItem("Gemini 3 Flash (Preview)", "gemini-3-flash-preview")
        self.model_combo.addItem("Gemini 3 Pro (Preview)", "gemini-3-pro-preview")
        self.model_combo.addItem("Gemini 2.5 Flash", "gemini-2.5-flash")
        self.model_combo.addItem("Gemini 2.5 Pro", "gemini-2.5-pro")
        
        # Check config for saved model
        saved_model = self.config.get("model_name", "gemini-3-flash-preview")
        idx = self.model_combo.findData(saved_model)
        if idx >= 0: self.model_combo.setCurrentIndex(idx)
        else: self.model_combo.setCurrentIndex(0)
        
        layout.addWidget(QLabel("Model:"))
        layout.addWidget(self.model_combo)
        
        # Skip Option
        self.skip_cb = QCheckBox("Skip already generated files (.ris exists)")
        self.skip_cb.setChecked(True)
        layout.addWidget(self.skip_cb)
        
        # Sleep Prevention
        self.prevent_sleep_cb = QCheckBox("Prevent PC sleep while processing (Windows Only)")
        self.prevent_sleep_cb.setChecked(self.config.get("prevent_sleep", False))
        layout.addWidget(self.prevent_sleep_cb)

        # Concurrency
        concurrency_layout = QHBoxLayout()
        concurrency_layout.addWidget(QLabel("Parallel Processing (Max threads):"))
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 10)
        self.workers_spin.setValue(self.config.get("max_workers", 3))
        concurrency_layout.addWidget(self.workers_spin)
        concurrency_layout.addStretch()
        layout.addLayout(concurrency_layout)

        layout.addStretch()
        
        # 4. Start Button
        self.start_btn = QPushButton("Generate RIS Files")
        self.start_btn.setFixedHeight(40)
        self.start_btn.clicked.connect(self.start_processing)
        layout.addWidget(self.start_btn)
        
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.path_edit.setText(folder)
            
    def start_processing(self):
        folder_path = self.path_edit.text().strip()
        api_key = self.api_key_edit.text().strip()
        
        if not folder_path or not os.path.isdir(folder_path):
            QMessageBox.warning(self, "Error", "Please select a valid folder.")
            return
            
        if not api_key:
            QMessageBox.warning(self, "Error", "Please enter an API Key.")
            return
            
        # scan files
        try:
            files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) 
                     if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(folder_path, f))]
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to scan directory: {e}")
            return
            
        if not files:
            QMessageBox.information(self, "Info", "No PDF files found in the selected folder.")
            return

        # Save Config
        save_config(
            api_key if self.save_key_cb.isChecked() else "",
            self.save_key_cb.isChecked(),
            self.model_combo.currentData(),
            self.prevent_sleep_cb.isChecked(),
            self.workers_spin.value()
        )
            
        # Start Worker & Progress Dialog
        self.worker = ProcessingWorker(
            files, 
            api_key, 
            self.model_combo.currentData(),
            prevent_sleep=self.prevent_sleep_cb.isChecked(),
            max_workers=self.workers_spin.value()
        )
        self.worker.set_skip_existing(self.skip_cb.isChecked())
        
        self.progress_dlg = ProgressDialog(self)
        
        # Signals
        self.worker.progress_update.connect(self.progress_dlg.update_progress)
        self.worker.finished_processing.connect(self.on_finished)
        self.progress_dlg.cancel_requested.connect(self.worker.requestInterruption)
        self.progress_dlg.pause_requested.connect(self.toggle_pause)
        
        self.worker.start()
        self.progress_dlg.exec()
        
    def toggle_pause(self):
        if self.worker:
            new_state = self.worker.toggle_pause()
            self.progress_dlg.set_paused_state(new_state)
        
    def on_finished(self, summary):
        if self.progress_dlg.isVisible():
            self.progress_dlg.accept()
            
        self.worker.deleteLater()
        self.worker = None
        
        # Show Result
        dlg = ResultDialog(summary, self)
        dlg.exec()
