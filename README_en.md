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
Follow these steps to create and set up your .env file:

1. Copy `.env.example` to `.env`:
    ```bash
    cp .env.example .env
    ```
2. Open `.env` and fill in the required values:
    - `OPENAI_API_KEY`: Your OpenAI API key
    - `DISCORD_BOT_TOKEN`: Your Discord Bot token
    - `DISCORD_CLIENT_ID`: Your Discord application client ID
    - `ALLOWED_SERVER_IDS`: Comma-separated list of server IDs where the bot is allowed
3. Set other items as needed.
```
1. Copy `.env.example` to `.env` and start filling in the values as detailed below
2. Go to https://beta.openai.com/account/api-keys, create a new API key, and fill in `OPENAI_API_KEY`
3. Create your own Discord application at https://discord.com/developers/applications
4. Go to the Bot tab and click "Add Bot"
    - Click "Reset Token" and fill in `DISCORD_BOT_TOKEN`
    - Disable "Public Bot" unless you want your bot to be visible to everyone
    - Enable "Message Content Intent" under "Privileged Gateway Intents"
5. Go to the OAuth2 tab, copy your "Client ID", and fill in `DISCORD_CLIENT_ID`
6. Copy the ID the server you want to allow your bot to be used in by right clicking the server icon and clicking "Copy ID". Fill in `ALLOWED_SERVER_IDS`. If you want to allow multiple servers, separate the IDs by "," like `server_id_1,server_id_2`
```

#### Model and System Prompt Settings
You can configure the AI model and system prompt in `app/src/sub/config.yaml`.

---

### Startup

#### Start with Docker Compose

```bash
cd path/to/DiscordBotWithGPT
docker-compose up -d
```

- Make sure to set up `.env` before the first launch.
- To stop the service, use `docker-compose down`.

---

### Discord command

Start chat in a thread:
```
/thread "any message"
```

Start chat in the current channel:
```
/message "any message"
```

Search the web for current information:
```
/websearch "search query"
```

You can also send a message with @BotName "any Message".
(*Replace "@BotName" with your actual bot name.)

---

### Reference
 - [gpt-discord-bot](https://github.com/openai/gpt-discord-bot)
