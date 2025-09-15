# DiscordBotWithGPT


[![GitHub commit activity](https://img.shields.io/github/commit-activity/m/koiusa/DiscordBotWithGPT)](https://github.com/koiusa/DiscordBotWithGPT/graphs/commit-activity)
[![GitHub issues](https://img.shields.io/github/issues/koiusa/DiscordBotWithGPT)](https://github.com/koiusa/DiscordBotWithGPT/issues)
[![GitHub license](https://img.shields.io/github/license/koiusa/DiscordBotWithGPT)](https://github.com/koiusa/DiscordBotWithGPT/blob/main/LICENSE)

### Testing Env
```
$ cat /etc/os-release
PRETTY_NAME="Ubuntu 24.04.3 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"
VERSION="24.04.3 LTS (Noble Numbat)"
VERSION_CODENAME=noble
ID=ubuntu
ID_LIKE=debian
HOME_URL="https://www.ubuntu.com/"
SUPPORT_URL="https://help.ubuntu.com/"
BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
UBUNTU_CODENAME=noble
LOGO=ubuntu-logo
```

```
gpt-4.1
```

---

### Setup

#### Create Discord Bot
 - [discord_developers](https://discord.com/developers/applications)
 
#### Getting OpenApi ApiKey
 - [openai_platform](https://platform.openai.com)

#### Setting Env File
以下の手順で.envファイルを作成・設定してください。

1. `.env.example` をコピーして `.env` ファイルを作成します。
    ```bash
    cp .env.example .env
    ```
2. `.env` ファイルを開き、必要な値を記入します。
    - `OPENAI_API_KEY` には OpenAI の API キーを入力します。
    - `DISCORD_BOT_TOKEN` には Discord Bot のトークンを入力します。
    - `DISCORD_CLIENT_ID` には Discord アプリのクライアントIDを入力します。
    - `ALLOWED_SERVER_IDS` にはBotを許可するサーバーIDをカンマ区切りで入力します。
3. 必要に応じて他の項目も設定してください。

#### モデル・システムプロンプトの設定
`app/src/sub/config.yaml` で、使用するAIモデルやシステムプロンプトの内容を設定できます。
```bash app/src/sub/config.yaml
model: gpt-4.1
name: Chappie
example_conversations:
  - messages:
    - role: system
      user: nobody
      content: あなたはChappieです。優秀なAIアシスタントでユーザーの様々な質問に答えます。会話履歴では username(userId): content 形式で与えられます。ユーザーIDで同一人物性を判断し、混同しないでください。複数のユーザーが参加している場合は、それぞれのユーザーを区別して適切に応答してください。
```

### ユーザー識別機能
v1.1.0 以降、複数ユーザーが同一チャンネルで会話する際に、AIが発言者を正確に識別できるようになりました。

#### 主な機能:
- **会話履歴の保存**: チャンネル単位で会話履歴を自動保存（デフォルト30件まで）
- **発言者の識別**: `username(userId): content` 形式でAIに会話履歴を提供
- **循環バッファ**: 設定した件数を超えると古いメッセージから自動削除

#### 設定項目:
- `HISTORY_MAX_ITEMS`: 保持する会話履歴の最大件数（デフォルト: 30）

---

### Startup

#### Docker Compose で起動

```bash
cd path/to/DiscordBotWithGPT
docker-compose up -d
```

- 初回起動時は `.env` の設定を忘れずに行ってください。
- サービスの停止は `docker-compose down` で可能です。

---

### Discord command

Chat Start on Thread 
```
/thread "any message"
```

Chat Start Current Channel
```
/message "any message"
```

Web Search
```
/websearch "search query"
```

また、＠BotName "any Message" でもメッセージを送信できます。
（※「＠BotName」はBot名なので、実際のBot名に置き換えてください）

---

### Reference
 - [gpt-discord-bot](https://github.com/openai/gpt-discord-bot)

---

### 追加機能 (Refactor 後)
- Web検索 (DuckDuckGo + Google Fallback) + 検索要否スコアリング
- 会話要約 (しきい値超過時に自動圧縮 `SUMMARY_*` 環境変数で調整)
- OpenAI 呼び出し共通ラッパ (再試行 / セマフォ / 計測)
- 検索結果キャッシュ (LRU + TTL / `WEBSEARCH_CACHE_*`)
- 免責(リアルタイム不可)自動除去・ガイドライン挿入
- メッセージ拡張セクション差分更新 (会話/検索/ガイドライン)
- トークン & コストロギング、要約適用有無、検索実行/キャッシュヒット記録

### 主要ログ例
```
openai_metrics decision=QUERY decision_score=3 decision_reasons=['pattern:.*最新', 'factual_keyword'] \
  prompt_tokens=1234 completion_tokens=456 total_tokens=1690 queue_wait_ms=12.3 invoke_ms=842.1 attempt=1 \
  messages=9 reply_chars=1023 cost_prompt=0.006170 cost_completion=0.006840 cost_total=0.013010 \
  summary_applied=True augment_truncated=False augment_sections=### <CONVERSATION_CONTEXT>,### <SEARCH_CONTEXT>,### <GUIDELINE> search_executed=True
```

### 追加環境変数
| 変数 | 説明 | 例 | 既定 |
| ---- | ---- | ---- | ---- |
| `SUMMARY_TRIGGER_PROMPT_TOKENS` | 概算プロンプトトークン数しきい値 | 2800 | 2800 |
| `SUMMARY_TARGET_REDUCTION_RATIO` | 要約後目標長 (元の何倍) | 0.5 | 0.5 |
| `SUMMARY_MAX_SOURCE_CHARS` | 要約対象の最大文字数 | 8000 | 8000 |
| `SUMMARY_MODEL` | 要約モデル (未指定ならメイン) | gpt-4o-mini | main model |
| `WEBSEARCH_CACHE_TTL` | 検索キャッシュ TTL 秒 | 300 | 180 |
| `WEBSEARCH_CACHE_MAX` | キャッシュ最大件数 | 256 | 128 |

`.env.example` を参照して `.env` を作成してください。

### セキュリティ注意
リポジトリに本物の API キーをコミットしないでください。万一履歴に含めた場合は以下を実施:
1. OpenAI / Discord でキー再発行
2. 旧キー無効化
3. `.env` を更新 (コミットしない)
4. 公開済みコミットからキー文字列を含むか再確認 ( `git log -S` など)

`.gitignore` に `.env` が含まれていることを確認:
```
echo ".env" >> .gitignore
```
既に push 済みのキーは public から必ず撤収 (ローテ) してください。

