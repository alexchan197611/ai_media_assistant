from __future__ import annotations

import threading
from pathlib import Path

import pytest

from media_core.omnivoice_bridge import OmniVoiceGenerationCancelled, OmniVoiceWorker
from media_core.tts_bridge import QwenTTSWorker, TTSGenerationCancelled


class _FakeStdin:
    def write(self, value: str) -> int:
        return len(value)

    def flush(self) -> None:
        return None


class _BlockingStdout:
    def __init__(self, stopped: threading.Event) -> None:
        self.stopped = stopped

    def readline(self) -> str:
        self.stopped.wait(timeout=5)
        return ""


class _FakeProcess:
    def __init__(self) -> None:
        self.stdin = _FakeStdin()
        self.stopped = threading.Event()
        self.stdout = _BlockingStdout(self.stopped)
        self.terminate_called = False

    def poll(self):
        return None if not self.stopped.is_set() else 0

    def terminate(self) -> None:
        self.terminate_called = True
        self.stopped.set()

    def wait(self, timeout=None):
        self.stopped.wait(timeout=timeout)
        return 0

    def kill(self) -> None:
        self.stopped.set()


def _cancel_after_first_wait():
    calls = {"count": 0}

    def check() -> bool:
        calls["count"] += 1
        return calls["count"] > 1

    return check


def test_qwen_worker_request_terminates_process_when_cancelled(monkeypatch):
    worker = QwenTTSWorker(Path("D:/missing-model"))
    fake_process = _FakeProcess()
    monkeypatch.setattr(worker, "_ensure_process", lambda: setattr(worker, "process", fake_process))

    with pytest.raises(TTSGenerationCancelled):
        worker.request(Path("request.json"), Path("result.json"), cancel_check=_cancel_after_first_wait())

    assert fake_process.terminate_called


def test_omnivoice_worker_request_terminates_process_when_cancelled(monkeypatch):
    worker = OmniVoiceWorker(Path("D:/missing-omnivoice"), Path("python.exe"))
    fake_process = _FakeProcess()
    monkeypatch.setattr(worker, "_ensure_process", lambda: setattr(worker, "process", fake_process))

    with pytest.raises(OmniVoiceGenerationCancelled):
        worker.request(Path("request.json"), Path("result.json"), cancel_check=_cancel_after_first_wait())

    assert fake_process.terminate_called
