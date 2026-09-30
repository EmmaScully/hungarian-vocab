# Hungarian Vocab Trainer

A weekly English → Hungarian vocabulary loop:

1. **Monday 06:00 UTC** — GitHub Actions generates a new word list, with an LLM (Gemini by default, Claude optional) filling up to
   half of it from words you failed or marked "needs practice". It builds an mp3 of each
   word (English, 2s pause, slow Hungarian, 2s pause) and publishes it as a GitHub Release, then emails
   you the list (Telegram is optional).
2. **During the week** — revise with flashcards on the GitHub Pages site, or listen to the
   audio (direct link, Telegram, or subscribe to the podcast feed).
3. **Any time in the week** — do the **reading & writing** exercise in the password-protected
   Writing tab. Submitting it has Gemini mark it; the feedback is emailed to you and appears
   in the tab.
4. **Before next Monday** — switch the site to **Test** mode. Your first answer for each card is
   committed to the repo and applied to the word bank:
   - **Mastered** words never come back.
   - **Fail** and **needs practice** words come back in the next list.

## Layout

| Path | What |
|---|---|
| `src/vocab/` | Python pipeline (`uv run vocab --help`) |
| `src/vocab/llm/` | LLM providers (Gemini, Claude; add others by implementing `LLMProvider`) |
| `src/vocab/audio/` | TTS providers (`edge` free/no key, `azure` free tier) and mp3 composition |
| `src/vocab/publish/` | GitHub Release upload, podcast RSS |
| `src/vocab/notify/` | Email (SMTP) and Telegram |
| `site/` | Static flashcard app and progress dashboard (no build step) |
| `data/bank.json` | Word bank: status, ease, lapses and history of every word |
| `data/lists/` | Weekly lists + `index.json` |
| `data/results/` | Test results written by the site |
| `data/writing/` | Reading & writing exercises, submissions and feedback — **encrypted** |
| `config.toml` | Word count, review ratio, topics, model, voices, pauses |

## Setup

Repo: <https://github.com/EmmaScully/hungarian-vocab>. Site: <https://www.emmascully.info/hungarian-vocab/>.
The site URL is normally `https://<username-in-lowercase>.github.io/<repo-name>/`. This account has
a custom domain, so `emmascully.github.io` redirects to `www.emmascully.info`. The live URL is
always shown under Settings → Pages.

1. **Pages:** open Settings → Pages and set Source to "GitHub Actions".
2. **Secrets:** open Settings → Secrets and variables → Actions. The workflows expect these:

   | Secret | Used as |
   |---|---|
   | `GEMINI_API` | Gemini API key (free tier), for words, sentences, exercises and marking |
   | `WRITING_TAB` | Password for the Writing tab; also encrypts everything in it |
   | `EMAIL` | Gmail address: SMTP login and recipient |
   | `APP_PW` | [Gmail app password](https://myaccount.google.com/apppasswords) |
   | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Optional, later. Also set `notify.telegram = true` in `config.toml` |
   | `ANTHROPIC_API_KEY` | Optional, only if `llm.provider = "claude"` |
   | `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` | Optional, only if `audio.provider = "azure"` |

3. **Site token:** in the site's **Settings** tab, add a
   [fine-grained token](https://github.com/settings/personal-access-tokens/new) scoped to this repo
   only, with **Contents: read and write**. It lives only in your browser's local storage.
4. **First run:** go to Actions → "Weekly word list" → Run workflow.

## Local use

```sh
uv sync
set -a; source .env; set +a          # see .env.example (GEMINI_API_KEY etc.)
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
- `vocab sentences`, `vocab writing`: add test sentences or the reading & writing exercise to a week.
- `vocab grade-writing`, `vocab email-feedback`: mark a submission, or re-send its feedback.

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
the LLM. Every word already in the bank is excluded, so mastered words never come back.

**If you skip a test,** that week's words stay "untested" and are carried into the next list.

## Test sentences

Each list also gets 10 short sentences built from its words. They appear only in **Test**
mode, mixed in with the words, and every card is shown in a random direction (English →
Magyar or Magyar → English). Sentence ratings show on the dashboard, but they never change
the word bank.

## Reading & writing (private)

Every Monday a B1–B2 passage is generated, with themes taken from your word lists or a
general-interest topic. It comes with 4 short and 2 longer comprehension questions, plus a
short and a long writing task.

**Privacy.** The repo and site are public, so this tab's content is protected by encryption,
not by hiding it:
- The exercise, your answers and the feedback are committed only as AES-256-GCM ciphertext.
- The key is derived from the `WRITING_TAB` password with PBKDF2-SHA256 (600k iterations).
- The browser decrypts after you enter the password, and the password never leaves the browser.
- Anyone can download the ciphertext, so its safety depends on the password. Use a long,
  unique one: four or more random words is good.

**Submitting.** Answers are encrypted in the browser and committed. That triggers
`grade-writing.yml`, which decrypts the submission, asks Gemini to mark it (with feedback in
English), saves the feedback encrypted, redeploys the site and emails the feedback to you.
In the tab, **Save as PDF** prints the feedback to a PDF.

**Maintenance workflow** (Actions → Maintenance). Tasks for an existing week:
- Add sentences and/or the reading & writing exercise.
- Rebuild the audio.
- Re-grade a submission.
- Re-send the feedback email.

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
