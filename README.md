<!-- PROJECT HEADER -->

# DiscordBotWithGPT

複数ユーザー同時会話・要約・外部 Web 検索（DuckDuckGo + Google Fallback）・構造化ログ・再試行付き OpenAI ラッパ等を備えた Discord Bot。運用可観測性と拡張性を優先した構成です。

---

## 目次
1. [主な機能](#主な機能)
2. [スクリーンショット / 動作イメージ (任意)](#スクリーンショット--動作イメージ)
3. [セットアップ](#セットアップ)
4. [環境変数](#環境変数)
5. [検索アーキテクチャ](#検索アーキテクチャ)
6. [ログと計測](#ログと計測)
7. [ディレクトリ構成](#ディレクトリ構成)
8. [動作開始 / 起動方法](#動作開始--起動方法)
9. [Slash コマンド](#slash-コマンド)
10. [ユーザー識別と履歴管理](#ユーザー識別と履歴管理)
11. [要約機能](#要約機能)
12. [レート制限とスパム防止](#レート制限とスパム防止)
13. [開発 Tips](#開発-tips)
14. [トラブルシューティング](#トラブルシューティング)
15. [参考 / クレジット](#参考--クレジット)

---

## 主な機能
| 分類 | 機能 | 説明 |
| ---- | ---- | ---- |
| 会話 | 複数ユーザー識別 | `username(userId): content` 形式で履歴をLLMへ提供 |
| 会話 | 循環履歴バッファ | `HISTORY_MAX_ITEMS` で制御 (古いものから削除) |
| 会話 | 長文要約 | プロンプトが閾値超過時に自動要約し圧縮 (再参照可能) |
| 検索 | 検索要否判定スコアリング | 正規表現 + 疑問語 + 年度/時制トークン + Aggressive Mode |
| 検索 | DuckDuckGo + Google Fallback | 0件時にフォールバック / NO_RESULTS を明示 |
| 検索 | キャッシュ | LRU + TTL (`WEBSEARCH_CACHE_*`) |
| 検索 | ステータス分類 | OK / NO_RESULTS / ERROR / SKIPPED をログ出力 |
| 出力 | メッセージ拡張セクション | 会話 / 検索 / ガイドライン を差分注入 |
| コスト | トークン概算 / コスト試算 | `OPENAI_*_TOKEN_COST` による課金額目安表示 |
| 信頼性 | OpenAI ラッパ | 再試行 / バックオフ / メトリクス計測 |
| レート制御 | 非メンション応答レート制限 | 簡易 per-user window ベース制御 |
| 運用 | 構造化ログ | 1行=1イベント `key=value` 形式 (grep / awk 解析容易) |
| 運用 | Heartbeat | 30sごとのレイテンシ報告 |
| 運用 | 診断コマンド | `/diag` で quick websearch + latency |
| 互換 | 旧パス再エクスポート | 移行期間の破壊的変更緩和 (deprecation ログ) |

---

[![GitHub commit activity](https://img.shields.io/github/commit-activity/m/koiusa/DiscordBotWithGPT)](https://github.com/koiusa/DiscordBotWithGPT/graphs/commit-activity)
[![GitHub issues](https://img.shields.io/github/issues/koiusa/DiscordBotWithGPT)](https://github.com/koiusa/DiscordBotWithGPT/issues)
[![GitHub license](https://img.shields.io/github/license/koiusa/DiscordBotWithGPT)](https://github.com/koiusa/DiscordBotWithGPT/blob/main/LICENSE)

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

## セットアップ

#### Create Discord Bot
 - [discord_developers](https://discord.com/developers/applications)
 
#### Getting OpenApi ApiKey
 - [openai_platform](https://platform.openai.com)

### `.env` の作成
以下の手順で `.env` を作成・設定します。

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

### モデル・システムプロンプト設定
`app/src/sub/config.yaml` でモデル / bot 名 / システムプロンプト例を定義:
```bash app/src/sub/config.yaml
model: gpt-4.1
name: Chappie
example_conversations:
  - messages:
    - role: system
      user: nobody
      content: あなたはChappieです。優秀なAIアシスタントでユーザーの様々な質問に答えます。会話履歴では username(userId): content 形式で与えられます。ユーザーIDで同一人物性を判断し、混同しないでください。複数のユーザーが参加している場合は、それぞれのユーザーを区別して適切に応答してください。
```

## ユーザー識別機能
複数ユーザー混在チャンネルでの「だれが何を言ったか」を安定供給:
* チャンネル単位の短期履歴を循環保持 (`HISTORY_MAX_ITEMS`)
* LLM へは `username(userId): content` フォーマットで送信 (ユーザー混同防止)
* 直前メッセージは別引数として明示し、コンテキスト圧縮時も話者情報保持

---

## 動作開始 / 起動方法

### Docker Compose

```bash
cd path/to/DiscordBotWithGPT
docker-compose up -d
```

- 初回起動時は `.env` の設定を忘れずに行ってください。
- サービスの停止は `docker-compose down` で可能です。

---

## Slash コマンド

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

## ディレクトリ構成
```
app/src/sub/
  core/          # ドメインモデル (Message, Conversation, Config ...)
  infra/         # 横断基盤 (logging)
  discord/       # Discord 特有ユーティリティ (ID変換等)
  llm/           # OpenAI 呼び出し & 生成ロジック
  search/        # 検索判定/実行/キャッシュ/コンテキスト化
  history_store.py  # チャンネル別履歴保持
  format_conversation.py # 履歴→プロンプト整形
```
後方互換シムは段階的削除予定。新規コードは新パスを利用してください。

## 検索アーキテクチャ
```
user message
  └─ search_decision.should_perform_web_search() → SearchDecision
        ├─ DATETIME_ANSWER: 即時日付回答
        ├─ QUERY: クエリ最適化 → websearch.perform_web_search()
        └─ NONE: 検索スキップ
  └─ search_context.build_search_context() / (結果0件時 NO_RESULTS フォールバック文)
  └─ message_augment: <SEARCH_CONTEXT> セクションとして LLM プロンプトへ注入
  └─ completion: openai 呼び出し / メトリクスログ
```
ステータス:
| status | 意味 | `search_executed` |
| ------ | ---- | ---------------- |
| OK | 結果 >=1 件を取得し要約挿入 | False (結果はテキスト注入で十分 / 二次実行不要の設計) |
| NO_RESULTS | 検索実行したが 0 件 → フォールバック文章挿入 | False |
| SKIPPED | そもそも検索不要判定 | False |
| ERROR | 検索中例外 → エラーメッセージを代替挿入 | False |

`search_injected=True` は <SEARCH_CONTEXT> がプロンプトに含まれたことを意味。結果 0 件でも **検索を試行した事実 + フォールバック案内** がユーザー回答に反映されるため、ユーザー混乱を低減します。

## 要約機能
プロンプト文字数が `SUMMARY_TRIGGER_PROMPT_TOKENS` を超過 → 直近会話の一部を要約し再注入。
結果ログ例: `summary_applied=True` / `augment_sections=...` に `<SUMMARY>` が含まれる (今後拡張予定)。

## レート制限とスパム防止
非メンション応答を許可 (`RESPOND_WITHOUT_MENTION=1`) している場合のみ、ユーザー毎スライディングウィンドウでドロップ: `RATE_LIMIT_WINDOW_SEC` / `RATE_LIMIT_MAX_EVENTS`。

## 環境変数
| 必須 | 変数 | 説明 | 例 | 既定 |
| ---- | ---- | ---- | ---- | ---- |
| ✅ | `DISCORD_BOT_TOKEN` | Discord Bot Token | (secret) | なし |
| ✅ | `DISCORD_CLIENT_ID` | Bot アプリ Client ID | 1234567890 | なし |
| ✅ | `OPENAI_API_KEY` | OpenAI API Key | sk-xxxx | なし |
| ✅ | `ALLOWED_SERVER_IDS` | 許可サーバIDカンマ区切り | 123,456 | なし |
| ✅ | `PERMISSIONS` | Bot 招待権限ビット | 17179937792 | なし |
|  | `OPENAI_PROMPT_TOKEN_COST` | 1K prompt tokens USD | 0.0095 | 0.0 |
|  | `OPENAI_COMPLETION_TOKEN_COST` | 1K completion tokens USD | 0.030 | 0.0 |
|  | `HISTORY_MAX_ITEMS` | 1チャンネル履歴件数 | 30 | 30 |
|  | `RESPOND_WITHOUT_MENTION` | メンション不要応答 | 1 | 1 |
|  | `RATE_LIMIT_WINDOW_SEC` | レート窓秒 | 30 | 30 |
|  | `RATE_LIMIT_MAX_EVENTS` | 窓内最大メッセージ | 5 | 5 |
|  | `SEARCH_AGGRESSIVE_MODE` | 検索閾値緩和 | 1 | 0 |
|  | `WEBSEARCH_CACHE_TTL` | 検索キャッシュ秒 | 300 | 180 |
|  | `WEBSEARCH_CACHE_MAX` | キャッシュ件数 | 256 | 128 |
|  | `SUMMARY_TRIGGER_PROMPT_TOKENS` | 要約発火トークン概算 | 2800 | 2800 |
|  | `SUMMARY_TARGET_REDUCTION_RATIO` | 要約後比率 | 0.5 | 0.5 |
|  | `SUMMARY_MAX_SOURCE_CHARS` | 要約入力最大文字 | 8000 | 8000 |
|  | `SUMMARY_MODEL` | 要約専用モデル | gpt-4o-mini | メインモデル |
|  | `DISCLAIMER_ENABLE_ENGLISH` | 英語免責除去 | 1 | 1 |
|  | `DISCLAIMER_EXTRA_PATTERNS` | 追加除去正規表現 | foo|bar | なし |

`.env.example` を基に環境を整備してください。

## ログと計測
1イベント=1行、`key=value` スペース区切り。
```
event=<名称> uptime_s=<起動秒> key1=value1 key2="空白含む値" ...
```
主要例:
```
event=on_message author_id=123 channel_id=456 preview="hello"
event=search_decision type=query score=3 reasons=pattern:.+?調べて query="GPU 市場 現在 2025 最新"
event=openai_call attempt=1 purpose=completion invoke_ms=842.1 prompt_tokens=142 completion_tokens=256 total_tokens=398 model=gpt-4.1
event=openai_call_failed purpose=completion attempt=3 retriable=True error="rate limit"
event=websearch_connectivity status=OK error=-
event=openai_metrics decision=QUERY decision_score=3 search_status=NO_RESULTS search_executed=False
```
集計例:
```bash
grep 'event=openai_call ' bot.log | awk '{for(i=1;i<=NF;i++){if($i~"invoke_ms="){sub("invoke_ms=","",$i);print $i}}}' | awk '{sum+=$1; n++} END{print "avg_invoke_ms="sum/n}'
```
JSON が必要なら `infra/logging.py` を差し替えてください。

## 開発 Tips
ローカル実行 (直接):
```bash
pip install -r app/requirements.txt
python app/src/main.py
```
型/静的解析は必要に応じて mypy / ruff 等を導入推奨。

## トラブルシューティング
| 症状 | 原因 | 対処 |
| ---- | ---- | ---- |
| Bot が返信しない | ALLOWED_SERVER_IDS 未設定 | `.env` を再確認 |
| 検索が常に NO_RESULTS | ネットワーク遮断 / 取得0件正常 | `websearch_connectivity` ログ確認 |
| トークンコスト 0 のまま | `OPENAI_*_TOKEN_COST` 未設定 | 課金単価を設定 |
| 旧 import が警告 | 後方互換シム | 新パスへ移行 |
| 要約が走らない | トークン閾値未達 | `SUMMARY_TRIGGER_PROMPT_TOKENS` を下げる |

## 参考 / クレジット
 - [gpt-discord-bot](https://github.com/openai/gpt-discord-bot)
 - OpenAI / Discord / DuckDuckGo / BeautifulSoup などの各ライブラリ作者に感謝。

---
以下は英語 README との同期対象（必要に応じて英語版更新）。

## セキュリティ注意
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

### 積極検索モード (Aggressive Mode)
`SEARCH_AGGRESSIVE_MODE=1`:
* 最低スコア閾値を 2 → 1
* 末尾 `?` / `？` / 語彙 `教えて|とは|まとめて|一覧` 含有でスコア0 → 1 に昇格
* `reasons=aggressive_form` が付与される場合あり
検索頻度 ↑ = レイテンシ / トークン増を許容できる探索向けサーバで有効化推奨。

