"""Command-line entry point: `uv run vocab <command>`."""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

from vocab import bank as bank_ops
from vocab.config import Config, load_config
from vocab.generator import build_list, iso_week_id
from vocab.models import ListIndexEntry
from vocab.store import Store


def _topics(raw: str | None, config: Config) -> list[str]:
    if raw is None:
        return config.generator.topics
    return [t.strip() for t in raw.split(",") if t.strip()]


def _resolve_list_id(store: Store, list_id: str | None) -> str:
    list_id = list_id or store.latest_list_id()
    if list_id is None:
        sys.exit("No word lists yet — run `vocab generate` first.")
    return list_id


def _audio_path(config: Config, list_id: str) -> Path:
    return config.general.build_dir / "audio" / f"hungarian-vocab-{list_id}.mp3"


def cmd_generate(args, config: Config, store: Store) -> None:
    from vocab.llm.base import get_provider

    bank = store.load_bank()
    index = store.load_index()
    now = datetime.now(UTC)
    n = args.n or config.generator.n_words
    topics = _topics(args.topics, config)

    list_id = iso_week_id(now.date())
    if store.list_path(list_id).exists():
        if not args.force:
            sys.exit(f"List {list_id} already exists — pass --force to regenerate it.")
        if list_id in bank.applied_results:
            sys.exit(f"List {list_id} has already been tested; refusing to regenerate it.")
        # Forget words that were introduced by the list being replaced.
        for card in store.load_list(list_id).cards:
            entry = bank.words.get(card.id)
            if card.source == "new" and entry is not None and entry.status == "new":
                del bank.words[card.id]
        index.lists = [e for e in index.lists if e.id != list_id]

    word_list = build_list(
        bank,
        get_provider(config.llm),
        n=n,
        topics=topics,
        review_ratio=config.generator.review_ratio,
        level=config.generator.level,
        now=now,
    )
    store.save_list(word_list)
    store.save_bank(bank)
    index.lists.append(
        ListIndexEntry(
            id=word_list.id,
            created=word_list.created,
            topics=word_list.topics,
            n_cards=len(word_list.cards),
        )
    )
    store.save_index(index)

    n_review = sum(c.source == "review" for c in word_list.cards)
    print(f"Created {word_list.id}: {len(word_list.cards)} cards ({n_review} review)")
    for card in word_list.cards:
        tag = " (review)" if card.source == "review" else ""
        print(f"  {card.front_en} — {card.back_hu}{tag}")


def cmd_audio(args, config: Config, store: Store) -> None:
    from vocab.audio.base import get_tts
    from vocab.audio.compose import build_audio, duration_seconds

    list_id = _resolve_list_id(store, args.list_id)
    word_list = store.load_list(list_id)
    out = build_audio(word_list, get_tts(config.audio), config.audio, _audio_path(config, list_id))

    index = store.load_index()
    entry = index.get(list_id)
    if entry is not None:
        entry.audio_bytes = out.stat().st_size
        entry.audio_duration_s = round(duration_seconds(out), 1)
        store.save_index(index)
    print(f"Wrote {out}")


def cmd_release(args, config: Config, store: Store) -> None:
    from vocab.publish.release import GitHubReleases

    list_id = _resolve_list_id(store, args.list_id)
    audio = _audio_path(config, list_id)
    if not audio.exists():
        sys.exit(f"{audio} not found — run `vocab audio` first.")

    word_list = store.load_list(list_id)
    body = "\n".join(f"- {c.front_en} — **{c.back_hu}**" for c in word_list.cards)
    url = GitHubReleases.from_env().upload(
        tag=f"week-{list_id}", name=f"Hungarian vocab {list_id}", body=body, file=audio
    )
    word_list.audio_url = url
    store.save_list(word_list)
    index = store.load_index()
    if (entry := index.get(list_id)) is not None:
        entry.audio_url = url
        store.save_index(index)
    print(f"Uploaded {url}")


def cmd_feed(args, config: Config, store: Store) -> None:
    from vocab.publish.feed import build_feed

    path = store.root / "feed.xml"
    path.write_text(build_feed(store.load_index(), config.general.site_url), encoding="utf-8")
    print(f"Wrote {path}")


def cmd_notify(args, config: Config, store: Store) -> None:
    list_id = _resolve_list_id(store, args.list_id)
    word_list = store.load_list(list_id)
    site_url = config.general.site_url

    if config.notify.email and not args.no_email:
        from vocab.notify.email import send_email

        entry = store.load_index().get(list_id)
        send_email(word_list, site_url, has_writing=bool(entry and entry.has_writing))
        print("Email sent")

    if config.notify.telegram and not args.no_telegram:
        from vocab.notify.telegram import send_telegram

        audio = _audio_path(config, list_id)
        if not audio.exists() and word_list.audio_url:
            audio.parent.mkdir(parents=True, exist_ok=True)
            r = httpx.get(word_list.audio_url, follow_redirects=True, timeout=120)
            r.raise_for_status()
            audio.write_bytes(r.content)
        send_telegram(word_list, site_url, audio if audio.exists() else None)
        print("Telegram sent")


def cmd_apply_results(args, config: Config, store: Store) -> None:
    bank = store.load_bank()
    index = store.load_index()
    applied = bank_ops.apply_pending_results(
        bank, index, store.load_results(), store.load_list, datetime.now(UTC).date()
    )
    if not applied:
        print("No new test results.")
        return
    store.save_bank(bank)
    store.save_index(index)
    print(f"Applied test results for: {', '.join(applied)}")


def cmd_sentences(args, config: Config, store: Store) -> None:
    from vocab.llm.base import get_provider
    from vocab.sentences import generate_sentences

    list_id = _resolve_list_id(store, args.list_id)
    word_list = store.load_list(list_id)
    word_list.sentences = generate_sentences(
        get_provider(config.llm), word_list, config.sentences.n
    )
    store.save_list(word_list)
    print(f"Added {len(word_list.sentences)} test sentences to {list_id}")
    for card in word_list.sentences:
        print(f"  {card.front_en} — {card.back_hu}")


def _writing_store(config: Config, store: Store):
    from vocab import crypto
    from vocab.writing import WritingStore

    password = crypto.password_from_env()
    if password is None:
        sys.exit(f"{crypto.PASSWORD_ENV} is not set (the WRITING_TAB secret).")
    return WritingStore(store.root, password)


def cmd_writing(args, config: Config, store: Store) -> None:
    from vocab.llm.base import get_provider
    from vocab.writing import generate_exercise

    wstore = _writing_store(config, store)
    list_id = _resolve_list_id(store, args.list_id)
    index = store.load_index()
    exercise = generate_exercise(
        get_provider(config.llm),
        week_id=list_id,
        current=store.load_list(list_id),
        index=index,
        recent_themes=wstore.recent_themes(),
        level=config.writing.level,
        n_short=config.writing.short_questions,
        n_long=config.writing.long_questions,
    )
    wstore.save_exercise(exercise)
    if (entry := index.get(list_id)) is not None:
        entry.has_writing = True
        entry.writing_submitted = False
        entry.writing_graded = False
        store.save_index(index)
    # Only the title is printed: the exercise itself stays private.
    print(f"Created encrypted reading & writing exercise for {list_id}: {exercise.title_en}")


def cmd_grade_writing(args, config: Config, store: Store) -> None:
    from vocab.llm.base import get_provider
    from vocab.writing import grade

    wstore = _writing_store(config, store)
    weeks = [args.list_id] if args.list_id else wstore.ungraded_weeks()
    if not weeks:
        print("No ungraded writing submissions.")
        return
    llm = get_provider(config.llm)
    index = store.load_index()
    email_errors = []
    for week in weeks:
        exercise, submission = wstore.load_exercise(week), wstore.load_submission(week)
        feedback = grade(llm, exercise, submission)
        wstore.save_feedback(feedback)
        if (entry := index.get(week)) is not None:
            entry.writing_submitted = entry.writing_graded = True
        store.save_index(index)
        print(f"Graded writing for {week}")
        if config.notify.email and not args.no_email:
            try:
                _email_feedback(wstore, week)
            except Exception as e:  # keep the saved feedback even if email fails
                email_errors.append(f"{week}: {e}")
    if email_errors:
        sys.exit("Feedback saved, but emailing failed:\n" + "\n".join(email_errors))


def _email_feedback(wstore, week: str) -> None:
    from vocab.notify.email import send_html_email
    from vocab.writing import feedback_email_html

    exercise, submission = wstore.load_exercise(week), wstore.load_submission(week)
    feedback = wstore.load_feedback(week)
    send_html_email(
        f"📝 Hungarian reading & writing feedback — {week}",
        feedback_email_html(exercise, submission, feedback),
        f"Reading {feedback.reading_score_pct}% · Writing {feedback.writing_score_pct}%\n\n"
        f"{feedback.summary}\n\nFull feedback is in the Writing tab of the site.",
    )
    print(f"Emailed feedback for {week}")


def cmd_email_feedback(args, config: Config, store: Store) -> None:
    wstore = _writing_store(config, store)
    _email_feedback(wstore, _resolve_list_id(store, args.list_id))


def _optional_step(name: str, func, args, config: Config, store: Store) -> None:
    """Run a non-essential weekly step; a failure is reported but doesn't stop the words/audio."""
    try:
        func(args, config, store)
    except (Exception, SystemExit) as e:
        print(f"::warning::{name} failed: {e}")


def cmd_weekly(args, config: Config, store: Store) -> None:
    """Monday pipeline minus notifications (those run after the Pages deploy in CI)."""
    cmd_apply_results(args, config, store)
    cmd_generate(args, config, store)
    _optional_step("Test sentences", cmd_sentences, args, config, store)
    _optional_step("Reading & writing exercise", cmd_writing, args, config, store)
    cmd_audio(args, config, store)
    if args.skip_release:
        print("Skipping GitHub release (--skip-release)")
    else:
        cmd_release(args, config, store)
    cmd_feed(args, config, store)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vocab", description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, func, help: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help)
        p.set_defaults(func=func)
        return p

    def generate_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--n", type=int, help="number of words (default: config)")
        p.add_argument("--topics", help="comma-separated topics; empty string = none")
        p.add_argument("--force", action="store_true", help="replace this week's list")

    generate_args(add("generate", cmd_generate, "generate this week's word list"))
    for name, func, help in [
        ("audio", cmd_audio, "build the practice mp3"),
        ("release", cmd_release, "upload the mp3 to a GitHub release"),
        ("notify", cmd_notify, "send email/Telegram notifications"),
        ("sentences", cmd_sentences, "(re)generate the test sentences for a list"),
        ("writing", cmd_writing, "(re)generate the encrypted reading & writing exercise"),
        ("grade-writing", cmd_grade_writing, "grade submitted writing and email feedback"),
        ("email-feedback", cmd_email_feedback, "re-send a week's writing feedback email"),
    ]:
        p = add(name, func, help)
        p.add_argument("--list-id", help="e.g. 2026-W40 (default: latest)")
        if name in ("notify", "grade-writing"):
            p.add_argument("--no-email", action="store_true")
        if name == "notify":
            p.add_argument("--no-telegram", action="store_true")
    add("feed", cmd_feed, "rebuild the podcast RSS feed")
    add("apply-results", cmd_apply_results, "apply submitted test results to the word bank")
    weekly = add(
        "weekly", cmd_weekly, "apply results, generate words/sentences/writing, audio, feed"
    )
    generate_args(weekly)
    weekly.add_argument("--list-id", default=None, help=argparse.SUPPRESS)
    weekly.add_argument("--skip-release", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)
    store = Store(config.general.data_dir)
    args.func(args, config, store)


if __name__ == "__main__":
    main()
