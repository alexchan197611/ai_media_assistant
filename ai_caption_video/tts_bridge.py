from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
import tempfile


DEFAULT_TTS_MODEL_DIR = Path("E:/Qwen3-TTS-1.7B/Qwen3-TTS-1.7B")
TTS_HELPER_PATH = Path("D:/Codex/cache/tmp/ai_caption_video_qwen_tts_helper.py")


@dataclass(frozen=True)
class TTSOptions:
    model_dir: Path
    speaker: str = "Vivian"
    language: str = "Chinese"
    model_size: str = "1.7B"
    instruct: str = ""


def generate_tts_audio(texts: list[str], output_dir: Path, options: TTSOptions) -> list[Path]:
    if not texts:
        return []

    model_dir = Path(options.model_dir)
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
        "speaker": options.speaker,
        "language": options.language,
        "model_size": options.model_size,
        "instruct": options.instruct,
    }

    request_path = output_dir / "tts_request.json"
    result_path = output_dir / "tts_result.json"
    with open(request_path, "w", encoding="utf-8") as f:
        json.dump(request, f, ensure_ascii=False, indent=2)

    env = _tts_env(model_dir)
    completed = subprocess.run(
        [str(python_exe), str(TTS_HELPER_PATH), str(request_path), str(result_path)],
        cwd=str(model_dir),
        env=env,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "未知 TTS 错误"
        raise RuntimeError(f"TTS 生成失败：\n{message}")

    with open(result_path, "r", encoding="utf-8") as f:
        result = json.load(f)

    audio_paths = [Path(item["path"]) for item in result.get("items", [])]
    missing = [str(path) for path in audio_paths if not path.exists()]
    if missing:
        raise RuntimeError("TTS 输出文件缺失：\n" + "\n".join(missing))
    return audio_paths


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


_HELPER_CODE = r'''
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import numpy as np
import soundfile as sf
import torch


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


def main():
    request_path = Path(sys.argv[1])
    result_path = Path(sys.argv[2])
    request = json.loads(request_path.read_text(encoding="utf-8"))

    model_dir = Path(request["model_dir"]).resolve()
    output_dir = Path(request["output_dir"]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(model_dir)
    sys.path.insert(0, str(model_dir))

    from qwen_tts import Qwen3TTSModel

    model_path = model_dir / "Qwen" / f"Qwen3-TTS-12Hz-{request['model_size']}-CustomVoice"
    if not model_path.exists():
        raise FileNotFoundError(f"Model path not found: {model_path}")

    use_cuda = torch.cuda.is_available()
    tts = Qwen3TTSModel.from_pretrained(
        str(model_path),
        device_map="cuda" if use_cuda else "cpu",
        dtype=torch.bfloat16 if use_cuda else torch.float32,
    )

    items = []
    speaker = request["speaker"].lower().replace(" ", "_")
    language = request["language"]
    instruct = request.get("instruct") or None

    for index, text in enumerate(request["texts"], start=1):
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

    result_path.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
'''
