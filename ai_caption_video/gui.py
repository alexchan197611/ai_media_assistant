from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import traceback
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from . import __version__
from .config import (
    ANCIENT_REFERENCE_TEXT,
    ANCIENT_VOICE,
    DEFAULT_BGM,
    DEFAULT_INPUT,
    DEFAULT_OUTPUT_DIR,
    VideoConfig,
)
from .font_utils import find_chinese_font
from .omnivoice_bridge import (
    DEFAULT_OMNIVOICE_DIR,
    OmniVoiceOptions,
    default_omnivoice_python,
    generate_omnivoice_audio,
    resolve_omnivoice_dir,
    shutdown_omnivoice_workers,
)
from .renderer import CaptionRenderer, TextToken
from .text_utils import load_text
from .tts_bridge import DEFAULT_TTS_MODEL_DIR, TTSOptions, generate_tts_audio, resolve_qwen_model_dir, shutdown_qwen_tts_workers
from .video_builder import build_video_from_token_segments


SETTINGS_PATH = Path("D:/Codex/cache/ai_caption_video_settings.json")


class CaptionVideoApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"AI Caption Video {__version__}")
        self.geometry("1180x940")
        self.minsize(1020, 760)

        self.messages: queue.Queue[tuple[str, str]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.settings = self._load_settings()

        self.output_dir_var = tk.StringVar(value=self._initial_output_dir())
        self.bgm_var = tk.StringVar(value=str(DEFAULT_BGM))
        self.random_bgm_var = tk.BooleanVar(value=bool(self.settings.get("random_bgm", False)))
        self.font_var = tk.StringVar(value="")
        self.duration_var = tk.StringVar(value="2.0")
        self.fps_var = tk.StringVar(value="30")
        self.width_var = tk.StringVar(value="1080")
        self.height_var = tk.StringVar(value="1920")
        self.font_size_var = tk.StringVar(value=str(self.settings.get("font_size", 108)))
        self.caption_template_var = tk.StringVar(value=str(self.settings.get("caption_template", "滚动队列")))
        self.heartbeat_var = tk.StringVar(value=str(self.settings.get("heartbeat_interval_ms", 700)))
        self.tts_enabled_var = tk.BooleanVar(value=bool(self.settings.get("tts_enabled", True)))
        self.tts_engine_var = tk.StringVar(value="OmniVoice")
        self.qwen_mode_var = tk.StringVar(value=str(self.settings.get("qwen_mode", "预设人声")))
        self.tts_model_dir_var = tk.StringVar(value=str(resolve_qwen_model_dir(self.settings.get("tts_model_dir", DEFAULT_TTS_MODEL_DIR))))
        self.tts_speaker_var = tk.StringVar(value=str(self.settings.get("tts_speaker", "Vivian")))
        self.tts_language_var = tk.StringVar(value=str(self.settings.get("tts_language", "Chinese")))
        self.tts_model_size_var = tk.StringVar(value=str(self.settings.get("tts_model_size", "1.7B")))
        self.qwen_ref_audio_var = tk.StringVar(value=str(self.settings.get("qwen_ref_audio", "")))
        self.qwen_use_xvector_var = tk.BooleanVar(value=bool(self.settings.get("qwen_use_xvector_only", False)))
        self.omnivoice_project_dir_var = tk.StringVar(
            value=str(resolve_omnivoice_dir(self.settings.get("omnivoice_project_dir", DEFAULT_OMNIVOICE_DIR)))
        )
        self.omnivoice_python_var = tk.StringVar(
            value=str(
                self.settings.get(
                    "omnivoice_python",
                    default_omnivoice_python(Path(self.omnivoice_project_dir_var.get())),
                )
            )
        )
        self.omnivoice_mode_var = tk.StringVar(value="语音克隆")
        default_ref_audio = str(ANCIENT_VOICE) if ANCIENT_VOICE.exists() else str(
            self.settings.get("omnivoice_ref_audio", "")
        )
        self.omnivoice_ref_audio_var = tk.StringVar(value=default_ref_audio)
        self.omnivoice_speed_var = tk.StringVar(value=str(self.settings.get("omnivoice_speed", "1.0")))
        self.omnivoice_num_step_var = tk.StringVar(value=str(self.settings.get("omnivoice_num_step", "16")))
        self.status_var = tk.StringVar(value="准备就绪")
        self.current_image_var = tk.StringVar(value="当前行：黑色背景")
        self.line_colors: dict[int, tuple[int, int, int, int]] = {}
        self.line_images: dict[int, Path] = {}
        self._line_snapshot: list[str] = []
        self.preview_photo = None

        self._build_ui()
        self._line_snapshot = self._script_lines()
        self.script_text.edit_modified(False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(150, self._poll_messages)
        self.after(0, self._maximize_window)

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
        form.columnconfigure(3, weight=0)

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
        ttk.Label(mark_bar, text="字幕模板").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.caption_template_combo = ttk.Combobox(
            mark_bar,
            textvariable=self.caption_template_var,
            values=["滚动队列", "居中大字", "古风模板"],
            state="readonly",
            width=14,
        )
        self.caption_template_combo.grid(row=0, column=1, sticky="w", padx=(0, 14))
        self.caption_template_combo.bind("<<ComboboxSelected>>", self._on_caption_template_changed)
        ttk.Button(mark_bar, text="标记重点", command=self._mark_selection).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(mark_bar, text="取消选中标记", command=self._unmark_selection).grid(row=0, column=3, padx=(0, 8))
        ttk.Button(mark_bar, text="清空全部标记", command=self._clear_marks).grid(row=0, column=4)
        self.color_bar = ttk.Frame(mark_bar)
        self.color_bar.grid(row=0, column=5, sticky="w", padx=(18, 0))
        ttk.Label(self.color_bar, text="行颜色").grid(row=0, column=0, padx=(0, 6))
        for index, (name, color) in enumerate(self._line_color_choices(), start=1):
            button = tk.Button(
                self.color_bar,
                text="",
                width=2,
                height=1,
                bg=color,
                activebackground=color,
                command=lambda value=color: self._set_current_line_color(value),
            )
            button.grid(row=0, column=index, padx=(0, 4))

        self._path_row(form, 2, "输出目录", self.output_dir_var, self._choose_output_dir)
        self._label(form, 3, "背景音乐")
        bgm_row = ttk.Frame(form)
        bgm_row.grid(row=3, column=1, columnspan=2, sticky="ew", pady=6)
        bgm_row.columnconfigure(0, weight=1)
        ttk.Entry(bgm_row, textvariable=self.bgm_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(bgm_row, text="选择", command=self._choose_bgm).grid(row=0, column=1, padx=(8, 10))
        ttk.Checkbutton(bgm_row, text="随机匹配并卡点", variable=self.random_bgm_var).grid(row=0, column=2, sticky="w")
        self._path_row(form, 4, "字体文件", self.font_var, self._choose_font)

        tts_row = ttk.Frame(form)
        tts_row.grid(row=5, column=1, columnspan=2, sticky="ew", pady=6)
        tts_row.columnconfigure(2, weight=1)
        ttk.Checkbutton(tts_row, text="启用 TTS", variable=self.tts_enabled_var).grid(row=0, column=0, sticky="w")
        self.tts_engine_combo = ttk.Combobox(
            tts_row,
            textvariable=self.tts_engine_var,
            values=["Qwen3-TTS", "OmniVoice"],
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

        qwen_mode_row = ttk.Frame(self.qwen_panel)
        qwen_mode_row.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        qwen_mode_row.columnconfigure(1, weight=1)
        ttk.Label(qwen_mode_row, text="Qwen能力").grid(row=0, column=0, sticky="w")
        self.qwen_mode_combo = ttk.Combobox(
            qwen_mode_row,
            textvariable=self.qwen_mode_var,
            values=["预设人声", "语音设计", "语音克隆"],
            state="readonly",
            width=14,
        )
        self.qwen_mode_combo.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.qwen_mode_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_qwen_mode_fields())

        qwen_options = ttk.Frame(self.qwen_panel)
        qwen_options.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        for i in range(2):
            qwen_options.columnconfigure(i, weight=1)
        self._combo_field(qwen_options, 0, "语言", self.tts_language_var, ["Auto", "Chinese", "English", "Japanese", "Korean", "French", "German", "Spanish", "Portuguese", "Russian"])
        self._combo_field(qwen_options, 1, "模型大小", self.tts_model_size_var, ["1.7B", "0.6B"])

        self.qwen_preset_frame = ttk.Frame(self.qwen_panel)
        self.qwen_preset_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.qwen_preset_frame.columnconfigure(1, weight=1)
        ttk.Label(self.qwen_preset_frame, text="预设人声").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            self.qwen_preset_frame,
            textvariable=self.tts_speaker_var,
            values=["Aiden", "Dylan", "Eric", "Ono_anna", "Ryan", "Serena", "Sohee", "Uncle_fu", "Vivian"],
            state="readonly",
            width=18,
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))

        self.qwen_clone_frame = ttk.Frame(self.qwen_panel)
        self.qwen_clone_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.qwen_clone_frame.columnconfigure(1, weight=1)
        ttk.Label(self.qwen_clone_frame, text="参考音频").grid(row=0, column=0, sticky="w")
        ttk.Entry(self.qwen_clone_frame, textvariable=self.qwen_ref_audio_var).grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Button(self.qwen_clone_frame, text="选择", command=self._choose_qwen_ref_audio).grid(row=0, column=2)
        ttk.Checkbutton(
            self.qwen_clone_frame,
            text="仅使用 x-vector（可不填参考文本，但音质会降低）",
            variable=self.qwen_use_xvector_var,
        ).grid(row=1, column=1, columnspan=2, sticky="w", pady=(6, 0))

        self.qwen_instruct_label = ttk.Label(self.qwen_panel, text="风格指令")
        self.qwen_instruct_label.grid(row=4, column=0, sticky="nw", pady=(8, 0))
        self.tts_instruct_text = tk.Text(self.qwen_panel, height=3, wrap="word", undo=True)
        self.tts_instruct_text.grid(row=4, column=1, columnspan=2, sticky="ew", pady=(8, 0))
        self.tts_instruct_text.insert("1.0", str(self.settings.get("tts_instruct", "")))

        self.qwen_ref_text_label = ttk.Label(self.qwen_panel, text="参考文本")
        self.qwen_ref_text_label.grid(row=5, column=0, sticky="nw", pady=(8, 0))
        self.qwen_ref_text = tk.Text(self.qwen_panel, height=3, wrap="word", undo=True)
        self.qwen_ref_text.grid(row=5, column=1, columnspan=2, sticky="ew", pady=(8, 0))
        self.qwen_ref_text.insert("1.0", str(self.settings.get("qwen_ref_text", "")))

        self.omnivoice_panel = ttk.Frame(form)
        self.omnivoice_panel.grid(row=6, column=1, columnspan=2, sticky="ew", pady=(0, 6))
        self.omnivoice_panel.columnconfigure(1, weight=1)
        self.omnivoice_panel.columnconfigure(4, weight=1)
        ttk.Label(self.omnivoice_panel, text="OmniVoice项目").grid(row=0, column=0, sticky="w")
        ttk.Entry(self.omnivoice_panel, textvariable=self.omnivoice_project_dir_var).grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Button(self.omnivoice_panel, text="选择", command=self._choose_omnivoice_project_dir).grid(row=0, column=2, padx=(0, 12))
        ttk.Label(self.omnivoice_panel, text="Python").grid(row=0, column=3, sticky="w")
        ttk.Entry(self.omnivoice_panel, textvariable=self.omnivoice_python_var).grid(row=0, column=4, sticky="ew", padx=(8, 8))
        ttk.Button(self.omnivoice_panel, text="选择", command=self._choose_omnivoice_python).grid(row=0, column=5)

        omni_options = ttk.Frame(self.omnivoice_panel)
        omni_options.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(6, 0))
        for i in range(3):
            omni_options.columnconfigure(i, weight=1)
        self._combo_field(omni_options, 0, "模式", self.omnivoice_mode_var, ["自动音色", "语音设计", "语音克隆"])
        self._small_field(omni_options, 1, "语速", self.omnivoice_speed_var)
        self._small_field(omni_options, 2, "步数", self.omnivoice_num_step_var)

        ttk.Label(self.omnivoice_panel, text="参考音频").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(self.omnivoice_panel, textvariable=self.omnivoice_ref_audio_var).grid(
            row=2, column=1, columnspan=4, sticky="ew", padx=(8, 8), pady=(6, 0)
        )
        ttk.Button(self.omnivoice_panel, text="选择", command=self._choose_omnivoice_ref_audio).grid(row=2, column=5, pady=(6, 0))

        ttk.Label(self.omnivoice_panel, text="参考文本").grid(row=3, column=0, sticky="nw", pady=(8, 0))
        self.omnivoice_ref_text = tk.Text(self.omnivoice_panel, height=2, wrap="word", undo=True)
        self.omnivoice_ref_text.grid(row=3, column=1, columnspan=5, sticky="ew", pady=(8, 0))
        self.omnivoice_ref_text.insert("1.0", ANCIENT_REFERENCE_TEXT)

        ttk.Label(self.omnivoice_panel, text="语音设计").grid(row=4, column=0, sticky="nw", pady=(8, 0))
        self.omnivoice_instruct_text = tk.Text(self.omnivoice_panel, height=2, wrap="word", undo=True)
        self.omnivoice_instruct_text.grid(row=4, column=1, columnspan=5, sticky="ew", pady=(8, 0))
        self.omnivoice_instruct_text.insert("1.0", str(self.settings.get("omnivoice_instruct", "female, natural, clear")))

        settings = ttk.Frame(form)
        settings.grid(row=7, column=1, columnspan=2, sticky="ew", pady=(6, 0))
        for i in range(6):
            settings.columnconfigure(i, weight=1)

        self._small_field(settings, 0, "每句秒数", self.duration_var)
        self._small_field(settings, 1, "FPS", self.fps_var)
        self._small_field(settings, 2, "宽度", self.width_var)
        self._small_field(settings, 3, "高度", self.height_var)
        self._small_field(settings, 4, "字号", self.font_size_var)
        self._small_field(settings, 5, "心跳毫秒", self.heartbeat_var)

        hint = ttk.Label(
            form,
            text="提示：每一行生成一个字幕片段；启用 TTS 后，每段字幕时长自动等于该行语音时长。",
            foreground="#555555",
        )
        hint.grid(row=9, column=1, columnspan=2, sticky="w", pady=(14, 0))

        self.log_text = tk.Text(form, height=9, wrap="word", state="disabled")
        self.log_text.grid(row=10, column=0, columnspan=3, sticky="nsew", pady=(14, 0))
        form.rowconfigure(10, weight=1)

        preview = ttk.Frame(form, padding=(16, 0, 0, 0))
        preview.grid(row=0, column=3, rowspan=11, sticky="n")
        ttk.Label(preview, text="手机预览 9:16").grid(row=0, column=0, sticky="w")
        self.preview_canvas = tk.Canvas(preview, width=270, height=480, bg="#111111", highlightthickness=1, highlightbackground="#444444")
        self.preview_canvas.grid(row=1, column=0, pady=(8, 0))
        ttk.Label(preview, text="预览当前光标所在行").grid(row=2, column=0, sticky="w", pady=(8, 0))
        image_actions = ttk.Frame(preview)
        image_actions.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(image_actions, text="选择当前行图片", command=self._choose_current_line_image).grid(row=0, column=0)
        ttk.Button(image_actions, text="清除", command=self._clear_current_line_image).grid(row=0, column=1, padx=(8, 0))
        ttk.Label(preview, textvariable=self.current_image_var, wraplength=270).grid(
            row=4, column=0, sticky="w", pady=(6, 0)
        )

        footer = ttk.Frame(self, padding=(18, 8, 18, 16))
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)

        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Button(footer, text="打开输出目录", command=self._open_output_folder).grid(row=0, column=1, padx=(8, 0))
        self.start_button = ttk.Button(footer, text="开始生成", command=self._start)
        self.start_button.grid(row=0, column=2, padx=(8, 0))
        self._refresh_tts_engine_fields()
        self._refresh_qwen_mode_fields()
        self._refresh_caption_template_fields(activate_voice=False)
        self._bind_preview_updates()
        self.after(250, self._update_preview)

    def _label(self, parent: ttk.Frame, row: int, text: str) -> None:
        ttk.Label(parent, text=text, width=10).grid(row=row, column=0, sticky="w", pady=6)

    def _bind_preview_updates(self) -> None:
        self.script_text.bind("<KeyRelease>", lambda _event: self._schedule_preview_update(), add=True)
        self.script_text.bind("<ButtonRelease-1>", lambda _event: self._schedule_preview_update(), add=True)
        self.script_text.bind("<<Modified>>", self._on_script_modified, add=True)
        for variable in (
            self.font_size_var,
            self.width_var,
            self.height_var,
            self.font_var,
            self.heartbeat_var,
            self.caption_template_var,
        ):
            variable.trace_add("write", lambda *_args: self._schedule_preview_update())

    def _on_script_modified(self, _event=None) -> None:
        if self.script_text.edit_modified():
            self.script_text.edit_modified(False)
            self._reconcile_line_metadata()
            self._schedule_preview_update()

    def _script_lines(self) -> list[str]:
        return self.script_text.get("1.0", "end-1c").split("\n")

    def _reconcile_line_metadata(self) -> None:
        new_lines = self._script_lines()
        old_lines = self._line_snapshot
        if new_lines == old_lines:
            return

        new_colors: dict[int, tuple[int, int, int, int]] = {}
        new_images: dict[int, Path] = {}
        matcher = SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
        for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
            if tag != "equal":
                continue
            for offset in range(old_end - old_start):
                old_line_no = old_start + offset + 1
                new_line_no = new_start + offset + 1
                if old_line_no in self.line_colors:
                    new_colors[new_line_no] = self.line_colors[old_line_no]
                if old_line_no in self.line_images:
                    new_images[new_line_no] = self.line_images[old_line_no]

        self.line_colors = new_colors
        self.line_images = new_images
        self._line_snapshot = new_lines
        self._refresh_line_color_tags()

    def _refresh_line_color_tags(self) -> None:
        for tag in self.script_text.tag_names():
            if tag.startswith("line_color_"):
                self.script_text.tag_delete(tag)
        for line_no, color in self.line_colors.items():
            self._apply_line_color_tag(line_no, self._hex_from_rgba(color))

    def _schedule_preview_update(self) -> None:
        if hasattr(self, "_preview_job"):
            try:
                self.after_cancel(self._preview_job)
            except tk.TclError:
                pass
        self._preview_job = self.after(120, self._update_preview)

    def _update_preview(self) -> None:
        if not hasattr(self, "preview_canvas"):
            return
        try:
            config = VideoConfig(
                width=int(self.width_var.get()),
                height=int(self.height_var.get()),
                font_size=int(self.font_size_var.get()),
                heartbeat_interval_ms=max(100, int(self.heartbeat_var.get())),
            )
            font_path = find_chinese_font(self.font_var.get().strip() or None)
            renderer = CaptionRenderer(config, font_path, [])
            line_no = self._current_line_no()
            background = self._preview_background_for_line(line_no)
            template = self._caption_template_value()
            if template == "queue":
                segments = tuple(tuple(segment) for segment in self._script_segments())
                if not segments:
                    segments = ((TextToken("请输入文案", False, self._rgba_from_hex("#666666")),),)
                index = min(max(self._current_nonempty_segment_index(), 0), len(segments) - 1)
                frame = renderer.frame_queue(
                    segments,
                    index,
                    t=config.intro_duration + 0.18,
                    duration=2.0,
                    background=background,
                )
            elif template == "ancient":
                tokens = self._tokens_for_line(line_no)
                frame = renderer.frame_ancient(
                    tuple(tokens),
                    t=1.45,
                    duration=2.0,
                    background=background,
                )
            else:
                tokens = self._tokens_for_line(line_no)
                frame = renderer.frame_tokens(
                    tuple(tokens),
                    t=config.intro_duration + 0.05,
                    duration=2.0,
                    background=background,
                )
            image = Image.fromarray(frame).resize((270, 480), Image.Resampling.LANCZOS)
        except Exception:
            image = Image.new("RGB", (270, 480), (0, 0, 0))

        self.preview_photo = ImageTk.PhotoImage(image)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(0, 0, anchor="nw", image=self.preview_photo)
        self._refresh_current_image_label()

    def _preview_background_for_line(self, line_no: int) -> Image.Image | None:
        path = self.line_images.get(line_no)
        if path is None or not path.exists():
            return None
        try:
            with Image.open(path) as source:
                return source.convert("RGB").copy()
        except OSError:
            return None

    def _refresh_current_image_label(self) -> None:
        path = self.line_images.get(self._current_line_no())
        if path and path.exists():
            self.current_image_var.set(f"当前行配图：{path.name}")
        else:
            self.current_image_var.set("当前行：黑色背景")

    def _tokens_for_line(self, line_no: int) -> list[TextToken]:
        line_text = self.script_text.get(f"{line_no}.0", f"{line_no}.end")
        if not line_text.strip():
            return [TextToken("请输入文案", False, self._rgba_from_hex("#666666"))]
        line_color = self.line_colors.get(line_no, self._rgba_from_hex("#ffffff"))
        tokens: list[TextToken] = []
        for col, char in enumerate(line_text):
            highlighted = "marked" in self.script_text.tag_names(f"{line_no}.{col}")
            if tokens and tokens[-1].highlighted == highlighted and tokens[-1].color == line_color:
                tokens[-1] = TextToken(tokens[-1].text + char, highlighted, line_color)
            else:
                tokens.append(TextToken(char, highlighted, line_color))
        return tokens

    def _current_line_no(self) -> int:
        try:
            return int(self.script_text.index("insert").split(".")[0])
        except (tk.TclError, ValueError):
            return 1

    def _current_nonempty_segment_index(self) -> int:
        current_line = self._current_line_no()
        index = 0
        for line_no in range(1, current_line):
            if self.script_text.get(f"{line_no}.0", f"{line_no}.end").strip():
                index += 1
        return index

    def _selected_line_numbers(self) -> list[int]:
        try:
            start = int(self.script_text.index("sel.first").split(".")[0])
            end = int(self.script_text.index("sel.last").split(".")[0])
            return list(range(start, end + 1))
        except tk.TclError:
            return [self._current_line_no()]

    def _set_current_line_color(self, color_hex: str) -> None:
        color = self._rgba_from_hex(color_hex)
        for line_no in self._selected_line_numbers():
            self.line_colors[line_no] = color
            self._apply_line_color_tag(line_no, color_hex)
        self._schedule_preview_update()

    def _apply_line_color_tag(self, line_no: int, color_hex: str) -> None:
        tag = f"line_color_{line_no}"
        self.script_text.tag_configure(tag, foreground=color_hex)
        self.script_text.tag_add(tag, f"{line_no}.0", f"{line_no}.end")
        self.script_text.tag_lower(tag, "marked")

    def _line_color_choices(self) -> list[tuple[str, str]]:
        return [
            ("白", "#ffffff"),
            ("黄", "#ffd60a"),
            ("绿", "#00856f"),
            ("橙", "#c46a00"),
            ("红", "#ff4d4f"),
            ("蓝", "#2f80ed"),
            ("紫", "#9b51e0"),
        ]

    def _rgba_from_hex(self, color_hex: str) -> tuple[int, int, int, int]:
        value = color_hex.strip().lstrip("#")
        if len(value) != 6:
            return (255, 255, 255, 255)
        return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), 255)

    def _hex_from_rgba(self, color: tuple[int, int, int, int]) -> str:
        return f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"

    def _path_row(self, parent: ttk.Frame, row: int, label: str, variable: tk.StringVar, command) -> None:
        self._label(parent, row, label)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=6)
        ttk.Button(parent, text="选择", command=command).grid(row=row, column=2, sticky="ew", padx=(8, 0), pady=6)

    def _refresh_tts_engine_fields(self) -> None:
        if self.tts_engine_var.get() == "OmniVoice":
            self.qwen_panel.grid_remove()
            self.omnivoice_panel.grid()
        else:
            self.omnivoice_panel.grid_remove()
            self.qwen_panel.grid()
            self._refresh_qwen_mode_fields()

    def _on_caption_template_changed(self, _event=None) -> None:
        self._refresh_caption_template_fields(activate_voice=True)
        self._schedule_preview_update()

    def _refresh_caption_template_fields(self, activate_voice: bool) -> None:
        if self._caption_template_value() == "ancient":
            self.color_bar.grid_remove()
            if activate_voice:
                self._activate_ancient_voice()
        else:
            self.color_bar.grid()

    def _activate_ancient_voice(self) -> None:
        self.tts_enabled_var.set(True)
        self.tts_engine_var.set("OmniVoice")
        self.omnivoice_mode_var.set("语音克隆")
        if ANCIENT_VOICE.exists():
            self.omnivoice_ref_audio_var.set(str(ANCIENT_VOICE))
        self.omnivoice_ref_text.delete("1.0", "end")
        self.omnivoice_ref_text.insert("1.0", ANCIENT_REFERENCE_TEXT)
        self._refresh_tts_engine_fields()

    def _maximize_window(self) -> None:
        try:
            self.state("zoomed")
        except tk.TclError:
            try:
                self.attributes("-zoomed", True)
            except tk.TclError:
                pass

    def _refresh_qwen_mode_fields(self) -> None:
        mode = self.qwen_mode_var.get()
        self.qwen_preset_frame.grid_remove()
        self.qwen_clone_frame.grid_remove()
        self.qwen_instruct_label.grid_remove()
        self.tts_instruct_text.grid_remove()
        self.qwen_ref_text_label.grid_remove()
        self.qwen_ref_text.grid_remove()

        if mode == "预设人声":
            self.qwen_preset_frame.grid()
            self.qwen_instruct_label.grid()
            self.tts_instruct_text.grid()
            self.qwen_instruct_label.configure(text="风格指令")
        elif mode == "语音设计":
            self.qwen_instruct_label.grid()
            self.tts_instruct_text.grid()
            self.qwen_instruct_label.configure(text="语音描述")
            if not self._tts_instruct():
                self.tts_instruct_text.insert(
                    "1.0",
                    "请描述想要的声音和情绪，例如：用温柔、清晰、略带鼓励感的中文女声朗读，语速中等，情绪自然。",
                )
        else:
            self.qwen_clone_frame.grid()
            self.qwen_ref_text_label.grid()
            self.qwen_ref_text.grid()

    def _small_field(self, parent: ttk.Frame, column: int, label: str, variable: tk.StringVar) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=0, column=column, sticky="ew", padx=(0, 10))
        ttk.Label(frame, text=label).grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=variable, width=10).grid(row=1, column=0, sticky="ew", pady=(4, 0))

    def _combo_field(self, parent: ttk.Frame, column: int, label: str, variable: tk.StringVar, values: list[str]) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=0, column=column, sticky="ew", padx=(0, 10))
        ttk.Label(frame, text=label).grid(row=0, column=0, sticky="w")
        ttk.Combobox(frame, textvariable=variable, values=values, state="readonly", width=12).grid(
            row=1, column=0, sticky="ew", pady=(4, 0)
        )

    def _choose_output_dir(self) -> None:
        path = filedialog.askdirectory(initialdir=self.output_dir_var.get() or str(DEFAULT_OUTPUT_DIR))
        if path:
            self.output_dir_var.set(path)

    def _choose_bgm(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Audio files", "*.mp3;*.wav;*.m4a"), ("All files", "*.*")])
        if path:
            self.bgm_var.set(path)

    def _choose_current_line_image(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[
                ("Image files", "*.jpg;*.jpeg;*.png;*.webp;*.bmp"),
                ("All files", "*.*"),
            ]
        )
        if path:
            self.line_images[self._current_line_no()] = Path(path)
            self._schedule_preview_update()

    def _clear_current_line_image(self) -> None:
        self.line_images.pop(self._current_line_no(), None)
        self._schedule_preview_update()

    def _choose_font(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Font files", "*.ttf;*.ttc;*.otf"), ("All files", "*.*")])
        if path:
            self.font_var.set(path)

    def _choose_tts_model_dir(self) -> None:
        path = filedialog.askdirectory(initialdir=self.tts_model_dir_var.get() or str(DEFAULT_TTS_MODEL_DIR))
        if path:
            self.tts_model_dir_var.set(path)

    def _choose_qwen_ref_audio(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Audio files", "*.wav;*.mp3;*.flac;*.m4a"), ("All files", "*.*")])
        if path:
            self.qwen_ref_audio_var.set(path)

    def _choose_omnivoice_project_dir(self) -> None:
        path = filedialog.askdirectory(initialdir=self.omnivoice_project_dir_var.get() or str(DEFAULT_OMNIVOICE_DIR))
        if path:
            self.omnivoice_project_dir_var.set(path)
            self.omnivoice_python_var.set(str(default_omnivoice_python(Path(path))))

    def _choose_omnivoice_python(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=str(Path(self.omnivoice_python_var.get()).parent if self.omnivoice_python_var.get() else DEFAULT_OMNIVOICE_DIR),
            filetypes=[("Python executable", "python.exe"), ("All files", "*.*")],
        )
        if path:
            self.omnivoice_python_var.set(path)

    def _choose_omnivoice_ref_audio(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Audio files", "*.wav;*.mp3;*.flac;*.m4a"), ("All files", "*.*")])
        if path:
            self.omnivoice_ref_audio_var.set(path)

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
                font_size=int(self.font_size_var.get()),
                heartbeat_interval_ms=int(self.heartbeat_var.get()),
                caption_template=self._caption_template_value(),
            )
            omnivoice_speed = float(self.omnivoice_speed_var.get())
            omnivoice_num_step = int(self.omnivoice_num_step_var.get())
        except ValueError:
            messagebox.showerror("参数错误", "请检查秒数、FPS、宽度、高度、心跳毫秒、OmniVoice 语速和步数是否为数字。")
            return

        if config.heartbeat_interval_ms < 100:
            messagebox.showerror("参数错误", "心跳毫秒不能小于 100。")
            return
        if config.font_size < 20 or config.font_size > 260:
            messagebox.showerror("参数错误", "字号建议设置在 20 到 260 之间。")
            return
        if omnivoice_speed < 0.5 or omnivoice_speed > 2.0:
            messagebox.showerror("参数错误", "OmniVoice 语速建议设置在 0.5 到 2.0 之间。")
            return
        if omnivoice_num_step < 4 or omnivoice_num_step > 64:
            messagebox.showerror("参数错误", "OmniVoice 步数建议设置在 4 到 64 之间。")
            return

        output_dir = Path(self.output_dir_var.get())
        output_path = output_dir / self._timestamped_video_name()
        bgm_text = self.bgm_var.get().strip()
        font_text = self.font_var.get().strip()
        segments = self._script_segments()
        background_paths = self._segment_background_paths()
        texts = self._segment_texts(segments)
        tts_enabled = bool(self.tts_enabled_var.get())
        tts_engine = self.tts_engine_var.get()
        tts_options = TTSOptions(
            model_dir=Path(self.tts_model_dir_var.get()),
            mode=self._qwen_mode_value(),
            speaker=self.tts_speaker_var.get().strip() or "Vivian",
            language=self.tts_language_var.get().strip() or "Chinese",
            model_size=self.tts_model_size_var.get().strip() or "1.7B",
            instruct=self._tts_instruct(),
            ref_audio=Path(self.qwen_ref_audio_var.get()) if self.qwen_ref_audio_var.get().strip() else None,
            ref_text=self._qwen_ref_text(),
            use_xvector_only=bool(self.qwen_use_xvector_var.get()),
        )
        omnivoice_options = OmniVoiceOptions(
            project_dir=Path(self.omnivoice_project_dir_var.get()),
            python_exe=Path(self.omnivoice_python_var.get()),
            mode=self._omnivoice_mode_value(),
            ref_audio=Path(self.omnivoice_ref_audio_var.get()) if self.omnivoice_ref_audio_var.get().strip() else None,
            ref_text=self._omnivoice_ref_text(),
            instruct=self._omnivoice_instruct(),
            speed=omnivoice_speed,
            num_step=omnivoice_num_step,
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
        if tts_enabled and tts_engine == "Qwen3-TTS" and tts_options.mode == "voice_design" and not tts_options.instruct:
            messagebox.showerror("语音描述为空", "语音设计模式需要填写声音、情绪或语速描述。")
            return
        if tts_enabled and tts_engine == "Qwen3-TTS" and tts_options.mode == "voice_clone":
            if not tts_options.ref_audio or not tts_options.ref_audio.exists():
                messagebox.showerror("Qwen 参考音频不存在", f"找不到文件：{tts_options.ref_audio}")
                return
            if not tts_options.use_xvector_only and not tts_options.ref_text:
                messagebox.showerror("Qwen 参考文本为空", "语音克隆建议填写参考音频中朗读的准确文字；或者勾选仅使用 x-vector。")
                return
        if tts_enabled and tts_engine == "OmniVoice":
            if not omnivoice_options.project_dir.exists():
                messagebox.showerror("OmniVoice 项目目录不存在", f"找不到目录：{omnivoice_options.project_dir}")
                return
            if not omnivoice_options.python_exe.exists():
                messagebox.showerror("OmniVoice Python 不存在", f"找不到文件：{omnivoice_options.python_exe}")
                return
            if omnivoice_options.mode == "clone" and (not omnivoice_options.ref_audio or not omnivoice_options.ref_audio.exists()):
                messagebox.showerror("OmniVoice 参考音频不存在", f"找不到文件：{omnivoice_options.ref_audio}")
                return
            if omnivoice_options.mode == "design" and not omnivoice_options.instruct:
                messagebox.showerror("OmniVoice 语音设计为空", "请填写语音设计，例如：female, natural, clear。")
                return

        self.start_button.configure(state="disabled")
        self.status_var.set("正在生成视频...")
        self._append_log("开始生成视频")
        self._save_settings()

        self.worker = threading.Thread(
            target=self._run_build,
            args=(
                segments,
                texts,
                background_paths,
                output_path,
                bgm_text,
                font_text,
                config,
                tts_enabled,
                tts_engine,
                tts_options,
                omnivoice_options,
                bool(self.random_bgm_var.get()),
            ),
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
            line_color = self.line_colors.get(line_no, self._rgba_from_hex("#ffffff"))
            for col, char in enumerate(line_text):
                highlighted = "marked" in self.script_text.tag_names(f"{line_no}.{col}")
                if tokens and tokens[-1].highlighted == highlighted and tokens[-1].color == line_color:
                    tokens[-1] = TextToken(tokens[-1].text + char, highlighted, line_color)
                else:
                    tokens.append(TextToken(char, highlighted, line_color))
            segments.append(tokens)

        return segments

    def _segment_texts(self, segments: list[list[TextToken]]) -> list[str]:
        return ["".join(token.text for token in segment).strip() for segment in segments]

    def _segment_background_paths(self) -> list[Path | None]:
        paths: list[Path | None] = []
        end_line = int(self.script_text.index("end-1c").split(".")[0])
        for line_no in range(1, end_line + 1):
            if self.script_text.get(f"{line_no}.0", f"{line_no}.end").strip():
                paths.append(self.line_images.get(line_no))
        return paths

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

    def _qwen_ref_text(self) -> str:
        if not hasattr(self, "qwen_ref_text"):
            return str(self.settings.get("qwen_ref_text", ""))
        return self.qwen_ref_text.get("1.0", "end-1c").strip()

    def _omnivoice_ref_text(self) -> str:
        if not hasattr(self, "omnivoice_ref_text"):
            return str(self.settings.get("omnivoice_ref_text", ""))
        return self.omnivoice_ref_text.get("1.0", "end-1c").strip()

    def _omnivoice_instruct(self) -> str:
        if not hasattr(self, "omnivoice_instruct_text"):
            return str(self.settings.get("omnivoice_instruct", ""))
        return self.omnivoice_instruct_text.get("1.0", "end-1c").strip()

    def _qwen_mode_value(self) -> str:
        return {
            "预设人声": "preset",
            "语音设计": "voice_design",
            "语音克隆": "voice_clone",
        }.get(self.qwen_mode_var.get(), "preset")

    def _caption_template_value(self) -> str:
        return {
            "滚动队列": "queue",
            "居中大字": "center",
            "古风模板": "ancient",
        }.get(self.caption_template_var.get(), "queue")

    def _omnivoice_mode_value(self) -> str:
        return {"自动音色": "auto", "语音设计": "design", "语音克隆": "clone"}.get(
            self.omnivoice_mode_var.get(), "auto"
        )

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
                "font_size": int(self.font_size_var.get()),
                "caption_template": self.caption_template_var.get(),
                "output_dir": self.output_dir_var.get(),
                "random_bgm": bool(self.random_bgm_var.get()),
                "tts_enabled": bool(self.tts_enabled_var.get()),
                "tts_engine": self.tts_engine_var.get(),
                "qwen_mode": self.qwen_mode_var.get(),
                "tts_model_dir": self.tts_model_dir_var.get(),
                "tts_speaker": self.tts_speaker_var.get(),
                "tts_language": self.tts_language_var.get(),
                "tts_model_size": self.tts_model_size_var.get(),
                "tts_instruct": self._tts_instruct(),
                "qwen_ref_audio": self.qwen_ref_audio_var.get(),
                "qwen_ref_text": self._qwen_ref_text(),
                "qwen_use_xvector_only": bool(self.qwen_use_xvector_var.get()),
                "omnivoice_project_dir": self.omnivoice_project_dir_var.get(),
                "omnivoice_python": self.omnivoice_python_var.get(),
                "omnivoice_mode": self.omnivoice_mode_var.get(),
                "omnivoice_ref_audio": self.omnivoice_ref_audio_var.get(),
                "omnivoice_ref_text": self._omnivoice_ref_text(),
                "omnivoice_instruct": self._omnivoice_instruct(),
                "omnivoice_speed": self.omnivoice_speed_var.get(),
                "omnivoice_num_step": self.omnivoice_num_step_var.get(),
            }
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except (OSError, ValueError):
            pass

    def _on_close(self) -> None:
        self._save_settings()
        shutdown_qwen_tts_workers()
        shutdown_omnivoice_workers()
        self.destroy()

    def _run_build(
        self,
        segments: list[list[TextToken]],
        texts: list[str],
        background_paths: list[Path | None],
        output_path: Path,
        bgm_text: str,
        font_text: str,
        config: VideoConfig,
        tts_enabled: bool,
        tts_engine: str,
        tts_options: TTSOptions,
        omnivoice_options: OmniVoiceOptions,
        random_bgm: bool,
    ) -> None:
        try:
            self.messages.put(("log", f"已准备 {len(segments)} 个字幕片段"))
            narration_paths = None
            if tts_enabled:
                self.messages.put(("log", f"正在使用 {tts_engine} 生成语音，首次加载模型可能较慢..."))
                if tts_engine == "OmniVoice":
                    tts_dir = Path("D:/Codex/cache/tmp/ai_caption_video_omnivoice")
                    narration_paths = generate_omnivoice_audio(texts, tts_dir, omnivoice_options)
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
                background_paths=background_paths,
                random_bgm=random_bgm,
                log_callback=lambda message: self.messages.put(("log", message)),
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
