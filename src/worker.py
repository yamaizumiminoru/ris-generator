from PySide6.QtCore import QThread, Signal
import os
from .extraction import extract_text_from_pdf
from .processor import generate_ris_data, dict_to_ris
import time
import random
import concurrent.futures
from PySide6.QtCore import QMutex, QWaitCondition
import ctypes

# Windows Sleep Constants
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


class ProcessingWorker(QThread):
    # Signals
    progress_update = Signal(int, int, str) # current, total, filename
    finished_processing = Signal(dict) # summary dict
    error_occurred = Signal(str) # critical error message

    def __init__(self, pdf_files, api_key, model_name, prevent_sleep=False, max_workers=3):
        super().__init__()
        self.pdf_files = pdf_files
        self.api_key = api_key
        self.model_name = model_name
        self.prevent_sleep = prevent_sleep
        self.max_workers = max_workers
        self.skip_existing = False
        self._paused = False
        self._mutex = QMutex()

    def toggle_pause(self):
        self._paused = not self._paused
        return self._paused

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
            "failed_files": [], 
            "cancelled": False
        }

        # Sleep Prevention Start
        if self.prevent_sleep:
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
                print("Sleep prevention enabled.")
            except Exception as e:
                print(f"Failed to set execution state: {e}")

        # Executor
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)
        futures = set()
        
        try:
            for i, pdf_path in enumerate(self.pdf_files):
                # Pause Check
                while self._paused:
                    if self.isInterruptionRequested():
                        summary["cancelled"] = True
                        break
                    self.msleep(100) 
                
                # Check cancellation in outer loop
                if self.isInterruptionRequested() or summary.get("cancelled"):
                    summary["cancelled"] = True
                    break
                
                # Rate Limiting / Queue Control
                # While we have max_workers active, wait for one to finish
                while len(futures) >= self.max_workers:
                     done, futures = concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_COMPLETED)
                     self._process_futures_results(done, summary)
                     if self.isInterruptionRequested(): break # Exit wait loop if cancelled

                if summary.get("cancelled") or self.isInterruptionRequested():
                    break

                # Submit task
                future = executor.submit(self._process_single_file, pdf_path, i, summary["total"])
                futures.add(future)
            
            # Wait for remaining
            if not summary.get("cancelled"):
                while futures:
                    if self.isInterruptionRequested():
                        summary["cancelled"] = True
                        break
                    done, futures = concurrent.futures.wait(futures, timeout=0.2, return_when=concurrent.futures.FIRST_COMPLETED)
                    self._process_futures_results(done, summary)
                    
            # If cancelled, we should try to cancel remaining futures?
            if summary.get("cancelled"):
                 for f in futures: f.cancel()

        finally:
            executor.shutdown(wait=False)
            
            # Sleep Prevention Release
            if self.prevent_sleep:
                try:
                    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
                    print("Sleep prevention released.")
                except Exception as e:
                    print(f"Failed to release execution state: {e}")

            self.finished_processing.emit(summary)

    def _process_futures_results(self, done_futures, summary):
        for f in done_futures:
            try:
                res = f.result()
                # res is dict: {status: 'success'|'skipped'|'failed', filename: str, reason: str, type: str}
                
                self._mutex.lock()
                try:
                    if res['status'] == 'skipped':
                        summary['skipped'] += 1
                    elif res['status'] == 'success':
                        if res.get('type') == 'filename_only':
                            summary['filename_only_success'] += 1
                        else:
                            summary['success'] += 1
                    else: # failed
                        summary['failed'] += 1
                        summary['failed_files'].append((res['filename'], res.get('reason', 'UNKNOWN')))
                    
                    summary['processed'] += 1
                finally:
                    self._mutex.unlock()

            except Exception as e:
                print(f"Future Error: {e}")
                self._mutex.lock()
                summary['failed'] += 1
                summary['processed'] += 1
                self._mutex.unlock()

    def _process_single_file(self, pdf_path, idx, total_count):
        basename = os.path.basename(pdf_path)
        # Emit 'Started' signal? Signal emitting from thread is safe.
        self.progress_update.emit(idx + 1, total_count, basename) # idx here is start index, might be out of order in UI updates but OK

        # Skip Logic
        ris_path = os.path.splitext(pdf_path)[0] + ".ris"
        if self.skip_existing and os.path.exists(ris_path):
            self.progress_update.emit(idx + 1, total_count, f"{basename} (Skipped)")
            return {'status': 'skipped', 'filename': basename}

        try:
            # 1. Extraction
            text = extract_text_from_pdf(pdf_path)
            
            use_filename_mode = False
            if not text.strip():
                use_filename_mode = True
                text = ""

            # 2. Gemini API with Retry
            data = None
            max_retries = 2
            
            for attempt in range(max_retries + 1):
                try:
                    data = generate_ris_data(
                        text_context=text, 
                        filename=basename, 
                        api_key=self.api_key, 
                        model_name=self.model_name,
                        filename_mode=use_filename_mode
                    )
                    
                    if data: break 
                    else:
                        if attempt < max_retries:
                            time.sleep(2 ** attempt + random.random())
                            continue
                        else:
                            raise Exception("AI_NULL")

                except Exception as e:
                    err_str = str(e)
                    is_retryable = (
                        "429" in err_str or 
                        "500" in err_str or "503" in err_str or "504" in err_str or 
                        "ResourceExhausted" in err_str or 
                        "DeadlineExceeded" in err_str or 
                        "AI_EMPTY_RESPONSE" in err_str or
                        "AI_NULL" in err_str 
                    )
                    
                    if is_retryable and attempt < max_retries:
                        sleep_time = (2 ** attempt) + (random.random() * 1.5)
                        print(f"Retry {attempt+1}/{max_retries} for {basename}: {err_str}")
                        time.sleep(sleep_time)
                        continue
                    else:
                        if "429" in err_str or "ResourceExhausted" in err_str: raise Exception("RATE_LIMIT")
                        elif "500" in err_str or "503" in err_str or "504" in err_str or "DeadlineExceeded" in err_str: raise Exception("TIMEOUT")
                        elif "AI_EMPTY_RESPONSE" in err_str or "AI_NULL" in err_str: raise Exception("AI_EMPTY_RESPONSE")
                        else: raise e

            # 3. Post-Processing & Save
            if data:
                has_ti = data.get("TI", {}).get("value")
                has_au = data.get("AU") 
                
                if not has_ti and not has_au:
                        raise Exception("AI_NULL" if not use_filename_mode else "OCR_REQUIRED")

                success_type = "normal"
                if use_filename_mode:
                    note_val = "OCR_REQUIRED"
                    missing_fields = []
                    if not has_au: missing_fields.append("AU")
                    if not data.get("PY", {}).get("value"): missing_fields.append("PY")
                    
                    if missing_fields: note_val += f" (CHECK: {','.join(missing_fields)} missing)"
                    
                    if "N1" not in data: data["N1"] = {}
                    data["N1"]["value"] = note_val
                    
                    success_type = "filename_only"
                    if not has_ti: raise Exception("OCR_REQUIRED") 

                ris_content = dict_to_ris(data)
                ris_path = os.path.splitext(pdf_path)[0] + ".ris"
                
                with open(ris_path, "w", encoding="utf-8") as f:
                    f.write(ris_content)
                
                return {'status': 'success', 'filename': basename, 'type': success_type}
                    
            else:
                raise Exception("AI_NULL")

        except Exception as e:
            msg = str(e)
            if "OCR_REQUIRED" in msg: code = "OCR_REQUIRED"
            elif "RATE_LIMIT" in msg: code = "RATE_LIMIT"
            elif "TIMEOUT" in msg: code = "TIMEOUT"
            elif "AI_NULL" in msg: code = "AI_NULL"
            elif "AI_EMPTY_RESPONSE" in msg: code = "AI_EMPTY_RESPONSE"
            elif "Permission" in msg: code = "WRITE_FAILED"
            else: code = f"API_ERROR: {msg}"
            
            return {'status': 'failed', 'filename': basename, 'reason': code}
