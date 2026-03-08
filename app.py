import os
import logging
from flask import Flask, request, abort

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
)

from config import (
    LINE_CHANNEL_SECRET,
    LINE_CHANNEL_ACCESS_TOKEN,
    LINE_REPLY_MAX_LENGTH,
)
from gemini_client import GeminiClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
gemini = GeminiClient()


@app.route("/", methods=["GET"])
def health_check():
    return "AI平野くん is running!", 200


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
        reply_text = "会話履歴をリセットしました！新しい会話を始めましょう 📚"
    else:
        try:
            reply_text = gemini.send_text(user_id, user_text)
        except Exception as e:
            logger.error("Gemini API error: %s", e, exc_info=True)
            reply_text = "申し訳ありません、エラーが発生しました。もう一度お試しください 🙏"

    reply_text = truncate_reply(reply_text)
    send_reply(event.reply_token, reply_text)


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
        reply_text = "画像の処理中にエラーが発生しました。もう一度お試しください 🙏"

    reply_text = truncate_reply(reply_text)
    send_reply(event.reply_token, reply_text)


def truncate_reply(text: str) -> str:
    if len(text) > LINE_REPLY_MAX_LENGTH:
        return text[: LINE_REPLY_MAX_LENGTH - 30] + "\n\n...（文字数制限のため省略されました）"
    return text


def send_reply(reply_token: str, text: str):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)],
            )
        )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
