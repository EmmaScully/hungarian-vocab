# Hungarian Vocab Trainer

A weekly English → Hungarian vocabulary loop:

1. **Monday 06:00 UTC** — GitHub Actions generates a new word list, with Claude filling up to
   half of it from words you failed or marked "needs practice". It builds an mp3 of each
   word (English, pause, Hungarian, pause) and publishes it as a GitHub Release, then emails
   you the list and sends it plus the audio to Telegram.
2. **During the week** — revise with flashcards on the GitHub Pages site, or listen to the
   audio (direct link, Telegram, or subscribe to the podcast feed).
3. **Before next Monday** — switch the site to **Test** mode. Your first answer for each card is
   committed to the repo and applied to the word bank:
   - **Mastered** words never come back.
   - **Fail** and **needs practice** words come back in the next list.

## Layout

| Path | What |
|---|---|
| `src/vocab/` | Python pipeline (`uv run vocab --help`) |
| `src/vocab/llm/` | LLM providers (Claude; add others by implementing `LLMProvider`) |
| `src/vocab/audio/` | TTS providers (`edge` free/no key, `azure` free tier) and mp3 composition |
| `src/vocab/publish/` | GitHub Release upload, podcast RSS |
| `src/vocab/notify/` | Email (SMTP) and Telegram |
| `site/` | Static flashcard app and progress dashboard (no build step) |
| `data/bank.json` | Word bank: status, ease, lapses and history of every word |
| `data/lists/` | Weekly lists + `index.json` |
| `data/results/` | Test results written by the site |
| `config.toml` | Word count, review ratio, topics, model, voices, pauses |

## Setup

1. **Create the GitHub repo.** It must be public for free GitHub Pages. Then push:
   ```sh
   git remote add origin git@github.com:<you>/hungarian-vocab.git
   git push -u origin main
   ```
2. **Pages:** open Settings → Pages and set Source to "GitHub Actions".
3. **Secrets:** open Settings → Secrets and variables → Actions, and add:
   - `ANTHROPIC_API_KEY`
   - `SMTP_USER`, `SMTP_APP_PASSWORD` (a [Gmail app password](https://myaccount.google.com/apppasswords)), `EMAIL_TO`
   - `TELEGRAM_BOT_TOKEN` (from @BotFather). To get `TELEGRAM_CHAT_ID`, message your bot, then open
     `https://api.telegram.org/bot<TOKEN>/getUpdates`.
   - Optional: `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` if you switch `audio.provider` to `azure`.
4. **`config.toml`:** set `site_url` to `https://<you>.github.io/hungarian-vocab/`.
5. **Site token:** in the site's **Settings** tab, add a
   [fine-grained token](https://github.com/settings/personal-access-tokens/new) scoped to this repo
   only, with **Contents: read and write**. It lives only in your browser's local storage.
6. **First run:** go to Actions → "Weekly word list" → Run workflow. This is the full dry run.

## Local use

```sh
uv sync
set -a; source .env; set +a          # see .env.example
uv run vocab generate --n 20 --topics "food,travel"
uv run vocab audio                   # needs ffmpeg (sudo apt install ffmpeg)
uv run vocab feed
python -m http.server                # then open http://localhost:8000/site/
uv run pytest
```

Other commands:
- `vocab apply-results`: fold `data/results/*` into the bank.
- `vocab release`: upload the mp3.
- `vocab notify`: send the email and Telegram message.
- `vocab weekly`: everything except notify.

## How it works

**Session order (site).** This is an Anki-style learning queue:
- **Fail:** the card comes back after about 3 cards.
- **Needs practice:** the card comes back after about 8 cards.
- **Mastered:** the card leaves the session.

**Score.** Each card's first answer counts 1 for mastered, 0.5 for needs practice and 0 for fail.
The score is the average of these, as a percentage.

**Revise vs test.**
- Revise mode only saves progress in your browser.
- Test mode submits `data/results/<week>-test.json`. That triggers `apply-results.yml`, which
  updates `bank.json` using a simplified SM-2 (ease, interval, lapses) and redeploys the site.

**Next list.** Review words are picked in this order:
1. Failed words.
2. Needs-practice words.
3. Words that were shown but never tested.

Within each group, words with more lapses come first. The rest of the list is new words from
Claude. Every word already in the bank is excluded, so mastered words never come back.

**If you skip a test,** that week's words stay "untested" and are carried into the next list.

## Audio: TTS and delivery options

| TTS | Cost | Notes |
|---|---|---|
| **edge-tts** (default) | Free, no key | Microsoft neural voices (`hu-HU-NoemiNeural`, `hu-HU-TamasNeural`). Uses an unofficial endpoint. |
| Azure AI Speech | Free F0: 500k chars/month | Same voices through the official API; set `audio.provider = "azure"`. |
| Google Cloud TTS | Free: 1M+ chars/month | hu-HU WaveNet voices; needs a GCP billing account. |
| Gemini TTS | Free tier | Expressive voices; tighter rate limits. |
| ElevenLabs | Free: 10k chars/month | Best quality; free quota covers only a week or two. |

Each week's mp3 is delivered three ways:
- **GitHub Release asset.** A stable link, used in the email.
- **Telegram audio message.** Plays or saves in one tap.
- **Podcast feed** at `<site_url>/data/feed.xml`. Subscribe in AntennaPod, Pocket Casts or Apple
  Podcasts, and new weeks download automatically.

## Roadmap: sentence practice

`Card.type` already supports `"sentence"`, and each card carries `word_ids`. `src/vocab/sentences.py`
holds the stub. The plan is to generate EN/HU sentences from words in the bank for the test phase.
A sentence rating would then update every word it contains.
