from PySide6.QtCore import QThread, Signal
import os
from .extraction import extract_text_from_pdf
from .processor import generate_ris_data, dict_to_ris
import time
import random
import concurrent.futures
from PySide6.QtCore import QMutex, QWaitCondition
import ctypes
import threading

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
        self._cancel_event = threading.Event()

    def toggle_pause(self):
        self._paused = not self._paused
        return self._paused

    def set_skip_existing(self, enabled):
        self.skip_existing = enabled

    def request_cancel(self):
        """Request cooperative cancellation from the GUI.

        ThreadPool jobs cannot be force-killed safely.  This event is visible
        to both the QThread coordinator and executor worker threads.
        """
        self._cancel_event.set()
        self.requestInterruption()

    def _cancel_requested(self):
        return self._cancel_event.is_set() or self.isInterruptionRequested()

    def _wait_or_cancel(self, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self._cancel_requested():
                return False
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
        return not self._cancel_requested()

    @staticmethod
    def _cancelled_result(filename):
        return {"status": "cancelled", "filename": filename}

    def _emit_finished(self, summary):
        # Kept as a seam for lifecycle regression tests.
        self.finished_processing.emit(summary)

    def run(self):
        summary = {
            "total": len(self.pdf_files),
            "processed": 0,
            "success": 0,
            "filename_only_success": 0,
            "skipped": 0,
            "failed": 0,
            "failed_files": [],
            "cancelled_jobs": 0,
            "cancelled": False,
        }

        if self.prevent_sleep:
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(
                    ES_CONTINUOUS | ES_SYSTEM_REQUIRED
                )
                print("Sleep prevention enabled.")
            except Exception as e:
                print(f"Failed to set execution state: {e}")

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)
        futures = set()

        try:
            for i, pdf_path in enumerate(self.pdf_files):
                while self._paused and not self.isInterruptionRequested():
                    self.msleep(100)

                if self.isInterruptionRequested():
                    summary["cancelled"] = True
                    break

                # Keep at most max_workers submitted. Use a timed wait so a
                # cancellation request is observed even while every worker is
                # blocked in an API call.
                while len(futures) >= self.max_workers:
                    if self.isInterruptionRequested():
                        summary["cancelled"] = True
                        break
                    done, pending = concurrent.futures.wait(
                        futures,
                        timeout=0.2,
                        return_when=concurrent.futures.FIRST_COMPLETED,
                    )
                    if done:
                        futures = pending
                        self._process_futures_results(done, summary)

                if summary["cancelled"] or self.isInterruptionRequested():
                    summary["cancelled"] = True
                    break

                future = executor.submit(
                    self._process_single_file, pdf_path, i, summary["total"]
                )
                futures.add(future)

            # Drain normally, or transition into cancellation as soon as it is
            # requested. No finished signal is emitted until this set is empty.
            while futures and not summary["cancelled"]:
                if self.isInterruptionRequested():
                    summary["cancelled"] = True
                    break
                done, pending = concurrent.futures.wait(
                    futures,
                    timeout=0.2,
                    return_when=concurrent.futures.FIRST_COMPLETED,
                )
                if done:
                    futures = pending
                    self._process_futures_results(done, summary)

            if summary["cancelled"] or self.isInterruptionRequested():
                summary["cancelled"] = True
                for future in futures:
                    future.cancel()

                # Pending work is cancelled immediately. Running jobs cannot be
                # killed safely; they cooperate at extraction/API/retry/save
                # boundaries and we wait here in the worker thread (not GUI).
                executor.shutdown(wait=True, cancel_futures=True)

                completed_after_cancel = {
                    future for future in futures
                    if future.done() and not future.cancelled()
                }
                self._process_futures_results(completed_after_cancel, summary)
                futures.clear()
            else:
                executor.shutdown(wait=True)

        finally:
            # shutdown is idempotent; this also covers unexpected exceptions in
            # queue management while preserving the "finished means no writers"
            # guarantee.
            try:
                executor.shutdown(wait=True, cancel_futures=True)
            except TypeError:
                executor.shutdown(wait=True)

            if self.prevent_sleep:
                try:
                    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
                    print("Sleep prevention released.")
                except Exception as e:
                    print(f"Failed to release execution state: {e}")

            self.finished_processing.emit(summary)

    def _process_futures_results(self, done_futures, summary):
        for f in done_futures:
            if f.cancelled():
                continue
            try:
                res = f.result()
                # res is dict: {status: 'success'|'skipped'|'failed', filename: str, reason: str, type: str}
                
                self._mutex.lock()
                try:
                    if res['status'] == 'cancelled':
                        summary['cancelled'] = True
                        continue
                    if res['status'] == 'cancelled':
                        summary['cancelled_jobs'] += 1
                        summary['cancelled'] = True
                    elif res['status'] == 'skipped':
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

    def _cancelled_result(self, basename):
        return {'status': 'cancelled', 'filename': basename}

    def _interruptible_sleep(self, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.isInterruptionRequested():
                return False
            time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
        return not self.isInterruptionRequested()

    def _process_single_file(self, pdf_path, idx, total_count):
        basename = os.path.basename(pdf_path)
        self.progress_update.emit(idx + 1, total_count, basename)

        if self.isInterruptionRequested():
            return self._cancelled_result(basename)

        ris_path = os.path.splitext(pdf_path)[0] + ".ris"
        if self.skip_existing and os.path.exists(ris_path):
            self.progress_update.emit(idx + 1, total_count, f"{basename} (Skipped)")
            return {'status': 'skipped', 'filename': basename}

        part_path = ris_path + ".part"

        try:
            if self.isInterruptionRequested():
                return self._cancelled_result(basename)

            # 1. Extraction. The extractor itself may be blocking, so cancellation
            # is observed immediately before and after it.
            text = extract_text_from_pdf(pdf_path)
            if self.isInterruptionRequested():
                return self._cancelled_result(basename)

            use_filename_mode = not text.strip()
            if use_filename_mode:
                text = ""

            # 2. Gemini API with retry. An in-flight HTTP/API call is allowed to
            # return safely; its result is discarded after STOP and never saved.
            data = None
            max_retries = 2

            for attempt in range(max_retries + 1):
                if self.isInterruptionRequested():
                    return self._cancelled_result(basename)
                try:
                    data = generate_ris_data(
                        text_context=text,
                        filename=basename,
                        api_key=self.api_key,
                        model_name=self.model_name,
                        filename_mode=use_filename_mode,
                    )
                    if self.isInterruptionRequested():
                        return self._cancelled_result(basename)

                    if data:
                        break
                    if attempt < max_retries:
                        if not self._interruptible_sleep(2 ** attempt + random.random()):
                            return self._cancelled_result(basename)
                        continue
                    raise Exception("AI_NULL")

                except Exception as e:
                    if self.isInterruptionRequested():
                        return self._cancelled_result(basename)

                    err_str = str(e)
                    is_retryable = (
                        "429" in err_str
                        or "500" in err_str
                        or "503" in err_str
                        or "504" in err_str
                        or "ResourceExhausted" in err_str
                        or "DeadlineExceeded" in err_str
                        or "AI_EMPTY_RESPONSE" in err_str
                        or "AI_NULL" in err_str
                    )

                    if is_retryable and attempt < max_retries:
                        sleep_time = (2 ** attempt) + (random.random() * 1.5)
                        print(
                            f"Retry {attempt+1}/{max_retries} for "
                            f"{basename}: {err_str}"
                        )
                        if not self._interruptible_sleep(sleep_time):
                            return self._cancelled_result(basename)
                        continue

                    if "429" in err_str or "ResourceExhausted" in err_str:
                        raise Exception("RATE_LIMIT")
                    if (
                        "500" in err_str
                        or "503" in err_str
                        or "504" in err_str
                        or "DeadlineExceeded" in err_str
                    ):
                        raise Exception("TIMEOUT")
                    if "AI_EMPTY_RESPONSE" in err_str or "AI_NULL" in err_str:
                        raise Exception("AI_EMPTY_RESPONSE")
                    raise

            # 3. Post-processing.
            if not data:
                raise Exception("AI_NULL")
            if self.isInterruptionRequested():
                return self._cancelled_result(basename)

            has_ti = data.get("TI", {}).get("value")
            has_au = data.get("AU")
            if not has_ti and not has_au:
                raise Exception("AI_NULL" if not use_filename_mode else "OCR_REQUIRED")

            success_type = "normal"
            if use_filename_mode:
                note_val = "OCR_REQUIRED"
                missing_fields = []
                if not has_au:
                    missing_fields.append("AU")
                if not data.get("PY", {}).get("value"):
                    missing_fields.append("PY")
                if missing_fields:
                    note_val += f" (CHECK: {','.join(missing_fields)} missing)"
                if "N1" not in data:
                    data["N1"] = {}
                data["N1"]["value"] = note_val
                success_type = "filename_only"
                if not has_ti:
                    raise Exception("OCR_REQUIRED")

            ris_content = dict_to_ris(data)
            if self.isInterruptionRequested():
                return self._cancelled_result(basename)

            # Write to a temporary sibling first. A cancellation before the
            # atomic replace leaves any previously completed RIS untouched.
            if os.path.exists(part_path):
                os.remove(part_path)
            with open(part_path, "w", encoding="utf-8") as f:
                f.write(ris_content)
                f.flush()
                os.fsync(f.fileno())

            if self.isInterruptionRequested():
                try:
                    os.remove(part_path)
                except OSError:
                    pass
                return self._cancelled_result(basename)

            os.replace(part_path, ris_path)
            return {
                'status': 'success',
                'filename': basename,
                'type': success_type,
            }

        except Exception as e:
            msg = str(e)
            if "OCR_REQUIRED" in msg:
                code = "OCR_REQUIRED"
            elif "RATE_LIMIT" in msg:
                code = "RATE_LIMIT"
            elif "TIMEOUT" in msg:
                code = "TIMEOUT"
            elif "AI_NULL" in msg:
                code = "AI_NULL"
            elif "AI_EMPTY_RESPONSE" in msg:
                code = "AI_EMPTY_RESPONSE"
            elif "Permission" in msg:
                code = "WRITE_FAILED"
            else:
                code = f"API_ERROR: {msg}"

            return {'status': 'failed', 'filename': basename, 'reason': code}
        finally:
            if os.path.exists(part_path):
                try:
                    os.remove(part_path)
                except OSError:
                    pass
