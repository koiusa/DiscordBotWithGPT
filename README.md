# DiscordBotWithGPT


[![GitHub commit activity](https://img.shields.io/github/commit-activity/m/koiusa/DiscordBotWithGPT)](https://github.com/koiusa/DiscordBotWithGPT/graphs/commit-activity)
[![GitHub issues](https://img.shields.io/github/issues/koiusa/DiscordBotWithGPT)](https://github.com/koiusa/DiscordBotWithGPT/issues)
[![GitHub license](https://img.shields.io/github/license/koiusa/DiscordBotWithGPT)](https://github.com/koiusa/DiscordBotWithGPT/blob/main/LICENSE)

### Testing Env
```
Python 3.10.10
```

```
gpt-3.5-turbo
```

---

### Setup

#### Create Discord Bot
 - [discord_developers](https://discord.com/developers/applications)
 
#### Getting OpenApi ApiKey
 - [openai_platform](https://platform.openai.com)

#### Setting Env File
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

---

### Startup

##### Environment
```
cd path/to/DiscordBotWithGPT
```

```
python3 -m venv .
```

```
source bin/activate
```

```
pip install -r requirements.txt
```

#### execution
```
python3 -m src.main
```

---

### Discord command

Create Thread Chat Start
```
/thread "any message"
```

Current Channel Chat Start
```
/message "any message"
```

---

### Reference
 - [gpt-discord-bot](https://github.com/openai/gpt-discord-bot)
