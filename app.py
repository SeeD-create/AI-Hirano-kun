import io
import os
import logging
from flask import Flask, request, abort, send_from_directory, send_file

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent,
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage,
    ImageMessage,
)

from config import (
    LINE_CHANNEL_SECRET,
    LINE_CHANNEL_ACCESS_TOKEN,
    LINE_REPLY_MAX_LENGTH,
    BASE_URL,
    IMAGE_OUTPUT_DIR,
)
from gemini_client import GeminiClient
from image_renderer import ImageRenderer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
gemini = GeminiClient()
renderer = ImageRenderer()


@app.route("/", methods=["GET"])
def health_check():
    return "AI平野くん is running!", 200


@app.route("/test-image", methods=["GET"])
def test_image():
    """サーバー上のフォント描画を診断するテスト画像"""
    from PIL import Image, ImageDraw, ImageFont
    from config import FONT_PATH

    info_lines = [f"Font path: {FONT_PATH}", f"Exists: {os.path.exists(FONT_PATH)}"]

    try:
        font = ImageFont.truetype(FONT_PATH, 28)
        info_lines.append("truetype: OK")
    except Exception as e:
        font = ImageFont.load_default(size=28)
        info_lines.append(f"truetype: FAILED ({e})")

    try:
        font.set_variation_by_axes([400])
        info_lines.append("variation: OK")
    except Exception as e:
        info_lines.append(f"variation: FAILED ({e})")

    img = Image.new("RGB", (600, 300), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    y = 10
    for line in info_lines:
        draw.text((10, y), line, font=ImageFont.load_default(size=16), fill=(100, 100, 100))
        y += 22
    y += 10
    draw.text((10, y), "日本語テスト: こんにちは世界", font=font, fill=(0, 0, 0))
    y += 40
    draw.text((10, y), "English test: Hello World", font=font, fill=(0, 0, 0))
    y += 40
    draw.text((10, y), "【見出し】★★★☆☆ 箇条書き・テスト", font=font, fill=(0, 0, 0))

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/images/<filename>", methods=["GET"])
def serve_image(filename):
    """生成した画像を配信"""
    return send_from_directory(IMAGE_OUTPUT_DIR, filename, mimetype="image/png")


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    logger.info("Request body: %s", body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.warning("Invalid signature")
        abort(400)

    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()

    if user_text in ("リセット", "reset"):
        gemini.reset_history(user_id)
        send_text_reply(event.reply_token, "会話履歴をリセットしました！新しい会話を始めましょう 📚")
        return

    try:
        reply_text = gemini.send_text(user_id, user_text)
    except Exception as e:
        logger.error("Gemini API error: %s", e, exc_info=True)
        send_text_reply(event.reply_token, "申し訳ありません、エラーが発生しました。もう一度お試しください 🙏")
        return

    send_image_reply(event.reply_token, reply_text)


@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event):
    user_id = event.source.user_id

    try:
        with ApiClient(configuration) as api_client:
            blob_api = MessagingApiBlob(api_client)
            image_bytes = blob_api.get_message_content(message_id=event.message.id)

        reply_text = gemini.send_image(
            user_id=user_id,
            image_bytes=image_bytes,
            mime_type="image/jpeg",
        )
    except Exception as e:
        logger.error("Image processing error: %s", e, exc_info=True)
        send_text_reply(event.reply_token, "画像の処理中にエラーが発生しました。もう一度お試しください 🙏")
        return

    send_image_reply(event.reply_token, reply_text)


def send_image_reply(reply_token: str, text: str):
    """テキストを画像にレンダリングして返信。失敗時はテキストフォールバック。"""
    renderer.cleanup_old_images()

    try:
        original_name, preview_name = renderer.render_text_to_image(text)
        original_url = f"{BASE_URL}/images/{original_name}"
        preview_url = f"{BASE_URL}/images/{preview_name}"

        messages = [
            ImageMessage(
                original_content_url=original_url,
                preview_image_url=preview_url,
            ),
        ]
    except Exception as e:
        logger.error("Image rendering error: %s", e, exc_info=True)
        messages = [TextMessage(text=truncate_reply(text))]

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages,
            )
        )


def send_text_reply(reply_token: str, text: str):
    """テキストのみで返信（リセット確認やエラー時）"""
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)],
            )
        )


def truncate_reply(text: str) -> str:
    if len(text) > LINE_REPLY_MAX_LENGTH:
        return text[: LINE_REPLY_MAX_LENGTH - 30] + "\n\n...（文字数制限のため省略されました）"
    return text


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
