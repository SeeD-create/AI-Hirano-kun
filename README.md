# AI平野くん - LINE学習サポートBot

英作文の添削・質問回答・画像入力に対応した、高校生・受験生向けの学習サポートLINE Botです。

## 機能

- **英作文添削**: 英文を送ると、文法・語彙・表現の改善点を指摘し、修正後の英文を提示
- **質問回答**: 勉強に関する質問に分かりやすく回答
- **画像入力**: 問題の写真を送ると、読み取って解答・解説を提供
- **会話履歴**: ユーザーごとに文脈を記憶（「リセット」で履歴クリア）

## 技術構成

- Python (Flask) + gunicorn
- LINE Messaging API (line-bot-sdk v3)
- Google Gemini (gemini-3-flash-preview)
- デプロイ: Render

---

## セットアップ手順

### 1. LINE Developers Console

1. [LINE Developers Console](https://developers.line.biz/) にログイン
2. プロバイダーを選択（または新規作成）
3. 「Messaging API」チャネルを新規作成
   - チャネル名: `AI平野くん`
4. **チャネル基本設定** タブ → 「チャネルシークレット」をコピー
5. **Messaging API設定** タブで:
   - 「チャネルアクセストークン」を発行してコピー
   - 「応答メッセージ」→ **無効** にする
   - 「Webhook」→ **有効** にする
   - Webhook URL はデプロイ後に設定

### 2. Gemini API Key 取得

1. [Google AI Studio](https://aistudio.google.com/) にアクセス
2. 「Get API Key」→ APIキーを作成してコピー

### 3. ローカルで動作確認（任意）

```bash
# 依存パッケージのインストール
pip install -r requirements.txt

# 環境変数を設定
cp .env.example .env
# .env を編集して各キーを入力

# サーバー起動
python app.py

# ngrok でトンネルを作成（別ターミナル）
ngrok http 8000
```

ngrok の URL を LINE Developers Console の Webhook URL に設定:
`https://xxxx.ngrok.io/callback`

### 4. Render にデプロイ

1. このリポジトリを GitHub にプッシュ
2. [Render Dashboard](https://dashboard.render.com/) → New → Web Service
3. GitHub リポジトリを接続
4. 設定:
   - **Name**: `ai-hirano-kun`
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120`
   - **Plan**: Free
5. **Environment** で環境変数を追加:
   - `LINE_CHANNEL_SECRET`
   - `LINE_CHANNEL_ACCESS_TOKEN`
   - `GEMINI_API_KEY`
6. デプロイ完了後、Render の URL を LINE Developers Console の Webhook URL に設定:
   `https://ai-hirano-kun.onrender.com/callback`

### 5. 動作確認

LINEアプリから「AI平野くん」を友だち追加して、以下を試してください:

- テキストで「I go to school yesterday.」→ 英作文添削
- テキストで「三角関数のsin, cos, tanの違いを教えて」→ 質問回答
- 問題の写真を撮って送信 → 画像読み取り＆解答
- 「リセット」と送信 → 会話履歴クリア

## 注意事項

- Render無料枠は15分間アクセスがないとスリープします（初回応答に数十秒かかる場合があります）
- [UptimeRobot](https://uptimerobot.com/) 等で `https://ai-hirano-kun.onrender.com/` に定期アクセスすると、スリープを防げます
