from dataclasses import dataclass
from functools import lru_cache
import math
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .config import VideoConfig
from .font_utils import load_font


@dataclass(frozen=True)
class TextToken:
    text: str
    highlighted: bool


@dataclass(frozen=True)
class CaptionTransform:
    scale_x: float = 1.0
    scale_y: float = 1.0
    offset_x: int = 0
    offset_y: int = 0
    opacity: float = 1.0
    rotation: float = 0.0


def ease_out_cubic(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 1 - pow(1 - x, 3)


class CaptionRenderer:
    def __init__(self, config: VideoConfig, font_path: str, keywords: list[str]):
        self.config = config
        self.font_path = font_path
        self.keywords = sorted(set(keywords), key=len, reverse=True)
        self.base_font = load_font(font_path, config.font_size)

    def frame(self, sentence: str, t: float, duration: float) -> np.ndarray:
        return self.frame_tokens(tuple(self._tokenize(sentence)), t, duration)

    def frame_tokens(
        self,
        tokens: tuple[TextToken, ...],
        t: float,
        duration: float,
        transition: str = "shrink",
    ) -> np.ndarray:
        transform = self._caption_transform(t, duration, transition)
        caption = self._render_caption_tokens(tokens, self._highlight_pulse(t, duration))

        scaled_size = (
            max(1, int(caption.width * transform.scale_x)),
            max(1, int(caption.height * transform.scale_y)),
        )
        caption = caption.resize(scaled_size, Image.Resampling.LANCZOS)
        if transform.rotation:
            caption = caption.rotate(transform.rotation, resample=Image.Resampling.BICUBIC, expand=True)
        if transform.opacity < 1.0:
            alpha = caption.getchannel("A")
            alpha = alpha.point(lambda value: int(value * max(0.0, min(1.0, transform.opacity))))
            caption.putalpha(alpha)

        frame = Image.new("RGB", (self.config.width, self.config.height), self.config.background_color)
        x = (self.config.width - caption.width) // 2 + transform.offset_x
        y = (self.config.height - caption.height) // 2 + transform.offset_y
        frame.paste(caption, (x, y), caption)
        return np.array(frame)

    def _caption_transform(self, t: float, duration: float, transition: str) -> CaptionTransform:
        intro_duration = max(0.001, self.config.intro_duration)
        outro_duration = max(0.001, self.config.outro_duration)
        outro_start = max(intro_duration, duration - outro_duration)

        if t < intro_duration:
            scale = 0.8 + 0.2 * ease_out_cubic(t / intro_duration)
            return CaptionTransform(scale_x=scale, scale_y=scale)
        if t >= outro_start:
            progress = min(max((t - outro_start) / outro_duration, 0.0), 1.0)
            return self._outro_transform(progress, transition)
        return CaptionTransform()

    def _outro_transform(self, progress: float, transition: str) -> CaptionTransform:
        eased = ease_out_cubic(progress)
        if transition == "slide_up":
            return CaptionTransform(offset_y=int(-self.config.height * 0.34 * eased), opacity=1.0 - 0.65 * eased)
        if transition == "slide_down":
            return CaptionTransform(offset_y=int(self.config.height * 0.34 * eased), opacity=1.0 - 0.65 * eased)
        if transition == "slide_left":
            return CaptionTransform(offset_x=int(-self.config.width * 0.60 * eased), opacity=1.0 - 0.65 * eased)
        if transition == "slide_right":
            return CaptionTransform(offset_x=int(self.config.width * 0.60 * eased), opacity=1.0 - 0.65 * eased)
        if transition == "stand_up":
            return CaptionTransform(
                scale_x=1.0 - 0.12 * eased,
                scale_y=max(0.08, 1.0 - 0.92 * eased),
                offset_y=int(-self.config.height * 0.10 * eased),
                opacity=1.0 - 0.55 * eased,
            )
        if transition == "tilt_away":
            scale = 1.0 - (1.0 - self.config.outro_scale) * eased
            return CaptionTransform(
                scale_x=scale,
                scale_y=scale,
                offset_y=int(-self.config.height * 0.08 * eased),
                opacity=1.0 - 0.45 * eased,
                rotation=-7.0 * eased,
            )

        scale = 1.0 - (1.0 - self.config.outro_scale) * eased
        return CaptionTransform(scale_x=scale, scale_y=scale, opacity=1.0 - 0.25 * eased)

    def _highlight_pulse(self, t: float, duration: float) -> float:
        if t < self.config.intro_duration or t >= duration - self.config.outro_duration:
            return 1.0
        interval = max(100, self.config.heartbeat_interval_ms) / 1000.0
        wave = 0.5 + 0.5 * math.sin((t / interval) * math.pi * 2)
        return 0.94 + 0.06 * wave

    def _render_caption_tokens(self, tokens: tuple[TextToken, ...], pulse: float) -> Image.Image:
        lines, line_metrics = self._layout_tokens(tokens)
        max_width = max((width for width, _ in line_metrics), default=1)
        total_height = sum(height for _, height in line_metrics)
        total_height += self.config.line_spacing * max(0, len(lines) - 1)

        padding = 24
        image = Image.new("RGBA", (max_width + padding * 2, total_height + padding * 2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        y = padding
        for line, (line_width, line_height) in zip(lines, line_metrics):
            x = (image.width - line_width) // 2
            for token in line:
                slot_font = self._layout_font_for(token.highlighted)
                slot_width = self._text_width(token.text, slot_font)
                font = self._draw_font_for(token.highlighted, pulse)
                color = self.config.highlight_color if token.highlighted else self.config.text_color
                bbox = draw.textbbox((0, 0), token.text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                draw_x = x + (slot_width - text_width) // 2
                draw_y = y + (line_height - text_height) // 2 - bbox[1]
                draw.text((draw_x, draw_y), token.text, fill=color, font=font)
                x += slot_width
            y += line_height + self.config.line_spacing
        return image

    @lru_cache(maxsize=256)
    def _layout_tokens(
        self, tokens: tuple[TextToken, ...]
    ) -> tuple[tuple[tuple[TextToken, ...], ...], tuple[tuple[int, int], ...]]:
        lines = self._wrap_tokens(tokens)
        line_metrics = [self._line_size(line) for line in lines]
        return tuple(tuple(line) for line in lines), tuple(line_metrics)

    def _tokenize(self, sentence: str) -> list[TextToken]:
        if not self.keywords:
            return [TextToken(sentence, False)]

        pattern = re.compile("|".join(re.escape(k) for k in self.keywords))
        tokens: list[TextToken] = []
        cursor = 0
        for match in pattern.finditer(sentence):
            if match.start() > cursor:
                tokens.append(TextToken(sentence[cursor : match.start()], False))
            tokens.append(TextToken(match.group(0), True))
            cursor = match.end()
        if cursor < len(sentence):
            tokens.append(TextToken(sentence[cursor:], False))
        return tokens

    def _wrap_tokens(self, tokens: tuple[TextToken, ...]) -> list[list[TextToken]]:
        max_width = int(self.config.width * self.config.max_text_width_ratio)
        lines: list[list[TextToken]] = [[]]
        current_width = 0

        for token in tokens:
            for char in token.text:
                if char == "\n":
                    lines.append([])
                    current_width = 0
                    continue
                font = self._layout_font_for(token.highlighted)
                char_width = self._text_width(char, font)
                if lines[-1] and current_width + char_width > max_width:
                    lines.append([])
                    current_width = 0
                self._append_char(lines[-1], char, token.highlighted)
                current_width += char_width

        return [line for line in lines if line]

    def _append_char(self, line: list[TextToken], char: str, highlighted: bool) -> None:
        if line and line[-1].highlighted == highlighted:
            line[-1] = TextToken(line[-1].text + char, highlighted)
        else:
            line.append(TextToken(char, highlighted))

    def _line_size(self, line: list[TextToken]) -> tuple[int, int]:
        width = 0
        height = 0
        probe = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        draw = ImageDraw.Draw(probe)
        for token in line:
            font = self._layout_font_for(token.highlighted)
            bbox = draw.textbbox((0, 0), token.text, font=font)
            width += bbox[2] - bbox[0]
            height = max(height, bbox[3] - bbox[1])
        return width, height

    def _text_width(self, text: str, font: ImageFont.FreeTypeFont) -> int:
        probe = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        draw = ImageDraw.Draw(probe)
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]

    def _layout_font_for(self, highlighted: bool) -> ImageFont.FreeTypeFont:
        if not highlighted:
            return self.base_font
        size = int(self.config.font_size * self.config.highlight_scale)
        return self._load_sized_font(size)

    def _draw_font_for(self, highlighted: bool, pulse: float) -> ImageFont.FreeTypeFont:
        if not highlighted:
            return self.base_font
        size = int(self.config.font_size * self.config.highlight_scale * pulse)
        return self._load_sized_font(size)

    @lru_cache(maxsize=64)
    def _load_sized_font(self, size: int) -> ImageFont.FreeTypeFont:
        return load_font(self.font_path, size)
