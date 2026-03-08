import os
import uuid
import time
import re
import logging

from PIL import Image, ImageDraw, ImageFont

from config import (
    IMAGE_OUTPUT_DIR,
    FONT_PATH,
    IMAGE_CLEANUP_TTL,
    FONT_WEIGHT_REGULAR,
    FONT_WEIGHT_BOLD,
)

logger = logging.getLogger(__name__)

# 画像レンダリング定数
CANVAS_WIDTH = 800
PADDING = 40
MAX_TEXT_WIDTH = CANVAS_WIDTH - PADDING * 2
FONT_SIZE = 28
HEADING_FONT_SIZE = 32
LINE_SPACING = 12
PARAGRAPH_SPACING = 20
BG_COLOR = (255, 255, 255)
TEXT_COLOR = (33, 33, 33)
HEADING_COLOR = (25, 80, 160)
ACCENT_COLOR = (200, 60, 60)
DIVIDER_COLOR = (200, 200, 200)
PREVIEW_MAX_WIDTH = 240


class ImageRenderer:
    def __init__(self):
        os.makedirs(IMAGE_OUTPUT_DIR, exist_ok=True)
        self.font = self._load_font(FONT_SIZE, FONT_WEIGHT_REGULAR)
        self.font_bold = self._load_font(HEADING_FONT_SIZE, FONT_WEIGHT_BOLD)
        self._validate_japanese_rendering()

    def _load_font(self, size: int, weight: int):
        """Variable Fontを指定サイズ・ウェイトで読み込む"""
        try:
            font = ImageFont.truetype(FONT_PATH, size)
            font.set_variation_by_axes([weight])
            logger.info("Loaded font: %s (size=%d, weight=%d)", FONT_PATH, size, weight)
            return font
        except OSError:
            logger.error("CRITICAL: Font file not found at %s", FONT_PATH)
            return ImageFont.load_default(size=size)
        except Exception as e:
            logger.error("Font loading error: %s", e, exc_info=True)
            return ImageFont.load_default(size=size)

    def _validate_japanese_rendering(self):
        """起動時に日本語が描画できるか検証"""
        img = Image.new("RGB", (50, 50), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((5, 5), "あ", font=self.font, fill=(0, 0, 0))
        pixels = list(img.getdata())
        if any(p != (255, 255, 255) for p in pixels):
            logger.info("Font validation passed: Japanese glyphs render correctly.")
        else:
            logger.error(
                "CRITICAL: Font validation FAILED. Japanese text renders as blank/tofu. "
                "Check that %s exists and contains Japanese glyphs.", FONT_PATH
            )

    def render_text_to_image(self, text: str) -> tuple[str, str]:
        """テキストをPNG画像にレンダリングし、(original, preview) のファイル名を返す"""
        commands = self._parse_text(text)
        height = self._calculate_height(commands)
        img = Image.new("RGB", (CANVAS_WIDTH, height), BG_COLOR)
        draw = ImageDraw.Draw(img)
        self._draw_commands(draw, commands)

        file_id = uuid.uuid4().hex
        original_path = os.path.join(IMAGE_OUTPUT_DIR, f"{file_id}.png")
        preview_path = os.path.join(IMAGE_OUTPUT_DIR, f"{file_id}_p.png")

        img.save(original_path, "PNG", optimize=True)

        ratio = PREVIEW_MAX_WIDTH / CANVAS_WIDTH
        preview_size = (PREVIEW_MAX_WIDTH, max(1, int(height * ratio)))
        preview_img = img.resize(preview_size, Image.LANCZOS)
        preview_img.save(preview_path, "PNG", optimize=True)

        return f"{file_id}.png", f"{file_id}_p.png"

    def _parse_text(self, text: str) -> list[dict]:
        """Markdown風テキストを描画命令リストに変換"""
        commands = []
        lines = text.split("\n")

        for line in lines:
            stripped = line.strip()

            if not stripped:
                commands.append({"type": "spacing", "size": PARAGRAPH_SPACING})
                continue

            # 見出し (## or 【...】)
            if stripped.startswith("##") or (stripped.startswith("【") and "】" in stripped):
                heading_text = stripped.lstrip("#").strip()
                commands.append({"type": "heading", "text": heading_text})
                continue

            # 番号付きリスト
            if re.match(r"^\d+[\.\)]\s", stripped):
                commands.append({"type": "list_item", "text": stripped})
                continue

            # 箇条書き
            if stripped.startswith(("- ", "* ", "・")):
                commands.append({"type": "bullet", "text": stripped})
                continue

            # 星評価
            if "★" in stripped or "☆" in stripped:
                commands.append({"type": "accent", "text": stripped})
                continue

            # 通常テキスト
            commands.append({"type": "text", "text": stripped})

        return commands

    def _wrap_text(self, text: str, font, draw) -> list[str]:
        """テキストを画像幅に合わせて折り返し（日本語対応）"""
        lines = []
        current = ""

        for char in text:
            test = current + char
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] > MAX_TEXT_WIDTH:
                if current:
                    lines.append(current)
                current = char
            else:
                current = test

        if current:
            lines.append(current)

        return lines if lines else [""]

    def _calculate_height(self, commands: list[dict]) -> int:
        """描画命令リストから必要な画像の高さを計算"""
        dummy = Image.new("RGB", (CANVAS_WIDTH, 1))
        draw = ImageDraw.Draw(dummy)
        y = PADDING

        for cmd in commands:
            if cmd["type"] == "spacing":
                y += cmd["size"]
            elif cmd["type"] == "heading":
                wrapped = self._wrap_text(cmd["text"], self.font_bold, draw)
                y += len(wrapped) * (HEADING_FONT_SIZE + LINE_SPACING)
                y += PARAGRAPH_SPACING // 2 + 4  # 下線 + 余白
            elif cmd["type"] in ("text", "list_item", "bullet", "accent"):
                wrapped = self._wrap_text(cmd["text"], self.font, draw)
                y += len(wrapped) * (FONT_SIZE + LINE_SPACING)

        y += PADDING
        return max(y, 100)

    def _draw_commands(self, draw, commands: list[dict]):
        """描画命令リストを実際にキャンバスに描画"""
        y = PADDING

        for cmd in commands:
            if cmd["type"] == "spacing":
                y += cmd["size"]

            elif cmd["type"] == "heading":
                wrapped = self._wrap_text(cmd["text"], self.font_bold, draw)
                for line in wrapped:
                    draw.text((PADDING, y), line, font=self.font_bold, fill=HEADING_COLOR)
                    y += HEADING_FONT_SIZE + LINE_SPACING
                y += 2
                draw.line(
                    [(PADDING, y), (CANVAS_WIDTH - PADDING, y)],
                    fill=DIVIDER_COLOR,
                    width=2,
                )
                y += PARAGRAPH_SPACING // 2

            elif cmd["type"] == "accent":
                wrapped = self._wrap_text(cmd["text"], self.font, draw)
                for line in wrapped:
                    draw.text((PADDING, y), line, font=self.font, fill=ACCENT_COLOR)
                    y += FONT_SIZE + LINE_SPACING

            elif cmd["type"] == "bullet":
                wrapped = self._wrap_text(cmd["text"], self.font, draw)
                for line in wrapped:
                    draw.text((PADDING + 20, y), line, font=self.font, fill=TEXT_COLOR)
                    y += FONT_SIZE + LINE_SPACING

            elif cmd["type"] in ("text", "list_item"):
                wrapped = self._wrap_text(cmd["text"], self.font, draw)
                for line in wrapped:
                    draw.text((PADDING, y), line, font=self.font, fill=TEXT_COLOR)
                    y += FONT_SIZE + LINE_SPACING

    def cleanup_old_images(self):
        """古い画像ファイルを削除"""
        now = time.time()
        try:
            for fname in os.listdir(IMAGE_OUTPUT_DIR):
                fpath = os.path.join(IMAGE_OUTPUT_DIR, fname)
                if os.path.isfile(fpath) and fname.endswith(".png"):
                    if now - os.path.getmtime(fpath) > IMAGE_CLEANUP_TTL:
                        os.remove(fpath)
        except Exception as e:
            logger.error("Image cleanup error: %s", e)
