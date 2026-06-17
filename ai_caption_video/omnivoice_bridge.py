from __future__ import annotations

import atexit
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import threading


FROZEN = getattr(sys, "frozen", False)
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parents[1]
PORTABLE_OMNIVOICE_DIR = APP_DIR / "models" / "OmniVoice"
WORKSPACE_OMNIVOICE_DIR = Path("D:/Codex/workspaces/OmniVoice")
DEFAULT_OMNIVOICE_DIR = PORTABLE_OMNIVOICE_DIR if PORTABLE_OMNIVOICE_DIR.exists() else WORKSPACE_OMNIVOICE_DIR
OMNIVOICE_HELPER_PATH = Path("D:/Codex/cache/tmp/ai_caption_video_omnivoice_helper.py")
RESULT_PREFIX = "__AI_CAPTION_OMNIVOICE_RESULT__ "


@dataclass(frozen=True)
class OmniVoiceOptions:
    project_dir: Path
    python_exe: Path
    mode: str = "auto"
    ref_audio: Path | None = None
    ref_text: str = ""
    instruct: str = ""
    speed: float = 1.0
    num_step: int = 16


class OmniVoiceWorker:
    def __init__(self, project_dir: Path, python_exe: Path) -> None:
        self.project_dir = Path(project_dir)
        self.python_exe = Path(python_exe)
        self.process: subprocess.Popen[str] | None = None
        self.lock = threading.Lock()

    def request(self, request_path: Path, result_path: Path) -> None:
        with self.lock:
            self._ensure_process()
            assert self.process is not None
            assert self.process.stdin is not None
            assert self.process.stdout is not None

            payload = {"request_path": str(request_path), "result_path": str(result_path)}
            self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self.process.stdin.flush()

            logs: list[str] = []
            while True:
                line = self.process.stdout.readline()
                if line == "":
                    raise RuntimeError("OmniVoice 后台进程已退出：\n" + "\n".join(logs[-40:]))
                line = line.rstrip()
                if line.startswith(RESULT_PREFIX):
                    result = json.loads(line[len(RESULT_PREFIX) :])
                    if not result.get("ok"):
                        raise RuntimeError(result.get("error") or "未知 OmniVoice 错误")
                    return
                if line:
                    logs.append(line)

    def terminate(self) -> None:
        with self.lock:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            self.process = None

    def _ensure_process(self) -> None:
        if self.process and self.process.poll() is None:
            return
        if not self.project_dir.exists():
            raise FileNotFoundError(f"OmniVoice 项目目录不存在：{self.project_dir}")
        if not self.python_exe.exists():
            raise FileNotFoundError(f"OmniVoice Python 不存在：{self.python_exe}")

        _ensure_helper_script()
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW

        self.process = subprocess.Popen(
            [str(self.python_exe), "-u", str(OMNIVOICE_HELPER_PATH), "--worker"],
            cwd=str(self.project_dir),
            env=_omnivoice_env(self.project_dir),
            text=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )


_workers: dict[str, OmniVoiceWorker] = {}
_workers_lock = threading.Lock()


def default_omnivoice_python(project_dir: Path = DEFAULT_OMNIVOICE_DIR) -> Path:
    candidates = [
        project_dir / ".python" / "python.exe",
        project_dir / ".venv" / "Scripts" / "python.exe",
        project_dir / "venv" / "Scripts" / "python.exe",
        project_dir / "python.exe",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def resolve_omnivoice_dir(preferred: Path | str | None = None) -> Path:
    if _is_omnivoice_dir(PORTABLE_OMNIVOICE_DIR):
        return PORTABLE_OMNIVOICE_DIR
    if preferred and _is_omnivoice_dir(Path(preferred)):
        return Path(preferred)
    return WORKSPACE_OMNIVOICE_DIR


def generate_omnivoice_audio(texts: list[str], output_dir: Path, options: OmniVoiceOptions) -> list[Path]:
    if not texts:
        return []

    project_dir = resolve_omnivoice_dir(options.project_dir)
    python_exe = Path(options.python_exe)
    if _is_omnivoice_dir(project_dir):
        python_exe = default_omnivoice_python(project_dir) if not python_exe.exists() else python_exe
    if not project_dir.exists():
        raise FileNotFoundError(f"OmniVoice 项目目录不存在：{project_dir}")
    if not python_exe.exists():
        raise FileNotFoundError(f"OmniVoice Python 不存在：{python_exe}")
    if options.mode == "clone" and (not options.ref_audio or not options.ref_audio.exists()):
        raise FileNotFoundError(f"OmniVoice 参考音频不存在：{options.ref_audio}")

    output_dir.mkdir(parents=True, exist_ok=True)
    request = {
        "output_dir": str(output_dir),
        "texts": texts,
        "mode": options.mode,
        "ref_audio": str(options.ref_audio) if options.ref_audio else "",
        "ref_text": options.ref_text,
        "instruct": options.instruct,
        "speed": options.speed,
        "num_step": options.num_step,
    }
    request_path = output_dir / "omnivoice_request.json"
    result_path = output_dir / "omnivoice_result.json"
    request_path.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")

    worker = _get_worker(project_dir, python_exe)
    try:
        worker.request(request_path, result_path)
    except Exception as exc:
        raise RuntimeError(f"OmniVoice 生成失败：\n{exc}") from exc

    result = json.loads(result_path.read_text(encoding="utf-8"))
    audio_paths = [Path(item["path"]) for item in result.get("items", [])]
    missing = [str(path) for path in audio_paths if not path.exists()]
    if missing:
        raise RuntimeError("OmniVoice 输出文件缺失：\n" + "\n".join(missing))
    return audio_paths


def shutdown_omnivoice_workers() -> None:
    with _workers_lock:
        workers = list(_workers.values())
        _workers.clear()
    for worker in workers:
        worker.terminate()


def _get_worker(project_dir: Path, python_exe: Path) -> OmniVoiceWorker:
    key = str(project_dir.resolve()).lower() + "|" + str(python_exe.resolve()).lower()
    with _workers_lock:
        if key not in _workers:
            _workers[key] = OmniVoiceWorker(project_dir, python_exe)
        return _workers[key]


def _is_omnivoice_dir(path: Path) -> bool:
    return path.exists() and (path / "omnivoice").exists()


def _omnivoice_env(project_dir: Path) -> dict[str, str]:
    env = dict(**os.environ)
    venv = project_dir / ".venv"
    site_packages = venv / "Lib" / "site-packages"
    runtime = project_dir / ".python"
    paths = [venv / "Scripts", venv, runtime, site_packages / "torch" / "lib"]
    env["PATH"] = ";".join(str(path) for path in paths) + ";" + env.get("PATH", "")
    env["PYTHONHOME"] = ""
    env["PYTHONPATH"] = ";".join([str(project_dir), str(site_packages)])
    env["HF_HOME"] = str(project_dir / "hf_cache")
    env["HF_HUB_DISABLE_SYMLINKS"] = "1"
    env["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    return env


def _ensure_helper_script() -> None:
    OMNIVOICE_HELPER_PATH.parent.mkdir(parents=True, exist_ok=True)
    OMNIVOICE_HELPER_PATH.write_text(_HELPER_CODE, encoding="utf-8")


atexit.register(shutdown_omnivoice_workers)


_HELPER_CODE = r'''
from __future__ import annotations

import json
from pathlib import Path
import sys
import traceback

import soundfile as sf
import torch
from omnivoice import OmniVoice

RESULT_PREFIX = "__AI_CAPTION_OMNIVOICE_RESULT__ "
model = None


def get_model():
    global model
    if model is None:
        use_cuda = torch.cuda.is_available()
        model = OmniVoice.from_pretrained(
            "k2-fsa/OmniVoice",
            device_map="cuda:0" if use_cuda else "cpu",
            dtype=torch.float16 if use_cuda else torch.float32,
        )
    return model


def process_request(request_path, result_path):
    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    output_dir = Path(request["output_dir"]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    tts = get_model()
    items = []
    mode = request.get("mode") or "auto"
    ref_audio = request.get("ref_audio") or None
    ref_text = request.get("ref_text") or None
    instruct = request.get("instruct") or None
    speed = float(request.get("speed") or 1.0)
    num_step = int(request.get("num_step") or 16)

    for index, text in enumerate(request["texts"], start=1):
        kwargs = {"text": text.strip(), "speed": speed, "num_step": num_step}
        if mode == "clone":
            kwargs["ref_audio"] = ref_audio
            if ref_text:
                kwargs["ref_text"] = ref_text
        elif mode == "design":
            kwargs["instruct"] = instruct or "female, natural, clear"

        audio = tts.generate(**kwargs)
        path = output_dir / f"omnivoice_{index:04d}.wav"
        sf.write(str(path), audio[0], 24000)
        items.append({"index": index, "path": str(path), "sample_rate": 24000})

    Path(result_path).write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8")


def run_worker():
    for line in sys.stdin:
        try:
            payload = json.loads(line)
            process_request(payload["request_path"], payload["result_path"])
            print(RESULT_PREFIX + json.dumps({"ok": True}, ensure_ascii=False), flush=True)
        except Exception:
            print(RESULT_PREFIX + json.dumps({"ok": False, "error": traceback.format_exc()}, ensure_ascii=False), flush=True)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        run_worker()
        return
    process_request(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
'''
