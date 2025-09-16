<!-- PROJECT HEADER -->

# DiscordBotWithGPT

[![GitHub commit activity](https://img.shields.io/github/commit-activity/m/koiusa/DiscordBotWithGPT)](https://github.com/koiusa/DiscordBotWithGPT/graphs/commit-activity)
[![GitHub issues](https://img.shields.io/github/issues/koiusa/DiscordBotWithGPT)](https://github.com/koiusa/DiscordBotWithGPT/issues)
[![GitHub license](https://img.shields.io/github/license/koiusa/DiscordBotWithGPT)](https://github.com/koiusa/DiscordBotWithGPT/blob/main/LICENSE)

Discord bot featuring multi-user contextual conversation, web search (DuckDuckGo + Google fallback), structured logging, automatic summarization, rate limiting, and resilient OpenAI wrapper.

---

## Table of Contents
1. [Features](#features)
2. [Setup](#setup)
3. [Environment Variables](#environment-variables)
4. [Architecture - Search Flow](#architecture---search-flow)
5. [Directory Layout](#directory-layout)
6. [Run (Docker)](#run-docker)
7. [Slash Commands](#slash-commands)
8. [Conversation History & Identity](#conversation-history--identity)
9. [Summarization](#summarization)
10. [Rate Limiting](#rate-limiting)
11. [Logging & Metrics](#logging--metrics)
12. [Development Tips](#development-tips)
13. [Troubleshooting](#troubleshooting)
14. [Reference](#reference)

---

## Features
| Area | Feature | Notes |
| ---- | ------- | ----- |
| Conversation | Multi-user speaker tagging | `username(userId): content` format to LLM |
| Conversation | Ring buffer history | `HISTORY_MAX_ITEMS` configurable |
| Summarization | Auto prompt compression | Triggered above threshold |
| Search | Need scoring + aggressive mode | Regex + question words + temporal tokens |
| Search | DuckDuckGo + Google fallback | Explicit `NO_RESULTS` fallback text |
| Search | LRU + TTL cache | `WEBSEARCH_CACHE_*` |
| Search | Status logging | OK / NO_RESULTS / ERROR / SKIPPED |
| Output | Section augmentation | Conversation / Search / Guideline |
| Reliability | OpenAI retry wrapper | Backoff + metrics + cost estimation |
| Rate limit | Per-user sliding window | For passive responses |
| Ops | Structured logs | 1 line = 1 event `key=value` |
| Ops | Heartbeat & diag | `/diag` latency + quick search |

---

## Setup
### Create Discord Bot
* https://discord.com/developers/applications

### Get OpenAI API Key
* https://platform.openai.com

### Create `.env`
1. Copy template:
```bash
cp .env.example .env
```
2. Fill required values:
     * `OPENAI_API_KEY`
     * `DISCORD_BOT_TOKEN`
     * `DISCORD_CLIENT_ID`
     * `ALLOWED_SERVER_IDS`
     * `PERMISSIONS`
3. Adjust optional parameters as needed.

### Model / System Prompt
Configure in `app/src/sub/config.yaml`.

## Run (Docker)
```bash
docker-compose up -d
```
Stop:
```bash
docker-compose down
```

## Slash Commands
Thread conversation:
```
/thread "message"
```
Channel conversation:
```
/message "message"
```
Web search:
```
/websearch "query"
```
Diagnostic:
```
/diag
```
Or mention: `@BotName your message` (replace with actual bot name).

## Conversation History & Identity
* Channel‑scoped cyclic buffer (`HISTORY_MAX_ITEMS`).
* Tagged speaker lines avoid identity confusion.

## Summarization
Triggered when heuristic token count > `SUMMARY_TRIGGER_PROMPT_TOKENS`, reduces to ratio `SUMMARY_TARGET_REDUCTION_RATIO`.

## Rate Limiting
If `RESPOND_WITHOUT_MENTION=1`, passive channel messages are rate limited per user with `RATE_LIMIT_WINDOW_SEC` / `RATE_LIMIT_MAX_EVENTS`.

## Environment Variables
| Req | Name | Description | Default |
| --- | ---- | ----------- | ------- |
| ✅ | DISCORD_BOT_TOKEN | Discord bot token | - |
| ✅ | DISCORD_CLIENT_ID | Application client id | - |
| ✅ | OPENAI_API_KEY | OpenAI API key | - |
| ✅ | ALLOWED_SERVER_IDS | Comma separated guild ids | - |
| ✅ | PERMISSIONS | Invite permissions bitset | - |
|   | OPENAI_PROMPT_TOKEN_COST | USD per 1K prompt tokens | 0.0 |
|   | OPENAI_COMPLETION_TOKEN_COST | USD per 1K completion tokens | 0.0 |
|   | HISTORY_MAX_ITEMS | Max history items per channel | 30 |
|   | RESPOND_WITHOUT_MENTION | Passive reply enable | 1 |
|   | RATE_LIMIT_WINDOW_SEC | Rate limit window seconds | 30 |
|   | RATE_LIMIT_MAX_EVENTS | Max events per window | 5 |
|   | SEARCH_AGGRESSIVE_MODE | Loosen search trigger | 0 |
|   | WEBSEARCH_CACHE_TTL | Search cache TTL seconds | 180 |
|   | WEBSEARCH_CACHE_MAX | Cache max entries | 128 |
|   | SUMMARY_TRIGGER_PROMPT_TOKENS | Summarization threshold | 2800 |
|   | SUMMARY_TARGET_REDUCTION_RATIO | Post-summary ratio | 0.5 |
|   | SUMMARY_MAX_SOURCE_CHARS | Max source chars | 8000 |
|   | SUMMARY_MODEL | Dedicated summary model | (main) |
|   | DISCLAIMER_ENABLE_ENGLISH | Remove English disclaimers | 1 |
|   | DISCLAIMER_EXTRA_PATTERNS | Extra regex removal | (empty) |

## Architecture - Search Flow
```
user msg -> search_decision.should_perform_web_search()
    -> DATETIME_ANSWER | QUERY | NONE
    -> (QUERY) perform_web_search -> status (OK/NO_RESULTS/ERROR)
    -> build <SEARCH_CONTEXT> (fallback for NO_RESULTS)
    -> augment -> OpenAI -> reply
```
Statuses (all `search_executed=False` by design; context injected only):
| status | Meaning |
| ------ | ------- |
| OK | >=1 result summarized & injected |
| NO_RESULTS | Search attempted, zero hits, fallback text |
| SKIPPED | Not triggered |
| ERROR | Exception -> error context |

## Directory Layout
```
app/src/sub/
    core/       # Domain models
    infra/      # Logging infra
    discord/    # Discord helpers
    llm/        # OpenAI calls & completion
    search/     # Decision / execution / cache
    history_store.py
    format_conversation.py
```

## Logging & Metrics
Single-line structured events:
```
event=search_decision type=query score=3 reasons=pattern:.+?調べて query="GPU 市場 現在 2025 最新"
event=openai_call attempt=1 purpose=completion invoke_ms=842.1 prompt_tokens=142 completion_tokens=256 total_tokens=398 model=gpt-4.1
event=openai_metrics decision=QUERY decision_score=3 search_status=NO_RESULTS search_executed=False
```

## Development Tips
```bash
pip install -r app/requirements.txt
python app/src/main.py
```

## Troubleshooting
| Symptom | Cause | Fix |
| ------- | ----- | --- |
| No reply | Guild not allowed | Check ALLOWED_SERVER_IDS |
| Always NO_RESULTS | Network or valid zero | See websearch_connectivity log |
| Cost always 0 | Cost envs unset | Set OPENAI_*_TOKEN_COST |
| Deprecation warnings | Old import paths | Migrate to new paths |
| No summarization | Threshold not reached | Lower SUMMARY_TRIGGER_PROMPT_TOKENS |

## Reference
* [gpt-discord-bot](https://github.com/openai/gpt-discord-bot)

---
_English README simplified. For detailed Japanese documentation see `README.md`._
