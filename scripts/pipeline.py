#!/usr/bin/env python3
"""drafts/pending の最古ファイルを推敲 → 投稿 → posted/ に移動。

- X_LIVE_POST=true のときだけ実投稿。false ならドライラン(推敲結果を logs に書くだけ)。
- 失敗したら drafts/failed/ に移動して理由ログを残す。
- ドラフトの1行目が `quote: <URL>` の場合は、そのツイートを引用RT扱いで投稿する。

Usage:
    python3 scripts/pipeline.py            # 通常
    python3 scripts/pipeline.py --dry-run  # 実投稿せず推敲のみ
    python3 scripts/pipeline.py --length 長文
"""
from __future__ import annotations

import datetime as dt
import json
import os
import random
import re
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "scripts"))

from polish_draft import generate_reply, polish  # noqa: E402
from post_tweet import post  # noqa: E402


def _reply_thread_rate() -> float:
    """自己リプ(コメ欄に続き)を付ける確率。0〜1。既定0.4。"""
    try:
        r = float(os.getenv("X_REPLY_THREAD_RATE", "0.4"))
    except ValueError:
        return 0.4
    return min(max(r, 0.0), 1.0)

HANDLE = os.getenv("X_HANDLE", "kante0123")
PENDING = ROOT / "drafts" / "pending"
POSTED = ROOT / "drafts" / "posted"
FAILED = ROOT / "drafts" / "failed"
LOGS = ROOT / "logs"

QUOTE_LINE_RE = re.compile(r"^\s*quote\s*:\s*(\S+)\s*$", re.IGNORECASE)
TWEET_ID_RE = re.compile(r"status/(\d+)")


def oldest_pending() -> Path | None:
    files = sorted(p for p in PENDING.iterdir() if p.is_file() and not p.name.startswith("."))
    return files[0] if files else None


def append_log(name: str, payload: dict) -> None:
    LOGS.mkdir(exist_ok=True)
    log_path = LOGS / "pipeline.log"
    payload = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(), "file": name, **payload}
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def parse_quote_header(raw: str) -> tuple[str | None, str]:
    """ドラフト先頭の `quote: <URL>` 行を抽出。なければ (None, raw) を返す。"""
    lines = raw.splitlines()
    if not lines:
        return None, raw
    m = QUOTE_LINE_RE.match(lines[0])
    if not m:
        return None, raw
    url = m.group(1)
    id_m = TWEET_ID_RE.search(url)
    if not id_m:
        raise ValueError(f"quote URLからtweet_idを抽出できません: {url}")
    body = "\n".join(lines[1:]).lstrip()
    return id_m.group(1), body


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    live = os.getenv("X_LIVE_POST", "false").lower() == "true" and not dry_run

    length = None
    if "--length" in sys.argv:
        i = sys.argv.index("--length")
        length = sys.argv[i + 1]

    draft_path = oldest_pending()
    if draft_path is None:
        append_log("(none)", {"event": "no_pending"})
        print("pending にドラフトはありません。drafts/pending/ に .md か .txt を置いてください。", file=sys.stderr)
        return 0

    raw = draft_path.read_text(encoding="utf-8")
    print(f"[draft] {draft_path.name}\n---\n{raw}\n---")

    try:
        quote_id, body = parse_quote_header(raw)
    except Exception as e:
        FAILED.mkdir(exist_ok=True)
        shutil.move(str(draft_path), str(FAILED / draft_path.name))
        append_log(draft_path.name, {"event": "parse_failed", "error": str(e)})
        print(f"[parse ERROR] {e}", file=sys.stderr)
        return 1

    if quote_id:
        print(f"[quote_rt] quote_tweet_id={quote_id}")

    # コメ欄に『続き』を自己リプで置くスレッド投稿にするか(引用RTとは併用しない)。
    thread = (quote_id is None) and (random.random() < _reply_thread_rate())

    try:
        polished = polish(body, length=length, comment_cta=thread)
    except Exception as e:
        FAILED.mkdir(exist_ok=True)
        shutil.move(str(draft_path), str(FAILED / draft_path.name))
        append_log(draft_path.name, {"event": "polish_failed", "error": str(e)})
        print(f"[polish ERROR] {e}", file=sys.stderr)
        return 1
    print(f"[polished] ({len(polished)}文字)\n---\n{polished}\n---")

    # スレッド投稿: コメ欄に置くリプ本文を“投稿前に”生成する。
    # 生成に失敗したら、本文だけが「コメ欄に続き」を約束する宙ぶらりんを避けるため
    # comment_cta なしで推敲し直し、単発投稿に落とす。
    reply_text: str | None = None
    if thread:
        try:
            reply_text = generate_reply(polished, body)
            print(f"[reply] ({len(reply_text)}文字)\n---\n{reply_text}\n---")
        except Exception as e:
            print(f"[reply gen failed → 単発に切替] {e}", file=sys.stderr)
            append_log(draft_path.name, {"event": "reply_gen_failed", "error": str(e)})
            thread = False
            reply_text = None
            try:
                polished = polish(body, length=length, comment_cta=False)
                print(f"[re-polished single] ({len(polished)}文字)\n---\n{polished}\n---")
            except Exception as e2:
                FAILED.mkdir(exist_ok=True)
                shutil.move(str(draft_path), str(FAILED / draft_path.name))
                append_log(draft_path.name, {"event": "polish_failed", "error": str(e2)})
                print(f"[polish ERROR] {e2}", file=sys.stderr)
                return 1

    if not live:
        append_log(
            draft_path.name,
            {
                "event": "dry_run",
                "polished": polished,
                "chars": len(polished),
                "quote_tweet_id": quote_id,
                "thread": thread,
                "reply_text": reply_text,
            },
        )
        print("[dry-run] 実投稿はしませんでした。X_LIVE_POST=true で本番投稿。")
        if thread:
            print("[dry-run] スレッド投稿(本ツイート→コメ欄リプ)になります。")
        return 0

    try:
        result = post(polished, quote_tweet_id=quote_id)
    except Exception as e:
        msg = str(e)
        m = re.search(r"status=(\d+)", msg)
        code = int(m.group(1)) if m else None
        # 402(クレジット枯渇)/429(レート制限)/5xx(一時的サーバ障害)は、ドラフトを
        # failed に捨てず pending に温存し、赤ランにもせず soft skip(exit 0)。
        # クレジット復活後の次回スケジュール実行で自動リトライされ、投稿が失われない。
        if code in {402, 429, 500, 502, 503, 504} or "CreditsDepleted" in msg:
            append_log(draft_path.name, {"event": "post_deferred", "status": code, "error": msg})
            print(f"[post DEFERRED status={code}] 一時的エラー。ドラフトを保持し次回リトライ: {msg}", file=sys.stderr)
            return 0
        FAILED.mkdir(exist_ok=True)
        shutil.move(str(draft_path), str(FAILED / draft_path.name))
        append_log(draft_path.name, {"event": "post_failed", "error": msg, "polished": polished})
        print(f"[post ERROR] {e}", file=sys.stderr)
        return 1

    tweet_id = result.get("data", {}).get("id")

    # 本ツイート投稿成功後、コメ欄に続きを自己リプ(失敗しても本投稿は成立済みなので致命にしない)。
    reply_id: str | None = None
    if thread and reply_text and tweet_id:
        try:
            reply_res = post(reply_text, in_reply_to_tweet_id=tweet_id)
            reply_id = reply_res.get("data", {}).get("id")
            print(f"[reply posted] https://x.com/{HANDLE}/status/{reply_id}")
        except Exception as e:
            append_log(draft_path.name, {"event": "reply_post_failed", "error": str(e), "reply_text": reply_text})
            print(f"[reply post ERROR(本投稿は成立)] {e}", file=sys.stderr)
    POSTED.mkdir(exist_ok=True)
    posted_name = f"{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}_{draft_path.name}"
    shutil.move(str(draft_path), str(POSTED / posted_name))
    (POSTED / (posted_name + ".result.json")).write_text(
        json.dumps(
            {
                "tweet_id": tweet_id,
                "text": polished,
                "quote_tweet_id": quote_id,
                "reply_tweet_id": reply_id,
                "reply_text": reply_text if thread else None,
                "raw": result,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    event_payload = {
        "event": "posted",
        "tweet_id": tweet_id,
        "url": f"https://x.com/{HANDLE}/status/{tweet_id}",
    }
    if quote_id:
        event_payload["quote_tweet_id"] = quote_id
    if reply_id:
        event_payload["reply_tweet_id"] = reply_id
    append_log(posted_name, event_payload)
    print(f"[posted] https://x.com/{HANDLE}/status/{tweet_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
