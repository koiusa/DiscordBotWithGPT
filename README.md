## 機能一覧
 - レートリミット (非メンション自動応答)
 - 検索積極モード (SEARCH_AGGRESSIVE_MODE)
- 構造化ログ (event=... key=value ... 形式)
  - モジュール階層再編 (infra / discord / search / llm / core 分離進行中)
## 開発 / 運用 Tips
### ログ
本Botは主要イベントを 1 行 = 1 イベントの構造化ログで出力します。

形式:
```
event=<名称> uptime_s=<起動から秒> key1=value1 key2="空白含む値" ...
```

主なイベント例:
```
event=on_message author_id=123456 channel_id=789012 preview="hello" uptime_s=12.3
event=address_check addressed=True reasons=name_prefix uptime_s=12.3
event=search_decision type=query score=3 reasons=pattern:.*最新 uptime_s=12.4 query="GPU 市場 現在 2025 最新"
event=openai_call attempt=1 purpose=completion invoke_ms=842.1 queue_wait_ms=0.3 prompt_tokens=142 completion_tokens=256 total_tokens=398 model=gpt-4o
event=openai_retry attempt=1 sleep_ms=800 retriable=True
event=openai_call_failed purpose=completion attempt=3 retriable=True error="rate limit"
event=websearch_connectivity status=OK error=-
```

検索判定や OpenAI 呼び出しは再試行/失敗/成功をそれぞれ別イベントで可観測化。

集計例 (シェル):
```bash
grep 'event=openai_call ' bot.log | awk '{for(i=1;i<=NF;i++){if($i~"invoke_ms="){sub("invoke_ms=","",$i);print $i}}}' | awk '{sum+=$1; n++} END{print "avg_invoke_ms="sum/n}'
```

カスタム解析ツールへ投入しやすいシンプル形式を優先。JSON が必要な場合は log_event 実装を差し替えても良いです。
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

### アーキテクチャ再編 (完了)
ディレクトリ階層を責務ごとに分離し保守性と拡張性を向上しました。

新構成:
```
sub/
  infra/        # 横断的基盤 (logging)
    logging.py  # 構造化ログ (log_event, logger)
  discord/      # Discord固有ユーティリティ
    discord_utils.py  # Discord メッセージ変換、スレッド操作等
  search/       # 検索機能
    search_decision.py  # 検索要否判定とクエリ最適化
    search_context.py   # 検索実行とコンテキスト構築
    websearch.py        # DuckDuckGo/Google 検索実装
    websearch_cache.py  # 検索結果 LRU+TTL キャッシュ
  llm/          # LLM呼び出し/トークン管理
    openai_wrapper.py   # OpenAI ChatCompletion ラッパ
    completion.py       # 応答生成メインロジック
    message_augment.py  # メッセージ拡張（会話履歴/検索結果注入）
    token_utils.py      # トークン概算ユーティリティ
  core/         # ドメインモデル
    base.py     # Message, Conversation, Config 等基本データ構造
  
  # 互換シム (Deprecation 警告付き)
  utils.py      # infra.logging / discord.discord_utils 再エクスポート
  base.py       # core.base 再エクスポート
  completion.py # llm.completion 再エクスポート
  (その他旧パス用シム)
```

移行完了したアイテム:
- ✅ 構造化ログを `infra.logging` へ統合
- ✅ Discord依存ユーティリティを `discord.discord_utils` へ分離
- ✅ 検索関連を `search/` パッケージ化 (判定・実行・キャッシュ)
- ✅ LLM呼び出しを `llm/` 下に統合 (OpenAI ラッパ・完了・拡張)
- ✅ ドメインモデルを `core/` 下に配置
- ✅ 後方互換シムで既存コード保護 (deprecation ログ付き)
- ✅ 全 import パスを新構成に更新

利用者影響:
新規開発では新パス（例: `from sub.search.search_decision import ...`）推奨。旧パス利用時は初回のみ deprecation ログが出力されますが機能は保持されます。

将来計画:
- constants.py の設定読み込み分離 (config_loader)
- 使用頻度に応じた旧シム段階削除

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
| `RESPOND_WITHOUT_MENTION` | メンション無しでも通常チャンネルで自動応答(1で有効) | 1 | 1 |
| `RATE_LIMIT_WINDOW_SEC` | 非メンション自動応答対象のレート制限ウィンドウ秒 | 30 | 30 |
| `RATE_LIMIT_MAX_EVENTS` | ウィンドウ内ユーザー毎最大メッセージ数 | 5 | 5 |
| `DISCLAIMER_ENABLE_ENGLISH` | 英語の免責/不要定型文も除去 (1=する/0=しない) | 1 | 1 |
| `DISCLAIMER_EXTRA_PATTERNS` | 追加除去したい正規表現パターン(|区切り) |  |  |
| `SEARCH_AGGRESSIVE_MODE` | 検索トリガを緩和し積極的に検索 (1=有効) | 0 | 0 |

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

### メンション不要応答オプション
`RESPOND_WITHOUT_MENTION=1` を有効化すると、Bot への明示メンションや名前プレフィックスが無くても通常チャンネル発言に反応します。

推奨運用:
1. Bot専用チャンネルを用意しノイズを隔離
2. 他Botとの応答ループは `author.bot` 無視で回避済み
3. 必要なら将来: レート制限 (例: 発話間隔 or 1分あたりN件) 導入を検討
4. `RESPOND_WITHOUT_MENTION=0` に戻せば従来どおりメンション/名前/リプライ時のみ応答
5. スパム保護: `RATE_LIMIT_WINDOW_SEC` (既定30秒) と `RATE_LIMIT_MAX_EVENTS` (既定5件) を超えると非メンション自動応答を一時的に無視

### 積極検索モード
`SEARCH_AGGRESSIVE_MODE=1` を設定すると以下が有効になります:
1. スコア閾値 `min_score` を 2 → 1 に引き下げ (より多くのメッセージで検索)
2. 明示的スコア0でも以下条件で検索候補化: 末尾 `?` / `？` / 含む語: `教えて`, `とは`, `まとめて`, `一覧`
3. ログに `aggressive_form` が理由として追加されるケースあり
用途: 情報探索寄りのサーバーで検索ヒット率を高めたい場合。
注意: 外部検索回数増 → レイテンシ/トークン消費上昇。

