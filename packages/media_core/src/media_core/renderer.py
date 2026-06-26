from dataclasses import dataclass
from functools import lru_cache
import math
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from .legacy_config import ANCIENT_BACKGROUND, VideoConfig
from .font_utils import find_ancient_font, load_font


@dataclass(frozen=True)
class TextToken:
    text: str
    highlighted: bool
    color: tuple[int, int, int, int] | None = None


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
        self.ancient_font_path = find_ancient_font()
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
        background: Image.Image | None = None,
        background_motion: str = "zoom_in",
        background_position: tuple[float, float] = (0.5, 0.5),
        caption_duration: float | None = None,
    ) -> np.ndarray:
        caption_duration = min(max(caption_duration or duration, 0.001), duration)
        intro_transition, outro_transition = self._split_transition(transition)
        transform = self._caption_transform(t, caption_duration, intro_transition, outro_transition)
        caption = self._render_caption_tokens(tokens, self._highlight_pulse(t, caption_duration))

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

        frame = self._background_frame(background, t, duration, background_motion, background_position)
        x = (self.config.width - caption.width) // 2 + transform.offset_x
        caption_position_y = min(max(float(self.config.caption_position_y), 0.05), 0.95)
        y = int(self.config.height * caption_position_y - caption.height / 2) + transform.offset_y
        frame.paste(caption, (x, y), caption)
        return np.array(frame)

    def frame_queue(
        self,
        segments: tuple[tuple[TextToken, ...], ...],
        index: int,
        t: float,
        duration: float,
        background: Image.Image | None = None,
        background_motion: str = "zoom_in",
        background_position: tuple[float, float] = (0.5, 0.5),
        caption_duration: float | None = None,
    ) -> np.ndarray:
        caption_duration = min(max(caption_duration or duration, 0.001), duration)
        frame = self._background_frame(background, t, duration, background_motion, background_position)
        layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))

        intro = min(1.0, t / max(0.001, self.config.intro_duration))
        outro_start = max(self.config.intro_duration, caption_duration - self.config.outro_duration)
        outro = min(max((t - outro_start) / max(0.001, self.config.outro_duration), 0.0), 1.0)
        intro_eased = ease_out_cubic(intro)
        outro_eased = ease_out_cubic(outro)

        for slot, prev_index in enumerate(range(max(0, index - 2), index)):
            distance = index - prev_index
            caption = self._render_caption_tokens(segments[prev_index], 1.0)
            scale = 0.58 - 0.12 * min(distance - 1, 1)
            x = int(self.config.width * (0.05 + 0.10 * slot))
            y = int(self.config.height * (0.20 + 0.16 * slot - 0.05 * intro_eased))
            opacity = 0.62 if distance == 1 else 0.38
            self._paste_transformed(layer, caption, x, y, scale, opacity, rotation=-90)

        for slot, next_index in enumerate(range(index + 1, min(len(segments), index + 3))):
            caption = self._render_caption_tokens(segments[next_index], 1.0)
            scale = 0.54 - 0.08 * slot
            x = int(self.config.width * 0.50)
            y = int(self.config.height * (0.76 + 0.10 * slot - 0.035 * intro_eased - 0.06 * outro_eased))
            opacity = 0.58 if slot == 0 else 0.34
            self._paste_transformed(layer, caption, x, y, scale, opacity, anchor="center")

        current = self._render_caption_tokens(segments[index], self._highlight_pulse(t, caption_duration))
        if outro > 0:
            scale = 1.0 - 0.45 * outro_eased
            x = int(self.config.width * (0.50 - 0.38 * outro_eased))
            y = int(self.config.height * (0.47 - 0.18 * outro_eased))
            rotation = -90 * outro_eased
            opacity = 1.0 - 0.22 * outro_eased
        else:
            pop = 0.82 + 0.22 * intro_eased
            settle = 1.0 + 0.04 * math.sin(min(1.0, intro) * math.pi)
            scale = pop * settle
            x = int(self.config.width * 0.50)
            y = int(self.config.height * (0.48 - 0.035 * (1.0 - intro_eased)))
            rotation = 0.0
            opacity = 1.0
        self._paste_transformed(layer, current, x, y, scale, opacity, rotation=rotation, anchor="center")

        frame = Image.alpha_composite(frame.convert("RGBA"), layer).convert("RGB")
        return np.array(frame)

    def frame_ancient(
        self,
        tokens: tuple[TextToken, ...],
        t: float,
        duration: float,
        background: Image.Image | None = None,
        background_motion: str = "zoom_in",
        background_position: tuple[float, float] = (0.5, 0.5),
        timeline_start: float = 0.0,
        caption_duration: float | None = None,
    ) -> np.ndarray:
        caption_duration = min(max(caption_duration or duration, 0.001), duration)
        if background is None:
            frame = self._default_ancient_background().copy()
        else:
            frame = self._background_frame(background, t, duration, background_motion, background_position)
            frame = self._stylize_ancient_background(frame)
        frame = self._composite_ancient_smoke(frame, timeline_start + t)

        entries = self._ancient_timeline(tokens, caption_duration)
        if not entries:
            return np.array(frame)

        layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        max_rows = 7
        placements: list[tuple[tuple[str, bool, float, float, bool], int, int]] = []
        column = 0
        row = 0
        for entry in entries:
            force_new_column = entry[4]
            if placements and (force_new_column or row >= max_rows):
                column += 1
                row = 0
            placements.append((entry, column, row))
            row += 1
        column_count = max(1, column + 1)
        visible_rows = max((row_index for _, _, row_index in placements), default=0) + 1
        usable_height = self.config.height * 0.72
        usable_width = self.config.width * 0.78
        size_by_height = int(usable_height / max(1.0, visible_rows * 1.12))
        size_by_width = int(usable_width / max(1.0, column_count * 1.22))
        dynamic_cap = max(72, int(self.config.font_size * 3.2))
        font_size = max(42, min(size_by_height, size_by_width, dynamic_cap))
        row_pitch = int(font_size * 1.12)
        column_pitch = int(font_size * 1.22)
        top = int((self.config.height - visible_rows * row_pitch) / 2 + row_pitch * 0.05)
        rightmost_x = int(
            self.config.width / 2 + (column_count - 1) * column_pitch / 2
        )

        for entry, column, row in placements:
            char, highlighted, appear_time, transition_duration, _ = entry
            if t < appear_time:
                continue
            progress = ease_out_cubic((t - appear_time) / max(0.001, transition_duration))
            glyph = self._render_ancient_glyph(char, highlighted, font_size)
            x = rightmost_x - column * column_pitch - glyph.width // 2
            y = top + row * row_pitch + (row_pitch - glyph.height) // 2

            if progress < 1.0:
                haze = glyph.filter(ImageFilter.GaussianBlur(radius=max(0.2, 7.0 * (1.0 - progress))))
                haze_alpha = haze.getchannel("A").point(lambda value: int(value * progress * 0.55))
                haze.putalpha(haze_alpha)
                layer.paste(haze, (x, y), haze)
                glyph = glyph.copy()
                glyph_alpha = glyph.getchannel("A").point(lambda value: int(value * progress))
                glyph.putalpha(glyph_alpha)
            layer.paste(glyph, (x, y), glyph)

        frame = Image.alpha_composite(frame.convert("RGBA"), layer).convert("RGB")
        return np.array(frame)

    def _ancient_timeline(
        self,
        tokens: tuple[TextToken, ...],
        duration: float,
    ) -> list[tuple[str, bool, float, float, bool]]:
        punctuation_weights = {
            "，": 0.55,
            ",": 0.55,
            "、": 0.35,
            "；": 0.7,
            ";": 0.7,
            "。": 0.95,
            ".": 0.95,
            "！": 0.9,
            "!": 0.9,
            "？": 0.9,
            "?": 0.9,
            "：": 0.5,
            ":": 0.5,
        }
        column_break_punctuation = {"，", ",", "；", ";", "。", ".", "！", "!", "？", "?", "：", ":"}
        raw_entries: list[tuple[str, bool, float, bool]] = []
        cursor = 0.0
        force_new_column = False
        for token in tokens:
            for char in token.text:
                if char.isspace():
                    continue
                if char in punctuation_weights:
                    cursor += punctuation_weights[char]
                    if char in column_break_punctuation:
                        force_new_column = True
                    continue
                raw_entries.append((char, token.highlighted, cursor, force_new_column))
                force_new_column = False
                cursor += 1.0

        if not raw_entries:
            return []
        total_weight = max(cursor, 1.0)
        reveal_start = min(0.16, max(0.04, duration * 0.05))
        hold_duration = min(0.8, max(0.32, duration * 0.16))
        reveal_duration = max(0.12, duration - reveal_start - hold_duration)
        transition_duration = max(
            0.07,
            min(0.18, reveal_duration / max(1, len(raw_entries)) * 0.70),
        )
        return [
            (
                char,
                highlighted,
                reveal_start + (weight / total_weight) * reveal_duration,
                transition_duration,
                break_before,
            )
            for char, highlighted, weight, break_before in raw_entries
        ]

    @lru_cache(maxsize=512)
    def _render_ancient_glyph(self, char: str, highlighted: bool, font_size: int) -> Image.Image:
        font = load_font(self.ancient_font_path, font_size)
        probe = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        draw = ImageDraw.Draw(probe)
        is_hanyi_shangwei = "hyshangweishoushu" in self.ancient_font_path.lower()
        if is_hanyi_shangwei:
            ink_stroke = max(1, font_size // 90)
            outer_stroke = ink_stroke + 1
        else:
            ink_stroke = max(3, font_size // 22)
            outer_stroke = ink_stroke + max(1, font_size // 70)
        bbox = draw.textbbox((0, 0), char, font=font, stroke_width=outer_stroke)
        padding = max(10, font_size // 7)
        width = max(1, bbox[2] - bbox[0] + padding * 2)
        height = max(1, bbox[3] - bbox[1] + padding * 2)
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        color = (142, 31, 24, 255) if highlighted else (8, 8, 7, 255)
        outline = (226, 226, 216, 130)
        draw.text(
            (padding - bbox[0], padding - bbox[1]),
            char,
            font=font,
            fill=color,
            stroke_width=outer_stroke,
            stroke_fill=outline,
        )
        draw.text(
            (padding - bbox[0], padding - bbox[1]),
            char,
            font=font,
            fill=color,
            stroke_width=ink_stroke,
            stroke_fill=color,
        )
        return image

    @lru_cache(maxsize=8)
    def _default_ancient_background(self) -> Image.Image:
        width = self.config.width
        height = self.config.height
        if ANCIENT_BACKGROUND.exists():
            with Image.open(ANCIENT_BACKGROUND) as source:
                return ImageOps.fit(
                    source.convert("RGB"),
                    (width, height),
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, 0.5),
                )

        yy, xx = np.mgrid[0:height, 0:width]
        nx = (xx - width * 0.50) / max(1.0, width * 0.58)
        ny = (yy - height * 0.47) / max(1.0, height * 0.55)
        radius = np.sqrt(nx * nx + ny * ny)
        glow = np.clip(1.0 - radius, 0.0, 1.0) ** 1.7
        rng = np.random.default_rng(20260621)
        small_noise = rng.normal(0.0, 1.0, (max(2, height // 24), max(2, width // 24)))
        noise_image = Image.fromarray(np.uint8(np.clip((small_noise + 3.0) * 36.0, 0, 255)))
        noise = np.asarray(
            noise_image.resize((width, height), Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(18)),
            dtype=np.float32,
        )
        noise = (noise - noise.mean()) * 0.24
        value = np.clip(22.0 + glow * 166.0 + noise, 10.0, 205.0)
        rgb = np.stack((value * 0.91, value * 0.96, value), axis=-1).astype(np.uint8)
        image = Image.fromarray(rgb, mode="RGB")

        fog = Image.new("RGBA", image.size, (0, 0, 0, 0))
        fog_draw = ImageDraw.Draw(fog)
        fog_draw.ellipse(
            (-width * 0.20, height * 0.30, width * 1.10, height * 0.78),
            fill=(225, 230, 228, 34),
        )
        fog_draw.ellipse(
            (width * 0.05, height * 0.55, width * 1.30, height * 0.95),
            fill=(205, 215, 216, 22),
        )
        fog = fog.filter(ImageFilter.GaussianBlur(max(24, width // 10)))
        return Image.alpha_composite(image.convert("RGBA"), fog).convert("RGB")

    @lru_cache(maxsize=8)
    def _ancient_smoke_layers(self) -> tuple[Image.Image, ...]:
        width = int(self.config.width * 1.48)
        height = int(self.config.height * 1.32)
        layers: list[Image.Image] = []
        for seed, tint, strength in (
            (721, (228, 234, 231), 88.0),
            (1931, (177, 193, 192), 68.0),
            (4093, (238, 239, 232), 52.0),
        ):
            rng = np.random.default_rng(seed)
            noise_height = max(12, height // 38)
            noise_width = max(12, width // 38)
            noise = rng.random((noise_height, noise_width), dtype=np.float32)
            noise_image = Image.fromarray(np.uint8(noise * 255.0), mode="L")
            noise_image = noise_image.resize((width, height), Image.Resampling.BICUBIC)
            noise_image = noise_image.filter(ImageFilter.GaussianBlur(max(18, self.config.width // 22)))
            values = np.asarray(noise_image, dtype=np.float32)
            values = (values - values.min()) / max(1.0, values.max() - values.min())
            alpha = np.uint8(np.clip((values - 0.36) * strength, 0.0, strength))
            layer = Image.new("RGBA", (width, height), (*tint, 0))
            layer.putalpha(Image.fromarray(alpha, mode="L"))
            layers.append(layer)
        return tuple(layers)

    def _composite_ancient_smoke(self, frame: Image.Image, t: float) -> Image.Image:
        result = frame.convert("RGBA")
        width, height = frame.size
        for index, layer in enumerate(self._ancient_smoke_layers()):
            travel_x = max(0, layer.width - width)
            travel_y = max(0, layer.height - height)
            if index == 0:
                x = int((0.5 + 0.34 * math.sin(t * 0.31) + 0.16 * math.sin(t * 0.097 + 1.2)) * travel_x)
                y = int((0.5 + 0.31 * math.cos(t * 0.21 + 0.8) + 0.19 * math.sin(t * 0.073)) * travel_y)
            elif index == 1:
                x = int((0.5 + 0.32 * math.cos(t * 0.25 + 1.6) + 0.18 * math.sin(t * 0.081)) * travel_x)
                y = int((0.5 + 0.35 * math.sin(t * 0.28 + 2.1) + 0.15 * math.cos(t * 0.093)) * travel_y)
            else:
                x = int((0.5 + 0.36 * math.sin(t * 0.19 + 2.8) + 0.14 * math.cos(t * 0.071)) * travel_x)
                y = int((0.5 + 0.33 * math.cos(t * 0.17 + 0.3) + 0.17 * math.sin(t * 0.089)) * travel_y)
            smoke = layer.crop((x, y, x + width, y + height))
            result = Image.alpha_composite(result, smoke)
        return result.convert("RGB")

    def _stylize_ancient_background(self, image: Image.Image) -> Image.Image:
        gray = ImageOps.grayscale(image)
        toned = ImageOps.colorize(gray, black=(8, 13, 14), white=(205, 214, 212))
        shade = self._ancient_vignette_mask(*toned.size)
        overlay = Image.new("RGBA", toned.size, (0, 0, 0, 0))
        overlay.putalpha(shade)
        return Image.alpha_composite(toned.convert("RGBA"), overlay).convert("RGB")

    @lru_cache(maxsize=8)
    def _ancient_vignette_mask(self, width: int, height: int) -> Image.Image:
        yy, xx = np.mgrid[0:height, 0:width]
        nx = (xx - width / 2) / max(1.0, width / 2)
        ny = (yy - height / 2) / max(1.0, height / 2)
        vignette = np.clip((nx * nx + ny * ny - 0.18) * 105.0, 0.0, 145.0).astype(np.uint8)
        return Image.fromarray(vignette, mode="L")

    def _background_frame(
        self,
        background: Image.Image | None,
        t: float,
        duration: float,
        motion: str,
        position: tuple[float, float] = (0.5, 0.5),
    ) -> Image.Image:
        if background is None:
            return Image.new("RGB", (self.config.width, self.config.height), self.config.background_color)

        source = background.convert("RGB")
        target_ratio = self.config.width / self.config.height
        source_ratio = source.width / max(1, source.height)
        if source_ratio > target_ratio:
            base_height = source.height
            base_width = int(base_height * target_ratio)
        else:
            base_width = source.width
            base_height = int(base_width / target_ratio)

        focus_x = min(max(float(position[0]), 0.0), 1.0)
        focus_y = min(max(float(position[1]), 0.0), 1.0)
        base_left = (source.width - base_width) * focus_x
        base_top = (source.height - base_height) * focus_y

        progress = min(max(t / max(0.001, duration), 0.0), 1.0)
        amount = max(0.0, min(0.20, self.config.background_motion_amount))
        if motion == "zoom_out":
            zoom = 1.0 + amount * (1.0 - progress)
        else:
            zoom = 1.0 + amount * progress
        if motion in {"pan_left", "pan_right", "pan_up", "pan_down"}:
            zoom = 1.0 + max(amount, 0.06)

        crop_width = max(1, int(base_width / zoom))
        crop_height = max(1, int(base_height / zoom))
        center_x = base_left + base_width / 2.0
        center_y = base_top + base_height / 2.0
        travel_x = max(0.0, (base_width - crop_width) / 2.0)
        travel_y = max(0.0, (base_height - crop_height) / 2.0)
        if motion == "pan_left":
            center_x += travel_x * (1.0 - 2.0 * progress)
        elif motion == "pan_right":
            center_x += travel_x * (-1.0 + 2.0 * progress)
        elif motion == "pan_up":
            center_y += travel_y * (1.0 - 2.0 * progress)
        elif motion == "pan_down":
            center_y += travel_y * (-1.0 + 2.0 * progress)

        left = int(round(center_x - crop_width / 2.0))
        top = int(round(center_y - crop_height / 2.0))
        left = min(max(left, 0), max(0, source.width - crop_width))
        top = min(max(top, 0), max(0, source.height - crop_height))
        image = source.crop((left, top, left + crop_width, top + crop_height))
        image = image.resize((self.config.width, self.config.height), Image.Resampling.LANCZOS)

        dim = max(0.0, min(0.85, self.config.background_image_dim))
        if dim:
            overlay = Image.new("RGBA", image.size, (0, 0, 0, int(255 * dim)))
            image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
        return image

    def _caption_transform(self, t: float, duration: float, intro_transition: str, outro_transition: str) -> CaptionTransform:
        intro_duration = max(0.001, self.config.intro_duration)
        outro_duration = max(0.001, self.config.outro_duration)
        outro_start = max(intro_duration, duration - outro_duration)

        if t < intro_duration:
            return self._intro_transform(t / intro_duration, intro_transition)
        if t >= outro_start:
            progress = min(max((t - outro_start) / outro_duration, 0.0), 1.0)
            return self._outro_transform(progress, outro_transition)
        return CaptionTransform()

    def _split_transition(self, transition: str) -> tuple[str, str]:
        intro = "center_zoom"
        outro = transition or "shrink"
        for part in transition.split("|"):
            if part.startswith("intro:"):
                intro = part.split(":", 1)[1]
            elif part.startswith("outro:"):
                outro = part.split(":", 1)[1]
        return intro, outro

    def _intro_transform(self, progress: float, transition: str) -> CaptionTransform:
        eased = ease_out_cubic(progress)
        scale = 0.8 + 0.2 * eased
        if transition == "left_in":
            return CaptionTransform(scale_x=1.0, scale_y=1.0, offset_x=int(-self.config.width * 0.55 * (1.0 - eased)), opacity=0.35 + 0.65 * eased)
        if transition == "right_in":
            return CaptionTransform(scale_x=1.0, scale_y=1.0, offset_x=int(self.config.width * 0.55 * (1.0 - eased)), opacity=0.35 + 0.65 * eased)
        return CaptionTransform(scale_x=scale, scale_y=scale, opacity=0.45 + 0.55 * eased)

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
        if transition == "stand_left":
            scale = 1.0 - 0.15 * eased
            return CaptionTransform(
                scale_x=scale,
                scale_y=scale,
                offset_x=int(-self.config.width * 0.32 * eased),
                opacity=1.0 - 0.55 * eased,
                rotation=-90.0 * eased,
            )
        if transition == "stand_right":
            scale = 1.0 - 0.15 * eased
            return CaptionTransform(
                scale_x=scale,
                scale_y=scale,
                offset_x=int(self.config.width * 0.32 * eased),
                opacity=1.0 - 0.55 * eased,
                rotation=90.0 * eased,
            )
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
                color = self.config.highlight_color if token.highlighted else (token.color or self.config.text_color)
                bbox = draw.textbbox((0, 0), token.text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                draw_x = x + (slot_width - text_width) // 2
                draw_y = y + (line_height - text_height) // 2 - bbox[1]
                draw.text((draw_x, draw_y), token.text, fill=color, font=font)
                x += slot_width
            y += line_height + self.config.line_spacing
        return image

    def _paste_transformed(
        self,
        layer: Image.Image,
        caption: Image.Image,
        x: int,
        y: int,
        scale: float,
        opacity: float,
        rotation: float = 0.0,
        anchor: str = "topleft",
    ) -> None:
        scale = max(0.05, scale)
        transformed = caption.resize(
            (max(1, int(caption.width * scale)), max(1, int(caption.height * scale))),
            Image.Resampling.LANCZOS,
        )
        if rotation:
            transformed = transformed.rotate(rotation, resample=Image.Resampling.BICUBIC, expand=True)
        if opacity < 1.0:
            alpha = transformed.getchannel("A")
            alpha = alpha.point(lambda value: int(value * max(0.0, min(1.0, opacity))))
            transformed.putalpha(alpha)
        if anchor == "center":
            x -= transformed.width // 2
            y -= transformed.height // 2
        layer.paste(transformed, (x, y), transformed)

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
                self._append_char(lines[-1], char, token.highlighted, token.color)
                current_width += char_width

        return [line for line in lines if line]

    def _append_char(
        self,
        line: list[TextToken],
        char: str,
        highlighted: bool,
        color: tuple[int, int, int, int] | None = None,
    ) -> None:
        if line and line[-1].highlighted == highlighted and line[-1].color == color:
            line[-1] = TextToken(line[-1].text + char, highlighted, color)
        else:
            line.append(TextToken(char, highlighted, color))

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
