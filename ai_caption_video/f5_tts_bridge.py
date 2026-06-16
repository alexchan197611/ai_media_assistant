from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess


DEFAULT_F5_PROJECT_DIR = Path("D:/Codex/workspaces/F5-TTS")
F5_HELPER_PATH = Path("D:/Codex/cache/tmp/ai_caption_video_f5_tts_helper.py")


@dataclass(frozen=True)
class F5TTSOptions:
    project_dir: Path
    python_exe: Path
    ref_audio: Path
    ref_text: str
    model: str = "F5TTS_v1_Base"
    speed: float = 1.0
    remove_silence: bool = False


def default_f5_python(project_dir: Path = DEFAULT_F5_PROJECT_DIR) -> Path:
    candidates = [
        project_dir / ".venv" / "Scripts" / "python.exe",
        project_dir / "venv" / "Scripts" / "python.exe",
        project_dir / "conda_env" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path("python")


def generate_f5_tts_audio(texts: list[str], output_dir: Path, options: F5TTSOptions) -> list[Path]:
    if not texts:
        return []

    project_dir = Path(options.project_dir)
    python_exe = Path(options.python_exe)
    ref_audio = Path(options.ref_audio)

    if not project_dir.exists():
        raise FileNotFoundError(f"F5-TTS 项目目录不存在：{project_dir}")
    if not (project_dir / "src" / "f5_tts").exists():
        raise FileNotFoundError(f"F5-TTS 项目目录不正确，缺少 src/f5_tts：{project_dir}")
    if not python_exe.exists() and str(python_exe).lower() != "python":
        raise FileNotFoundError(f"F5-TTS Python 不存在：{python_exe}")
    if not ref_audio.exists():
        raise FileNotFoundError(f"F5 参考音频不存在：{ref_audio}")
    if not options.ref_text.strip():
        raise ValueError("F5-TTS 需要填写参考音频对应文本，才能更稳定地克隆音色。")

    output_dir.mkdir(parents=True, exist_ok=True)
    _ensure_helper_script()

    request = {
        "project_dir": str(project_dir),
        "output_dir": str(output_dir),
        "texts": texts,
        "ref_audio": str(ref_audio),
        "ref_text": options.ref_text,
        "model": options.model,
        "speed": options.speed,
        "remove_silence": options.remove_silence,
    }
    request_path = output_dir / "f5_request.json"
    result_path = output_dir / "f5_result.json"
    request_path.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")

    completed = subprocess.run(
        [str(python_exe), str(F5_HELPER_PATH), str(request_path), str(result_path)],
        cwd=str(project_dir),
        env=_f5_env(project_dir),
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "未知 F5-TTS 错误"
        raise RuntimeError(f"F5-TTS 生成失败：\n{message}")

    result = json.loads(result_path.read_text(encoding="utf-8"))
    audio_paths = [Path(item["path"]) for item in result.get("items", [])]
    missing = [str(path) for path in audio_paths if not path.exists()]
    if missing:
        raise RuntimeError("F5-TTS 输出文件缺失：\n" + "\n".join(missing))
    return audio_paths


def _f5_env(project_dir: Path) -> dict[str, str]:
    env = dict(os.environ)
    src_dir = project_dir / "src"
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(src_dir) + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
    env["HF_HOME"] = str(Path("D:/Codex/cache/huggingface"))
    env["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    return env


def _ensure_helper_script() -> None:
    F5_HELPER_PATH.parent.mkdir(parents=True, exist_ok=True)
    F5_HELPER_PATH.write_text(_HELPER_CODE, encoding="utf-8")


_HELPER_CODE = r'''
from __future__ import annotations

import json
from pathlib import Path
import sys

import soundfile as sf
import torch
import torchaudio


def patch_torchaudio_load():
    def soundfile_load(uri, *args, **kwargs):
        data, sample_rate = sf.read(str(uri), dtype="float32", always_2d=True)
        return torch.from_numpy(data.T.copy()), sample_rate

    torchaudio.load = soundfile_load


def main():
    request_path = Path(sys.argv[1])
    result_path = Path(sys.argv[2])
    request = json.loads(request_path.read_text(encoding="utf-8"))

    project_dir = Path(request["project_dir"]).resolve()
    sys.path.insert(0, str(project_dir / "src"))
    patch_torchaudio_load()

    from f5_tts.api import F5TTS

    output_dir = Path(request["output_dir"]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    tts = F5TTS(model=request.get("model") or "F5TTS_v1_Base")
    items = []
    for index, text in enumerate(request["texts"], start=1):
        path = output_dir / f"f5_tts_{index:04d}.wav"
        tts.infer(
            ref_file=request["ref_audio"],
            ref_text=request["ref_text"],
            gen_text=text.strip(),
            speed=float(request.get("speed") or 1.0),
            remove_silence=bool(request.get("remove_silence")),
            file_wave=str(path),
            show_info=lambda *args, **kwargs: None,
            progress=None,
        )
        items.append({"index": index, "path": str(path)})

    result_path.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
'''
