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

また、＠BotName "any Message" でもメッセージを送信できます。
（※「＠BotName」はBot名なので、実際のBot名に置き換えてください）

---

### Reference
 - [gpt-discord-bot](https://github.com/openai/gpt-discord-bot)
