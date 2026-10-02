import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from src import worker as worker_module
from src.worker import ProcessingWorker


class CapturingWorker(ProcessingWorker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.finished_summaries = []

    def _emit_finished(self, summary):
        self.finished_summaries.append(dict(summary))


class CancellationLifecycleTests(unittest.TestCase):
    def _pdfs(self, root, count=1):
        paths = []
        for i in range(count):
            path = Path(root) / f"doc{i}.pdf"
            path.write_bytes(b"%PDF-dummy")
            paths.append(str(path))
        return paths

    def _valid_data(self):
        return {"TI": {"value": "Title"}, "AU": ["Author"]}

    def test_cancel_while_api_waits_emits_finished_only_after_api_returns(self):
        with tempfile.TemporaryDirectory() as td:
            pdf = self._pdfs(td)[0]
            worker = CapturingWorker([pdf], "key", "model", max_workers=1)
            api_started = threading.Event()
            release_api = threading.Event()

            def slow_api(**kwargs):
                api_started.set()
                self.assertTrue(release_api.wait(timeout=3))
                return self._valid_data()

            with patch.object(worker_module, "extract_text_from_pdf", return_value="text"),                  patch.object(worker_module, "generate_ris_data", side_effect=slow_api),                  patch.object(worker_module, "dict_to_ris", return_value="TY  - JOUR\nER  - \n"):
                coordinator = threading.Thread(target=worker.run)
                coordinator.start()
                self.assertTrue(api_started.wait(timeout=2))

                worker.request_cancel()
                time.sleep(0.1)
                self.assertEqual(worker.finished_summaries, [])
                self.assertFalse(Path(pdf).with_suffix(".ris").exists())

                release_api.set()
                coordinator.join(timeout=3)

            self.assertFalse(coordinator.is_alive())
            self.assertEqual(len(worker.finished_summaries), 1)
            self.assertTrue(worker.finished_summaries[0]["cancelled"])
            self.assertFalse(Path(pdf).with_suffix(".ris").exists())

    def test_cancel_stops_new_jobs_from_being_submitted(self):
        with tempfile.TemporaryDirectory() as td:
            pdfs = self._pdfs(td, 2)
            worker = CapturingWorker(pdfs, "key", "model", max_workers=1)
            first_started = threading.Event()
            release_first = threading.Event()
            extracted = []

            def extract(path):
                extracted.append(os.path.basename(path))
                return "text"

            def api(**kwargs):
                first_started.set()
                release_first.wait(timeout=3)
                return self._valid_data()

            with patch.object(worker_module, "extract_text_from_pdf", side_effect=extract),                  patch.object(worker_module, "generate_ris_data", side_effect=api),                  patch.object(worker_module, "dict_to_ris", return_value="RIS"):
                coordinator = threading.Thread(target=worker.run)
                coordinator.start()
                self.assertTrue(first_started.wait(timeout=2))
                worker.request_cancel()
                release_first.set()
                coordinator.join(timeout=3)

            self.assertEqual(extracted, ["doc0.pdf"])
            self.assertTrue(worker.finished_summaries[0]["cancelled"])
            self.assertFalse(Path(pdfs[1]).with_suffix(".ris").exists())

    def test_cancel_before_save_does_not_write_completed_ris(self):
        with tempfile.TemporaryDirectory() as td:
            pdf = self._pdfs(td)[0]
            worker = CapturingWorker([pdf], "key", "model", max_workers=1)

            def api_then_cancel(**kwargs):
                worker.request_cancel()
                return self._valid_data()

            with patch.object(worker_module, "extract_text_from_pdf", return_value="text"),                  patch.object(worker_module, "generate_ris_data", side_effect=api_then_cancel),                  patch.object(worker_module, "dict_to_ris", return_value="RIS"):
                worker.run()

            self.assertTrue(worker.finished_summaries[0]["cancelled"])
            self.assertFalse(Path(pdf).with_suffix(".ris").exists())
            self.assertFalse(Path(str(Path(pdf).with_suffix(".ris")) + ".tmp").exists())

    def test_normal_completion_writes_once_before_finished(self):
        with tempfile.TemporaryDirectory() as td:
            pdf = self._pdfs(td)[0]
            ris = Path(pdf).with_suffix(".ris")
            worker = CapturingWorker([pdf], "key", "model", max_workers=1)

            with patch.object(worker_module, "extract_text_from_pdf", return_value="text"),                  patch.object(worker_module, "generate_ris_data", return_value=self._valid_data()),                  patch.object(worker_module, "dict_to_ris", return_value="TY  - JOUR\nER  - \n"):
                worker.run()

            self.assertTrue(ris.exists())
            self.assertEqual(ris.read_text(encoding="utf-8"), "TY  - JOUR\nER  - \n")
            self.assertEqual(len(worker.finished_summaries), 1)
            summary = worker.finished_summaries[0]
            self.assertFalse(summary["cancelled"])
            self.assertEqual(summary["success"], 1)
            self.assertEqual(summary["processed"], 1)


if __name__ == "__main__":
    unittest.main()
