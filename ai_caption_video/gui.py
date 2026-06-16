from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import traceback
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .config import DEFAULT_BGM, DEFAULT_INPUT, DEFAULT_OUTPUT_DIR, VideoConfig
from .f5_tts_bridge import DEFAULT_F5_PROJECT_DIR, F5TTSOptions, default_f5_python, generate_f5_tts_audio
from .renderer import TextToken
from .text_utils import load_text
from .tts_bridge import DEFAULT_TTS_MODEL_DIR, TTSOptions, generate_tts_audio
from .video_builder import build_video_from_token_segments


SETTINGS_PATH = Path("D:/Codex/cache/ai_caption_video_settings.json")


class CaptionVideoApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AI Caption Video")
        self.geometry("980x760")
        self.minsize(900, 700)

        self.messages: queue.Queue[tuple[str, str]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.settings = self._load_settings()

        self.output_dir_var = tk.StringVar(value=self._initial_output_dir())
        self.bgm_var = tk.StringVar(value=str(DEFAULT_BGM))
        self.font_var = tk.StringVar(value="")
        self.duration_var = tk.StringVar(value="2.0")
        self.fps_var = tk.StringVar(value="30")
        self.width_var = tk.StringVar(value="1080")
        self.height_var = tk.StringVar(value="1920")
        self.heartbeat_var = tk.StringVar(value=str(self.settings.get("heartbeat_interval_ms", 700)))
        self.tts_enabled_var = tk.BooleanVar(value=bool(self.settings.get("tts_enabled", False)))
        self.tts_engine_var = tk.StringVar(value=str(self.settings.get("tts_engine", "Qwen3-TTS")))
        self.tts_model_dir_var = tk.StringVar(value=str(self.settings.get("tts_model_dir", DEFAULT_TTS_MODEL_DIR)))
        self.tts_speaker_var = tk.StringVar(value=str(self.settings.get("tts_speaker", "Vivian")))
        self.tts_language_var = tk.StringVar(value=str(self.settings.get("tts_language", "Chinese")))
        self.tts_model_size_var = tk.StringVar(value=str(self.settings.get("tts_model_size", "1.7B")))
        self.f5_project_dir_var = tk.StringVar(value=str(self.settings.get("f5_project_dir", DEFAULT_F5_PROJECT_DIR)))
        self.f5_python_var = tk.StringVar(
            value=str(self.settings.get("f5_python", default_f5_python(Path(self.settings.get("f5_project_dir", DEFAULT_F5_PROJECT_DIR)))))
        )
        self.f5_ref_audio_var = tk.StringVar(value=str(self.settings.get("f5_ref_audio", "")))
        self.f5_model_var = tk.StringVar(value=str(self.settings.get("f5_model", "F5TTS_v1_Base")))
        self.f5_speed_var = tk.StringVar(value=str(self.settings.get("f5_speed", "1.0")))
        self.status_var = tk.StringVar(value="准备就绪")

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(150, self._poll_messages)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=(18, 16, 18, 6))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        title = ttk.Label(header, text="AI Caption Video", font=("Microsoft YaHei UI", 18, "bold"))
        title.grid(row=0, column=0, sticky="w")
        subtitle = ttk.Label(header, text="黑底大字报短视频生成器")
        subtitle.grid(row=1, column=0, sticky="w", pady=(4, 0))

        form = ttk.Frame(self, padding=(18, 8, 18, 8))
        form.grid(row=1, column=0, sticky="nsew")
        form.columnconfigure(1, weight=1)
        form.columnconfigure(2, weight=0)

        self._label(form, 0, "文案")
        script_frame = ttk.Frame(form)
        script_frame.grid(row=0, column=1, columnspan=2, sticky="nsew", pady=6)
        script_frame.columnconfigure(0, weight=1)
        script_frame.rowconfigure(0, weight=1)
        self.script_text = tk.Text(script_frame, height=9, wrap="word", undo=True)
        self.script_text.grid(row=0, column=0, sticky="nsew")
        script_scroll = ttk.Scrollbar(script_frame, orient="vertical", command=self.script_text.yview)
        script_scroll.grid(row=0, column=1, sticky="ns")
        self.script_text.configure(yscrollcommand=script_scroll.set)
        self.script_text.tag_configure("marked", background="#ffe45c", foreground="#111111")
        self.script_text.bind("<Control-a>", self._select_all_script)
        self._load_initial_text()

        mark_bar = ttk.Frame(form)
        mark_bar.grid(row=1, column=1, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Button(mark_bar, text="标记重点", command=self._mark_selection).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(mark_bar, text="取消选中标记", command=self._unmark_selection).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(mark_bar, text="清空全部标记", command=self._clear_marks).grid(row=0, column=2)

        self._path_row(form, 2, "输出目录", self.output_dir_var, self._choose_output_dir)
        self._path_row(form, 3, "背景音乐", self.bgm_var, self._choose_bgm)
        self._path_row(form, 4, "字体文件", self.font_var, self._choose_font)

        tts_row = ttk.Frame(form)
        tts_row.grid(row=5, column=1, columnspan=2, sticky="ew", pady=6)
        tts_row.columnconfigure(2, weight=1)
        ttk.Checkbutton(tts_row, text="启用 TTS", variable=self.tts_enabled_var).grid(row=0, column=0, sticky="w")
        self.tts_engine_combo = ttk.Combobox(
            tts_row,
            textvariable=self.tts_engine_var,
            values=["Qwen3-TTS", "F5-TTS"],
            state="readonly",
            width=12,
        )
        self.tts_engine_combo.grid(row=0, column=1, sticky="w", padx=(10, 8))
        self.tts_engine_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_tts_engine_fields())

        self.qwen_panel = ttk.Frame(form)
        self.qwen_panel.grid(row=6, column=1, columnspan=2, sticky="ew", pady=(0, 6))
        self.qwen_panel.columnconfigure(1, weight=1)
        ttk.Label(self.qwen_panel, text="Qwen目录").grid(row=0, column=0, sticky="w")
        ttk.Entry(self.qwen_panel, textvariable=self.tts_model_dir_var).grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Button(self.qwen_panel, text="选择", command=self._choose_tts_model_dir).grid(row=0, column=2, sticky="e")
        qwen_options = ttk.Frame(self.qwen_panel)
        qwen_options.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        for i in range(3):
            qwen_options.columnconfigure(i, weight=1)
        self._small_field(qwen_options, 0, "发音人", self.tts_speaker_var)
        self._small_field(qwen_options, 1, "语言", self.tts_language_var)
        self._small_field(qwen_options, 2, "模型大小", self.tts_model_size_var)
        ttk.Label(self.qwen_panel, text="风格指令").grid(row=2, column=0, sticky="nw", pady=(8, 0))
        self.tts_instruct_text = tk.Text(self.qwen_panel, height=3, wrap="word", undo=True)
        self.tts_instruct_text.grid(row=2, column=1, columnspan=2, sticky="ew", pady=(8, 0))
        self.tts_instruct_text.insert("1.0", str(self.settings.get("tts_instruct", "")))

        self.f5_panel = ttk.Frame(form)
        self.f5_panel.grid(row=6, column=1, columnspan=2, sticky="ew", pady=(0, 6))
        self.f5_panel.columnconfigure(1, weight=1)
        self.f5_panel.columnconfigure(4, weight=1)
        ttk.Label(self.f5_panel, text="F5项目").grid(row=0, column=0, sticky="w")
        ttk.Entry(self.f5_panel, textvariable=self.f5_project_dir_var).grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Button(self.f5_panel, text="选择", command=self._choose_f5_project_dir).grid(row=0, column=2, padx=(0, 12))
        ttk.Label(self.f5_panel, text="F5 Python").grid(row=0, column=3, sticky="w")
        ttk.Entry(self.f5_panel, textvariable=self.f5_python_var).grid(row=0, column=4, sticky="ew", padx=(8, 8))
        ttk.Button(self.f5_panel, text="选择", command=self._choose_f5_python).grid(row=0, column=5)

        ttk.Label(self.f5_panel, text="参考音频").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(self.f5_panel, textvariable=self.f5_ref_audio_var).grid(
            row=1, column=1, columnspan=4, sticky="ew", padx=(8, 8), pady=(6, 0)
        )
        ttk.Button(self.f5_panel, text="选择", command=self._choose_f5_ref_audio).grid(row=1, column=5, pady=(6, 0))

        f5_options = ttk.Frame(self.f5_panel)
        f5_options.grid(row=2, column=0, columnspan=6, sticky="ew", pady=(6, 0))
        for i in range(2):
            f5_options.columnconfigure(i, weight=1)
        self._small_field(f5_options, 0, "F5模型", self.f5_model_var)
        self._small_field(f5_options, 1, "F5语速", self.f5_speed_var)

        ttk.Label(self.f5_panel, text="参考文本").grid(row=3, column=0, sticky="nw", pady=(8, 0))
        self.f5_ref_text = tk.Text(self.f5_panel, height=3, wrap="word", undo=True)
        self.f5_ref_text.grid(row=3, column=1, columnspan=5, sticky="ew", pady=(8, 0))
        self.f5_ref_text.insert("1.0", str(self.settings.get("f5_ref_text", "")))

        settings = ttk.Frame(form)
        settings.grid(row=7, column=1, columnspan=2, sticky="ew", pady=(6, 0))
        for i in range(6):
            settings.columnconfigure(i, weight=1)

        self._small_field(settings, 0, "每句秒数", self.duration_var)
        self._small_field(settings, 1, "FPS", self.fps_var)
        self._small_field(settings, 2, "宽度", self.width_var)
        self._small_field(settings, 3, "高度", self.height_var)
        self._small_field(settings, 4, "心跳毫秒", self.heartbeat_var)

        hint = ttk.Label(
            form,
            text="提示：每一行生成一个字幕片段；启用 TTS 后，每段字幕时长自动等于该行语音时长。",
            foreground="#555555",
        )
        hint.grid(row=8, column=1, columnspan=2, sticky="w", pady=(14, 0))

        self.log_text = tk.Text(form, height=9, wrap="word", state="disabled")
        self.log_text.grid(row=9, column=0, columnspan=3, sticky="nsew", pady=(14, 0))
        form.rowconfigure(9, weight=1)

        footer = ttk.Frame(self, padding=(18, 8, 18, 16))
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)

        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Button(footer, text="打开输出目录", command=self._open_output_folder).grid(row=0, column=1, padx=(8, 0))
        self.start_button = ttk.Button(footer, text="开始生成", command=self._start)
        self.start_button.grid(row=0, column=2, padx=(8, 0))
        self._refresh_tts_engine_fields()

    def _label(self, parent: ttk.Frame, row: int, text: str) -> None:
        ttk.Label(parent, text=text, width=10).grid(row=row, column=0, sticky="w", pady=6)

    def _path_row(self, parent: ttk.Frame, row: int, label: str, variable: tk.StringVar, command) -> None:
        self._label(parent, row, label)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=6)
        ttk.Button(parent, text="选择", command=command).grid(row=row, column=2, sticky="ew", padx=(8, 0), pady=6)

    def _refresh_tts_engine_fields(self) -> None:
        if self.tts_engine_var.get() == "F5-TTS":
            self.qwen_panel.grid_remove()
            self.f5_panel.grid()
        else:
            self.f5_panel.grid_remove()
            self.qwen_panel.grid()

    def _small_field(self, parent: ttk.Frame, column: int, label: str, variable: tk.StringVar) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=0, column=column, sticky="ew", padx=(0, 10))
        ttk.Label(frame, text=label).grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=variable, width=10).grid(row=1, column=0, sticky="ew", pady=(4, 0))

    def _choose_output_dir(self) -> None:
        path = filedialog.askdirectory(initialdir=self.output_dir_var.get() or str(DEFAULT_OUTPUT_DIR))
        if path:
            self.output_dir_var.set(path)

    def _choose_bgm(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Audio files", "*.mp3;*.wav;*.m4a"), ("All files", "*.*")])
        if path:
            self.bgm_var.set(path)

    def _choose_font(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Font files", "*.ttf;*.ttc;*.otf"), ("All files", "*.*")])
        if path:
            self.font_var.set(path)

    def _choose_tts_model_dir(self) -> None:
        path = filedialog.askdirectory(initialdir=self.tts_model_dir_var.get() or str(DEFAULT_TTS_MODEL_DIR))
        if path:
            self.tts_model_dir_var.set(path)

    def _choose_f5_project_dir(self) -> None:
        path = filedialog.askdirectory(initialdir=self.f5_project_dir_var.get() or str(DEFAULT_F5_PROJECT_DIR))
        if path:
            self.f5_project_dir_var.set(path)
            self.f5_python_var.set(str(default_f5_python(Path(path))))

    def _choose_f5_python(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=str(Path(self.f5_python_var.get()).parent if self.f5_python_var.get() else DEFAULT_F5_PROJECT_DIR),
            filetypes=[("Python executable", "python.exe"), ("All files", "*.*")],
        )
        if path:
            self.f5_python_var.set(path)

    def _choose_f5_ref_audio(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Audio files", "*.wav;*.mp3;*.flac;*.m4a"), ("All files", "*.*")])
        if path:
            self.f5_ref_audio_var.set(path)

    def _load_initial_text(self) -> None:
        if DEFAULT_INPUT.exists():
            try:
                self.script_text.insert("1.0", load_text(str(DEFAULT_INPUT)))
            except OSError:
                pass

    def _select_all_script(self, event) -> str:
        self.script_text.tag_add("sel", "1.0", "end-1c")
        return "break"

    def _mark_selection(self) -> None:
        try:
            self.script_text.tag_add("marked", "sel.first", "sel.last")
        except tk.TclError:
            messagebox.showinfo("没有选中文字", "请先在文案框里选中需要标记的文字。")

    def _unmark_selection(self) -> None:
        try:
            self.script_text.tag_remove("marked", "sel.first", "sel.last")
        except tk.TclError:
            messagebox.showinfo("没有选中文字", "请先选中需要取消标记的文字。")

    def _clear_marks(self) -> None:
        self.script_text.tag_remove("marked", "1.0", "end")

    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("正在生成", "当前任务还在运行，请稍等。")
            return

        try:
            config = VideoConfig(
                width=int(self.width_var.get()),
                height=int(self.height_var.get()),
                fps=int(self.fps_var.get()),
                segment_duration=float(self.duration_var.get()),
                heartbeat_interval_ms=int(self.heartbeat_var.get()),
            )
            f5_speed = float(self.f5_speed_var.get())
        except ValueError:
            messagebox.showerror("参数错误", "请检查秒数、FPS、宽度、高度、心跳毫秒和 F5 语速是否为数字。")
            return

        if config.heartbeat_interval_ms < 100:
            messagebox.showerror("参数错误", "心跳毫秒不能小于 100。")
            return

        output_dir = Path(self.output_dir_var.get())
        output_path = output_dir / self._timestamped_video_name()
        bgm_text = self.bgm_var.get().strip()
        font_text = self.font_var.get().strip()
        segments = self._script_segments()
        texts = self._segment_texts(segments)
        tts_enabled = bool(self.tts_enabled_var.get())
        tts_engine = self.tts_engine_var.get()
        tts_options = TTSOptions(
            model_dir=Path(self.tts_model_dir_var.get()),
            speaker=self.tts_speaker_var.get().strip() or "Vivian",
            language=self.tts_language_var.get().strip() or "Chinese",
            model_size=self.tts_model_size_var.get().strip() or "1.7B",
            instruct=self._tts_instruct(),
        )
        f5_options = F5TTSOptions(
            project_dir=Path(self.f5_project_dir_var.get()),
            python_exe=Path(self.f5_python_var.get()),
            ref_audio=Path(self.f5_ref_audio_var.get()),
            ref_text=self._f5_ref_text(),
            model=self.f5_model_var.get().strip() or "F5TTS_v1_Base",
            speed=f5_speed,
        )

        if not segments:
            messagebox.showerror("文案为空", "请在文案框里输入至少一行文字。")
            return
        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                messagebox.showerror("输出目录错误", f"无法创建输出目录：\n{exc}")
                return
        if not output_dir.is_dir():
            messagebox.showerror("输出目录错误", f"不是有效目录：{output_dir}")
            return
        if tts_enabled and tts_engine == "Qwen3-TTS" and not tts_options.model_dir.exists():
            messagebox.showerror("TTS 模型目录不存在", f"找不到目录：{tts_options.model_dir}")
            return
        if tts_enabled and tts_engine == "F5-TTS":
            if not f5_options.project_dir.exists():
                messagebox.showerror("F5-TTS 项目目录不存在", f"找不到目录：{f5_options.project_dir}")
                return
            if not f5_options.ref_audio.exists():
                messagebox.showerror("F5-TTS 参考音频不存在", f"找不到文件：{f5_options.ref_audio}")
                return
            if not f5_options.ref_text:
                messagebox.showerror("F5-TTS 参考文本为空", "请填写参考音频中朗读的准确文字。")
                return

        self.start_button.configure(state="disabled")
        self.status_var.set("正在生成视频...")
        self._append_log("开始生成视频")
        self._save_settings()

        self.worker = threading.Thread(
            target=self._run_build,
            args=(segments, texts, output_path, bgm_text, font_text, config, tts_enabled, tts_engine, tts_options, f5_options),
            daemon=True,
        )
        self.worker.start()

    def _script_segments(self) -> list[list[TextToken]]:
        end_index = self.script_text.index("end-1c")
        end_line = int(end_index.split(".")[0])
        segments: list[list[TextToken]] = []

        for line_no in range(1, end_line + 1):
            line_text = self.script_text.get(f"{line_no}.0", f"{line_no}.end")
            if not line_text.strip():
                continue

            tokens: list[TextToken] = []
            for col, char in enumerate(line_text):
                highlighted = "marked" in self.script_text.tag_names(f"{line_no}.{col}")
                if tokens and tokens[-1].highlighted == highlighted:
                    tokens[-1] = TextToken(tokens[-1].text + char, highlighted)
                else:
                    tokens.append(TextToken(char, highlighted))
            segments.append(tokens)

        return segments

    def _segment_texts(self, segments: list[list[TextToken]]) -> list[str]:
        return ["".join(token.text for token in segment).strip() for segment in segments]

    def _initial_output_dir(self) -> str:
        saved = self.settings.get("output_dir") or self.settings.get("output_path")
        if saved:
            path = Path(saved)
            return str(path.parent if path.suffix else path)
        return str(DEFAULT_OUTPUT_DIR)

    def _timestamped_video_name(self) -> str:
        return datetime.now().strftime("%Y%m%d%H%M%S") + ".mp4"

    def _tts_instruct(self) -> str:
        if not hasattr(self, "tts_instruct_text"):
            return str(self.settings.get("tts_instruct", ""))
        return self.tts_instruct_text.get("1.0", "end-1c").strip()

    def _f5_ref_text(self) -> str:
        if not hasattr(self, "f5_ref_text"):
            return str(self.settings.get("f5_ref_text", ""))
        return self.f5_ref_text.get("1.0", "end-1c").strip()

    def _load_settings(self) -> dict:
        try:
            if SETTINGS_PATH.exists():
                with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
        except (OSError, json.JSONDecodeError):
            pass
        return {}

    def _save_settings(self) -> None:
        try:
            SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            value = int(self.heartbeat_var.get())
            data = {
                "heartbeat_interval_ms": value,
                "output_dir": self.output_dir_var.get(),
                "tts_enabled": bool(self.tts_enabled_var.get()),
                "tts_engine": self.tts_engine_var.get(),
                "tts_model_dir": self.tts_model_dir_var.get(),
                "tts_speaker": self.tts_speaker_var.get(),
                "tts_language": self.tts_language_var.get(),
                "tts_model_size": self.tts_model_size_var.get(),
                "tts_instruct": self._tts_instruct(),
                "f5_project_dir": self.f5_project_dir_var.get(),
                "f5_python": self.f5_python_var.get(),
                "f5_ref_audio": self.f5_ref_audio_var.get(),
                "f5_ref_text": self._f5_ref_text(),
                "f5_model": self.f5_model_var.get(),
                "f5_speed": self.f5_speed_var.get(),
            }
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except (OSError, ValueError):
            pass

    def _on_close(self) -> None:
        self._save_settings()
        self.destroy()

    def _run_build(
        self,
        segments: list[list[TextToken]],
        texts: list[str],
        output_path: Path,
        bgm_text: str,
        font_text: str,
        config: VideoConfig,
        tts_enabled: bool,
        tts_engine: str,
        tts_options: TTSOptions,
        f5_options: F5TTSOptions,
    ) -> None:
        try:
            self.messages.put(("log", f"已准备 {len(segments)} 个字幕片段"))
            narration_paths = None
            if tts_enabled:
                self.messages.put(("log", f"正在使用 {tts_engine} 生成语音，首次加载模型可能较慢..."))
                if tts_engine == "F5-TTS":
                    tts_dir = Path("D:/Codex/cache/tmp/ai_caption_video_f5_tts")
                    narration_paths = generate_f5_tts_audio(texts, tts_dir, f5_options)
                else:
                    tts_dir = Path("D:/Codex/cache/tmp/ai_caption_video_tts")
                    narration_paths = generate_tts_audio(texts, tts_dir, tts_options)
                self.messages.put(("log", f"TTS 已生成 {len(narration_paths)} 段语音"))

            result = build_video_from_token_segments(
                segments=segments,
                output_path=output_path,
                config=config,
                bgm_path=bgm_text or None,
                font_path=font_text or None,
                narration_paths=narration_paths,
            )
            self.messages.put(("done", str(result)))
        except Exception:
            self.messages.put(("error", traceback.format_exc()))

    def _poll_messages(self) -> None:
        while True:
            try:
                kind, value = self.messages.get_nowait()
            except queue.Empty:
                break

            if kind == "log":
                self._append_log(value)
            elif kind == "done":
                self._append_log(f"生成完成：{value}")
                self.status_var.set("生成完成")
                self.start_button.configure(state="normal")
                messagebox.showinfo("完成", f"视频已生成：\n{value}")
            elif kind == "error":
                self._append_log(value)
                self.status_var.set("生成失败")
                self.start_button.configure(state="normal")
                messagebox.showerror("生成失败", value)

        self.after(150, self._poll_messages)

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message.rstrip() + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _open_output_folder(self) -> None:
        folder = Path(self.output_dir_var.get()).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(folder)
        else:
            subprocess.Popen(["xdg-open", str(folder)])


def main() -> None:
    app = CaptionVideoApp()
    app.mainloop()
