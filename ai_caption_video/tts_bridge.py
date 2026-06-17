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
PORTABLE_TTS_MODEL_DIR = APP_DIR / "models" / "Qwen3-TTS-1.7B"
LEGACY_TTS_MODEL_DIR = Path("E:/Qwen3-TTS-1.7B/Qwen3-TTS-1.7B")
DEFAULT_TTS_MODEL_DIR = PORTABLE_TTS_MODEL_DIR if PORTABLE_TTS_MODEL_DIR.exists() else LEGACY_TTS_MODEL_DIR
TTS_HELPER_PATH = Path("D:/Codex/cache/tmp/ai_caption_video_qwen_tts_helper.py")
RESULT_PREFIX = "__AI_CAPTION_QWEN_RESULT__ "


@dataclass(frozen=True)
class TTSOptions:
    model_dir: Path
    mode: str = "preset"
    speaker: str = "Vivian"
    language: str = "Chinese"
    model_size: str = "1.7B"
    instruct: str = ""
    ref_audio: Path | None = None
    ref_text: str = ""
    use_xvector_only: bool = False


class QwenTTSWorker:
    def __init__(self, model_dir: Path) -> None:
        self.model_dir = Path(model_dir)
        self.python_exe = self.model_dir / "conda_env" / "python.exe"
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
                    raise RuntimeError("Qwen-TTS 后台进程已退出：\n" + "\n".join(logs[-40:]))
                line = line.rstrip()
                if line.startswith(RESULT_PREFIX):
                    result = json.loads(line[len(RESULT_PREFIX) :])
                    if not result.get("ok"):
                        raise RuntimeError(result.get("error") or "未知 Qwen-TTS 错误")
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
        if not self.model_dir.exists():
            raise FileNotFoundError(f"TTS 模型目录不存在：{self.model_dir}")
        if not self.python_exe.exists():
            raise FileNotFoundError(f"找不到模型自带 Python：{self.python_exe}")

        _ensure_helper_script()
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW

        self.process = subprocess.Popen(
            [str(self.python_exe), "-u", str(TTS_HELPER_PATH), "--worker"],
            cwd=str(self.model_dir),
            env=_tts_env(self.model_dir),
            text=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )


_workers: dict[str, QwenTTSWorker] = {}
_workers_lock = threading.Lock()


def generate_tts_audio(texts: list[str], output_dir: Path, options: TTSOptions) -> list[Path]:
    if not texts:
        return []

    model_dir = resolve_qwen_model_dir(options.model_dir)
    python_exe = model_dir / "conda_env" / "python.exe"
    if not model_dir.exists():
        raise FileNotFoundError(f"TTS 模型目录不存在：{model_dir}")
    if not python_exe.exists():
        raise FileNotFoundError(f"找不到模型自带 Python：{python_exe}")

    output_dir.mkdir(parents=True, exist_ok=True)
    _ensure_helper_script()

    request = {
        "model_dir": str(model_dir),
        "output_dir": str(output_dir),
        "texts": texts,
        "mode": options.mode,
        "speaker": options.speaker,
        "language": options.language,
        "model_size": options.model_size,
        "instruct": options.instruct,
        "ref_audio": str(options.ref_audio) if options.ref_audio else "",
        "ref_text": options.ref_text,
        "use_xvector_only": options.use_xvector_only,
    }

    request_path = output_dir / "tts_request.json"
    result_path = output_dir / "tts_result.json"
    with open(request_path, "w", encoding="utf-8") as f:
        json.dump(request, f, ensure_ascii=False, indent=2)

    worker = _get_worker(model_dir)
    try:
        worker.request(request_path, result_path)
    except Exception as exc:
        raise RuntimeError(f"Qwen-TTS 生成失败：\n{exc}") from exc

    with open(result_path, "r", encoding="utf-8") as f:
        result = json.load(f)

    audio_paths = [Path(item["path"]) for item in result.get("items", [])]
    missing = [str(path) for path in audio_paths if not path.exists()]
    if missing:
        raise RuntimeError("TTS 输出文件缺失：\n" + "\n".join(missing))
    return audio_paths


def shutdown_qwen_tts_workers() -> None:
    with _workers_lock:
        workers = list(_workers.values())
        _workers.clear()
    for worker in workers:
        worker.terminate()


def resolve_qwen_model_dir(preferred: Path | str | None = None) -> Path:
    portable = PORTABLE_TTS_MODEL_DIR
    if _is_qwen_model_dir(portable):
        return portable
    if preferred:
        preferred_path = Path(preferred)
        if _is_qwen_model_dir(preferred_path):
            return preferred_path
    return LEGACY_TTS_MODEL_DIR


def _get_worker(model_dir: Path) -> QwenTTSWorker:
    key = str(Path(model_dir).resolve()).lower()
    with _workers_lock:
        if key not in _workers:
            _workers[key] = QwenTTSWorker(model_dir)
        return _workers[key]


def _is_qwen_model_dir(path: Path) -> bool:
    return (
        path.exists()
        and (path / "conda_env" / "python.exe").exists()
        and (path / "Qwen").exists()
        and (path / "qwen_tts").exists()
    )


def _tts_env(model_dir: Path) -> dict[str, str]:
    env = dict(**__import__("os").environ)
    conda_env = model_dir / "conda_env"
    paths = [
        conda_env,
        conda_env / "Scripts",
        conda_env / "ffmpeg" / "bin",
        conda_env / "sox",
    ]
    env["PATH"] = ";".join(str(path) for path in paths) + ";" + env.get("PATH", "")
    env["PYTHONHOME"] = ""
    env["PYTHONPATH"] = ""
    env["HF_HOME"] = str(model_dir / "hf_download")
    return env


def _ensure_helper_script() -> None:
    TTS_HELPER_PATH.parent.mkdir(parents=True, exist_ok=True)
    TTS_HELPER_PATH.write_text(_HELPER_CODE, encoding="utf-8")


atexit.register(shutdown_qwen_tts_workers)


_HELPER_CODE = r'''
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback

import numpy as np
import soundfile as sf
import torch

RESULT_PREFIX = "__AI_CAPTION_QWEN_RESULT__ "
loaded_models = {}


def normalize_audio(wav):
    x = np.asarray(wav)
    if np.issubdtype(x.dtype, np.integer):
        info = np.iinfo(x.dtype)
        if info.min < 0:
            y = x.astype(np.float32) / max(abs(info.min), info.max)
        else:
            mid = (info.max + 1) / 2.0
            y = (x.astype(np.float32) - mid) / mid
    else:
        y = x.astype(np.float32)
        m = np.max(np.abs(y)) if y.size else 0.0
        if m > 1.0 + 1e-6:
            y = y / (m + 1e-12)
    if y.ndim > 1:
        y = np.mean(y, axis=-1).astype(np.float32)
    return np.clip(y, -1.0, 1.0)


def load_ref_audio(path):
    import librosa

    wav, sr = librosa.load(path, sr=None, mono=True)
    return normalize_audio(wav), int(sr)


def get_model(model_dir, mode, model_size):
    from qwen_tts import Qwen3TTSModel

    model_type = {
        "preset": "CustomVoice",
        "voice_design": "VoiceDesign",
        "voice_clone": "Base",
    }.get(mode, "CustomVoice")
    resolved_size = "1.7B" if mode == "voice_design" else model_size
    key = (str(model_dir), model_type, resolved_size)
    if key in loaded_models:
        return loaded_models[key]

    model_path = model_dir / "Qwen" / f"Qwen3-TTS-12Hz-{resolved_size}-{model_type}"
    if not model_path.exists():
        raise FileNotFoundError(f"Model path not found: {model_path}")

    use_cuda = torch.cuda.is_available()
    loaded_models[key] = Qwen3TTSModel.from_pretrained(
        str(model_path),
        device_map="cuda" if use_cuda else "cpu",
        dtype=torch.bfloat16 if use_cuda else torch.float32,
    )
    return loaded_models[key]


def process_request(request_path, result_path):
    request = json.loads(Path(request_path).read_text(encoding="utf-8"))

    model_dir = Path(request["model_dir"]).resolve()
    output_dir = Path(request["output_dir"]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(model_dir)
    sys.path.insert(0, str(model_dir))

    mode = request.get("mode") or "preset"
    tts = get_model(model_dir, mode, request["model_size"])

    items = []
    speaker = request["speaker"].lower().replace(" ", "_")
    language = request["language"]
    instruct = request.get("instruct") or None
    ref_audio_path = request.get("ref_audio") or ""
    ref_text = request.get("ref_text") or None
    use_xvector_only = bool(request.get("use_xvector_only"))

    ref_audio = None
    if mode == "voice_clone":
        if not ref_audio_path:
            raise ValueError("Voice clone requires reference audio.")
        ref_audio = load_ref_audio(ref_audio_path)
        if not use_xvector_only and not ref_text:
            raise ValueError("Voice clone requires reference text unless x-vector only is enabled.")

    for index, text in enumerate(request["texts"], start=1):
        if mode == "voice_design":
            if not instruct:
                raise ValueError("Voice design requires a voice description.")
            wavs, sr = tts.generate_voice_design(
                text=text.strip(),
                language=language,
                instruct=instruct,
                non_streaming_mode=True,
                max_new_tokens=2048,
            )
        elif mode == "voice_clone":
            wavs, sr = tts.generate_voice_clone(
                text=text.strip(),
                language=language,
                ref_audio=ref_audio,
                ref_text=ref_text,
                x_vector_only_mode=use_xvector_only,
                max_new_tokens=2048,
            )
        else:
            wavs, sr = tts.generate_custom_voice(
                text=text.strip(),
                language=language,
                speaker=speaker,
                instruct=instruct,
                non_streaming_mode=True,
                max_new_tokens=2048,
            )
        audio = normalize_audio(wavs[0])
        path = output_dir / f"tts_{index:04d}.wav"
        sf.write(str(path), audio, int(sr))
        items.append({"index": index, "path": str(path), "sample_rate": int(sr)})

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
    request_path = Path(sys.argv[1])
    result_path = Path(sys.argv[2])
    process_request(request_path, result_path)


if __name__ == "__main__":
    main()
'''
