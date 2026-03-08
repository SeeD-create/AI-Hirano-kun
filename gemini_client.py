import time
import threading
import logging

from google import genai
from google.genai import types

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    CONVERSATION_HISTORY_MAX_TURNS,
    CONVERSATION_HISTORY_TTL,
    MAX_USERS_IN_MEMORY,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """あなたは「AI平野くん」という名前の、高校生・大学受験生向けの学習サポートAIアシスタントです。

## 基本的な性格・口調
- 親しみやすく、丁寧な口調で話します（「です・ます」調）
- 励ましの言葉を適度に入れます
- 難しい内容でもわかりやすく説明します

## 機能1: 英作文添削
ユーザーが英文を送ってきた場合、以下のフォーマットで添削してください：

【原文】
（ユーザーの英文をそのまま記載）

【添削後】
（修正した英文）

【修正ポイント】
1.（具体的な修正内容と理由を番号付きで列挙）

【表現のレベルアップ】
（より自然・高度な表現があれば提案）

【スコア】★☆☆☆☆ ～ ★★★★★（5段階で評価）

## 機能2: 質問回答
勉強に関する質問には、以下の方針で回答してください：
- まず結論を簡潔に述べる
- その後に詳しい説明を加える
- 必要に応じて具体例を示す
- 関連する重要事項があれば補足する

## 機能3: 画像入力対応
画像が送られてきた場合：
- 画像内の問題文を正確に読み取る
- 問題の解き方を段階的に説明する
- 最終的な答えを明示する

## 注意事項
- 回答はLINEで読みやすいよう、適度に改行を入れてください
- 勉強に無関係な質問には「勉強に関する質問をお願いします！」とやんわり断ってください
- 回答が長くなりすぎないよう、簡潔にまとめてください
"""


class GeminiClient:
    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.chat_sessions: dict = {}
        self.last_access: dict[str, float] = {}
        self._lock = threading.Lock()

    def _cleanup_old_sessions(self):
        """TTL超過・メモリ上限超過のセッションを削除"""
        now = time.time()
        with self._lock:
            expired = [
                uid
                for uid, ts in self.last_access.items()
                if now - ts > CONVERSATION_HISTORY_TTL
            ]
            for uid in expired:
                self.chat_sessions.pop(uid, None)
                self.last_access.pop(uid, None)

            if len(self.chat_sessions) > MAX_USERS_IN_MEMORY:
                sorted_users = sorted(self.last_access.items(), key=lambda x: x[1])
                to_remove = len(self.chat_sessions) - MAX_USERS_IN_MEMORY
                for uid, _ in sorted_users[:to_remove]:
                    self.chat_sessions.pop(uid, None)
                    self.last_access.pop(uid, None)

    def _get_or_create_chat(self, user_id: str):
        """ユーザーごとのチャットセッションを取得または新規作成"""
        self._cleanup_old_sessions()
        with self._lock:
            self.last_access[user_id] = time.time()
            if user_id not in self.chat_sessions:
                self.chat_sessions[user_id] = self.client.chats.create(
                    model=GEMINI_MODEL,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.7,
                    ),
                )
            return self.chat_sessions[user_id]

    def send_text(self, user_id: str, text: str) -> str:
        """テキストメッセージを送信し、応答を取得"""
        chat = self._get_or_create_chat(user_id)
        response = chat.send_message(text)
        return response.text

    def send_image(self, user_id: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
        """画像（+プロンプト）を送信し、応答を取得"""
        chat = self._get_or_create_chat(user_id)
        contents = [
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            "この画像の内容を確認して、問題があれば解答と解説をお願いします。英語の問題であれば添削も含めてください。",
        ]
        response = chat.send_message(contents)
        return response.text

    def reset_history(self, user_id: str):
        """ユーザーの会話履歴をリセット"""
        with self._lock:
            self.chat_sessions.pop(user_id, None)
            self.last_access.pop(user_id, None)
