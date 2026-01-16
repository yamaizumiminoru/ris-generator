from PySide6.QtCore import QThread, Signal
import os
from .extraction import extract_text_from_pdf
from .processor import generate_ris_data, dict_to_ris
import time
import random

class ProcessingWorker(QThread):
    # Signals
    progress_update = Signal(int, int, str) # current, total, filename
    finished_processing = Signal(dict) # summary dict
    finished_processing = Signal(dict) # summary dict
    error_occurred = Signal(str) # critical error message

    def __init__(self, pdf_files, api_key, model_name):
        super().__init__()
        self.pdf_files = pdf_files
        self.api_key = api_key
        self.model_name = model_name
        self.skip_existing = False

    def set_skip_existing(self, enabled):
        self.skip_existing = enabled

    def run(self):
        summary = {
            "total": len(self.pdf_files),
            "processed": 0,
            "success": 0,
            "filename_only_success": 0,
            "skipped": 0,
            "failed": 0,
            "failed_files": [], # List of (filename, user_friendly_reason)
            "cancelled": False
        }

        for i, pdf_path in enumerate(self.pdf_files):
            if self.isInterruptionRequested():
                summary["cancelled"] = True
                break
            
            basename = os.path.basename(pdf_path)
            self.progress_update.emit(i + 1, summary["total"], basename)
            
            error_reason = "Unknown Error"
            success_type = "normal" # or "filename_only"
            
            # Check for Skip
            ris_path = os.path.splitext(pdf_path)[0] + ".ris"
            if self.skip_existing and os.path.exists(ris_path):
                summary["skipped"] += 1
                summary["processed"] += 1
                self.progress_update.emit(i + 1, summary["total"], f"{basename} (Skipped)")
                # Yield briefly to keep UI responsive
                time.sleep(0.001) 
                continue

            try:
                # 1. Extraction
                text = extract_text_from_pdf(pdf_path)
                
                # Check for empty text -> Trigger OCR Rescue (Filename Only Mode)
                use_filename_mode = False
                if not text.strip():
                    use_filename_mode = True
                    text = "" # Clear it to be safe
                    # Note: We continue to API call, but with flag
                
                # 2. Gemini API with Retry
                data = None
                max_retries = 2
                
                for attempt in range(max_retries + 1):
                    try:
                        # On 2nd retry for Timeout (attempt==2), we could truncate text further, 
                        # but processor handles 20k chars. Let's just rely on backoff.
                        
                        data = generate_ris_data(
                            text_context=text, 
                            filename=basename, 
                            api_key=self.api_key, 
                            model_name=self.model_name,
                            filename_mode=use_filename_mode
                        )
                        
                        if data: 
                            break # Success
                        else:
                            # AI returned null/empty json
                            if attempt < max_retries:
                                time.sleep(2 ** attempt + random.random())
                                continue
                            else:
                                raise Exception("AI_NULL")

                    except Exception as e:
                        err_str = str(e)
                        # Check for retryable errors
                        # 2) Retry Logic (Auto-Retry)
                        is_retryable = (
                            "429" in err_str or 
                            "500" in err_str or "503" in err_str or "504" in err_str or 
                            "ResourceExhausted" in err_str or 
                            "DeadlineExceeded" in err_str or 
                            "AI_EMPTY_RESPONSE" in err_str or
                            "AI_NULL" in err_str # Also retry null json
                        )
                        
                        if is_retryable and attempt < max_retries:
                            # Exponential backoff + jitter
                            sleep_time = (2 ** attempt) + (random.random() * 1.5)
                            print(f"Retry {attempt+1}/{max_retries} for {basename}: {err_str} (sleeping {sleep_time:.2f}s)")
                            time.sleep(sleep_time)
                            continue
                        else:
                            # Final failure or non-retryable
                            if "429" in err_str or "ResourceExhausted" in err_str:
                                raise Exception("RATE_LIMIT")
                            elif "500" in err_str or "503" in err_str or "504" in err_str or "DeadlineExceeded" in err_str:
                                raise Exception("TIMEOUT")
                            elif "AI_EMPTY_RESPONSE" in err_str or "AI_NULL" in err_str:
                                raise Exception("AI_EMPTY_RESPONSE")
                            else:
                                raise e # Re-raise others

                # 3. Post-Processing & Save
                if data:
                    # Check if valid (need at least TI or AU)
                    has_ti = data.get("TI", {}).get("value")
                    has_au = data.get("AU") # list or dict
                    
                    if not has_ti and not has_au:
                         raise Exception("AI_NULL" if not use_filename_mode else "OCR_REQUIRED")

                    # If this was filename mode, inject the OCR note
                    if use_filename_mode:
                        # 3) OCR Rescue Enhancement
                        # If we have TI but missing others, IT IS ACCEPTABLE for Filename Mode.
                        # We tag it with OCR_REQUIRED in N1 so user knows it's imperfect.
                        
                        note_val = "OCR_REQUIRED"
                        missing_fields = []
                        if not has_au: missing_fields.append("AU")
                        # PY is also often missing in filename only
                        if not data.get("PY", {}).get("value"): missing_fields.append("PY")
                        
                        if missing_fields:
                            note_val += f" (CHECK: {','.join(missing_fields)} missing)"
                        
                        if "N1" not in data: data["N1"] = {}
                        data["N1"]["value"] = note_val
                        
                        success_type = "filename_only"

                        # Allow TI only for filename mode
                        if not has_ti:
                             raise Exception("OCR_REQUIRED") # Even filename failed to give Title


                    ris_content = dict_to_ris(data)
                    ris_path = os.path.splitext(pdf_path)[0] + ".ris"
                    
                    with open(ris_path, "w", encoding="utf-8") as f:
                        f.write(ris_content)
                    
                    if success_type == "filename_only":
                        summary["filename_only_success"] += 1
                    else:
                        summary["success"] += 1
                        
                else:
                    raise Exception("AI_NULL")

            except Exception as e:
                msg = str(e)
                # Map to internal codes for GUI to format
                if "OCR_REQUIRED" in msg: code = "OCR_REQUIRED"
                elif "RATE_LIMIT" in msg: code = "RATE_LIMIT"
                elif "TIMEOUT" in msg: code = "TIMEOUT"
                elif "AI_NULL" in msg: code = "AI_NULL"
                elif "AI_EMPTY_RESPONSE" in msg: code = "AI_EMPTY_RESPONSE"
                elif "Permission" in msg: code = "WRITE_FAILED"
                else: code = f"API_ERROR: {msg}"
                
                summary["failed"] += 1
                summary["failed_files"].append((basename, code))
            
            summary["processed"] += 1
            
        self.finished_processing.emit(summary)
