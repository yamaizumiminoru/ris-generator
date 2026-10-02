import threading
import time
from pathlib import Path

import pytest

import src.worker as worker_module
from src.worker import ProcessingWorker


class ControlledWorker(ProcessingWorker):
    def __init__(self, *args, cancel_event, **kwargs):
        super().__init__(*args, **kwargs)
        self._test_cancel_event = cancel_event

    def isInterruptionRequested(self):
        return self._test_cancel_event.is_set()


def make_worker(tmp_path, count=1, max_workers=1):
    files = []
    for i in range(count):
        path = Path(tmp_path) / f"doc{i}.pdf"
        path.write_bytes(b"dummy")
        files.append(str(path))
    cancel_event = threading.Event()
    worker = ControlledWorker(
        files,
        "dummy-key",
        "dummy-model",
        prevent_sleep=False,
        max_workers=max_workers,
        cancel_event=cancel_event,
    )
    return worker, cancel_event, files


def valid_data():
    return {
        "TI": {"value": "Title"},
        "AU": [{"value": "Author"}],
        "PY": {"value": "2026"},
    }


def run_in_thread(worker):
    thread = threading.Thread(target=worker.run)
    thread.start()
    return thread


def test_cancel_while_api_running_waits_before_finished_and_never_saves(
    tmp_path, monkeypatch
):
    worker, cancel, files = make_worker(tmp_path, count=2, max_workers=1)
    api_started = threading.Event()
    api_release = threading.Event()
    calls = []

    monkeypatch.setattr(worker_module, "extract_text_from_pdf", lambda _: "text")

    def fake_generate(**kwargs):
        calls.append(kwargs["filename"])
        api_started.set()
        assert api_release.wait(2)
        return valid_data()

    monkeypatch.setattr(worker_module, "generate_ris_data", fake_generate)
    monkeypatch.setattr(worker_module, "dict_to_ris", lambda _: "TY  - JOUR\nER  -\n")

    thread = run_in_thread(worker)
    assert api_started.wait(1)
    cancel.set()

    time.sleep(0.05)
    assert thread.is_alive(), "worker reported completion while API job was still running"
    assert worker.last_summary is None

    api_release.set()
    thread.join(2)
    assert not thread.is_alive()
    assert worker.last_summary["cancelled"] is True
    assert calls == ["doc0.pdf"], "new work was submitted after cancellation"
    assert not Path(files[0]).with_suffix(".ris").exists()
    assert not Path(files[1]).with_suffix(".ris").exists()

    # finished truly means there are no writers left.
    time.sleep(0.05)
    assert not list(Path(tmp_path).glob("*.ris"))


def test_cancel_during_retry_wait_is_interruptible(tmp_path, monkeypatch):
    worker, cancel, files = make_worker(tmp_path)
    called = threading.Event()

    monkeypatch.setattr(worker_module, "extract_text_from_pdf", lambda _: "text")

    def rate_limited(**kwargs):
        called.set()
        raise Exception("429 ResourceExhausted")

    monkeypatch.setattr(worker_module, "generate_ris_data", rate_limited)

    thread = run_in_thread(worker)
    assert called.wait(1)
    cancel.set()
    thread.join(2)

    assert not thread.is_alive()
    assert worker.last_summary["cancelled"] is True
    assert not Path(files[0]).with_suffix(".ris").exists()


def test_cancel_after_api_before_save_discards_result(tmp_path, monkeypatch):
    worker, cancel, files = make_worker(tmp_path)

    monkeypatch.setattr(worker_module, "extract_text_from_pdf", lambda _: "text")
    monkeypatch.setattr(worker_module, "generate_ris_data", lambda **_: valid_data())

    def cancel_at_save_boundary(_):
        cancel.set()
        return "TY  - JOUR\nER  -\n"

    monkeypatch.setattr(worker_module, "dict_to_ris", cancel_at_save_boundary)

    worker.run()

    assert worker.last_summary["cancelled"] is True
    assert not Path(files[0]).with_suffix(".ris").exists()
    assert not Path(str(Path(files[0]).with_suffix(".ris")) + ".part").exists()


def test_normal_completion_atomically_saves_ris(tmp_path, monkeypatch):
    worker, cancel, files = make_worker(tmp_path)

    monkeypatch.setattr(worker_module, "extract_text_from_pdf", lambda _: "text")
    monkeypatch.setattr(worker_module, "generate_ris_data", lambda **_: valid_data())
    monkeypatch.setattr(
        worker_module, "dict_to_ris", lambda _: "TY  - JOUR\nTI  - Title\nER  -\n"
    )

    worker.run()

    ris = Path(files[0]).with_suffix(".ris")
    assert ris.read_text(encoding="utf-8").startswith("TY  - JOUR")
    assert not Path(str(ris) + ".part").exists()
    assert worker.last_summary["cancelled"] is False
    assert worker.last_summary["success"] == 1


def test_completed_ris_is_preserved_when_skipping(tmp_path, monkeypatch):
    worker, cancel, files = make_worker(tmp_path)
    ris = Path(files[0]).with_suffix(".ris")
    ris.write_text("existing", encoding="utf-8")
    worker.set_skip_existing(True)

    monkeypatch.setattr(
        worker_module,
        "generate_ris_data",
        lambda **_: pytest.fail("API must not run for an existing RIS"),
    )

    worker.run()

    assert ris.read_text(encoding="utf-8") == "existing"
    assert worker.last_summary["skipped"] == 1
