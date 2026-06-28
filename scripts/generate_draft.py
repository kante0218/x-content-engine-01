#!/usr/bin/env python3
"""髙橋敢輝(@kante0123) 用に、ペルソナ準拠の新規ドラフトを自動生成する。

- 5カテゴリ × 複数シードからランダム抽出(Claude / Codex の実践知を主軸)
- Claude API に「髙橋本人の長文の思考ツイート」を書かせ、drafts/pending/ に保存
- pending に既にファイルが残っている場合はスキップ(投稿待ちが先)

Usage:
    python3 scripts/generate_draft.py
    python3 scripts/generate_draft.py --theme A   # カテゴリ強制
    python3 scripts/generate_draft.py --force     # pending に残っていても追加生成
"""
from __future__ import annotations

import datetime as dt
import json
import os
import random
import sys
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

PENDING = ROOT / "drafts" / "pending"
POSTED = ROOT / "drafts" / "posted"
LOGS = ROOT / "logs"

MODEL = "claude-opus-4-8"

# テーマA-E: Claude / Codex の実践知を主軸に。A+B+C(=Claude/Codex/使い分け)で約75%。
# 「専門的で有益」=実際に手を動かした人にしか書けない具体テク・ハマり・回避策を出す。
THEMES = {
    "A": {
        "label": "Claude Code 実践テクニック",
        "ratio": 32,
        "seeds": [
            "CLAUDE.md にプロジェクト規約を書いておくと毎回の指示が消えて、精度が安定する話",
            "サブエージェントに調査を並列で投げて、メインのコンテキストを汚さない使い方",
            "plan mode(Shift+Tab)で実装前に計画を握ってから書かせると事故が激減する",
            "/hooks の Stop / PostToolUse に自動処理を挿して、投稿や日報を勝手に回す設計",
            "MCPサーバ経由で Slack / Gmail / Playwright を Claude から直接叩く構成",
            "settings.json の permissions allowlist を整えて、許可プロンプト地獄を消す",
            "スラッシュコマンドを自作して、定型の作業フローを一発で呼べるようにする",
            "長いセッションはコンテキスト要約と /resume で繋ぐ、握っておきたい情報の置き方",
            "出力をスキーマで縛る(structured output)と、エージェント運用が一気に安定する",
            "Claude Code に並列でファイル横断させる時、Explore系エージェントに任せる線引き",
        ],
    },
    "B": {
        "label": "Codex 実践テクニック",
        "ratio": 23,
        "seeds": [
            "AGENTS.md に規約を渡しておくと Codex の出力ブレが減る、Claude との対比",
            "Codex を対話ループで section ごとに質問→コード断片→反映、でUIを磨く回し方",
            "Codex に別視点のレビューをさせて、Claude が書いたコードの穴を潰す併走",
            "Codex CLI を実務のどのタスクで握るか、得意/不得意の手触りでの使い分け",
            "Codex に任せると速い領域、Claude に任せた方が良い領域の境界の引き方",
            "Codex の出力を鵜呑みにして事故った話と、型・テストを先に置く再発防止",
        ],
    },
    "C": {
        "label": "Claude × Codex 使い分け・マルチモデル",
        "ratio": 20,
        "seeds": [
            "Claude / Codex / Gemini を三者で投げて synthesize する(ccg型)実務の効き",
            "同じタスクでも Claude と Codex で出力の癖が違う、どっちに何を振るかの基準",
            "オーケストレーション(誰にどの工程を渡すか)の設計が品質の9割という実感",
            "作る人(Claude)とレビューする人(Codex)を分けると、自己承認の事故が減る",
            "モデルを使い分ける時のコストと速度のトレードオフ、どこを贅沢するか",
            "複数モデルで意見が割れた時、最後に人間が握る判断軸の置き方",
        ],
    },
    "D": {
        "label": "LLM/プロンプト/API 実装の手触り",
        "ratio": 15,
        "seeds": [
            "tool use はツール定義の粒度が精度を決める、細かく切るか粗く渡すかの判断",
            "RAGより先にやることがある——プロンプトの構造化とコンテキスト設計の効き",
            "prompt caching をどう効かせるか、コンテキスト長とトークン単価のトレードオフ",
            "Anthropic API で自分専用の業務エージェントを内製した構成の具体",
            "つまずいた API エラー(429/レート制限・コンテキスト超過)と地味に効く回避策",
            "AIに置き換わるのは『作業』、残るのは『要件定義』という確信の実装的根拠",
        ],
    },
    "E": {
        "label": "自分の事業でClaude/Codexをどう使っているか",
        "ratio": 10,
        "seeds": [
            "launchd × Claude Code で日報もSNS投稿も自動化、枯れた仕組みとの組み合わせが安定",
            "GitHub Actions の cron でサーバ常駐なしにエージェントを定期実行する設計",
            "ロボティクスの受託・社内ツールを、Claude/Codexで内製して回している実際",
            "個人や小チームが Claude/Codex を武器にして、作れる範囲が一気に広がった実感",
        ],
    },
}


def pick_theme(forced: str | None = None) -> tuple[str, str, str]:
    if forced:
        if forced not in THEMES:
            raise ValueError(f"theme は {list(THEMES)} のいずれか")
        t = THEMES[forced]
        return forced, t["label"], random.choice(t["seeds"])
    keys = list(THEMES.keys())
    weights = [THEMES[k]["ratio"] for k in keys]
    k = random.choices(keys, weights=weights, k=1)[0]
    return k, THEMES[k]["label"], random.choice(THEMES[k]["seeds"])


def recent_seeds_to_avoid(n: int = 12) -> list[str]:
    """直近 n 件の posted を見て、似たトピック連発を避けるためのヒント"""
    if not POSTED.exists():
        return []
    files = sorted(
        (p for p in POSTED.iterdir() if p.suffix not in {".json"} and not p.name.startswith(".")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:n]
    out = []
    for f in files:
        try:
            txt = f.read_text(encoding="utf-8").strip()
            if txt:
                out.append(txt[:140])
        except Exception:
            pass
    return out


GENERATE_SYSTEM = """あなたは「髙橋敢輝(@kante0123)」=clear AI株式会社 代表 本人として、
これから自分のXに投稿する単体ツイートの**素のドラフト**を1つ書く。

仕上げの推敲は別工程で行うので、ここでは:
- 完成形でなくてよい。考えの筋と熱量だけ正しく載せる
- **内容の主軸は Claude / Codex(AIコーディングエージェント)の専門的で有益な実践知**。読んだ人が「明日これ試そう」と思える具体テク・ハマり・回避策を1つ載せる
- **バズる種を仕込む**: ①1行目でスクロールが止まる強いフック(意外な結論/具体的な数字/失敗の告白)を必ず先頭に置く。自己紹介や「最近〜」の助走で始めない ②一番おいしい学びを先に出す(オチを最後に隠さない) ③保存(ブックマーク)したくなる具体(設定値・手順・数字)を1つ ④単体で引用されても刺さる、言い切りの一行を1つ
- **矢印「→」とトレンド感**: Before→After・原因→結果・手順A→B→Cのような変化や関係を「→」で1〜2箇所だけ視覚化すると、今のXで一目で伝わり保存されやすい(乱用はしない)。結論ファースト/手順は番号や箇条書きで分ける、という今の読まれ方を意識する
- **コメ欄に続けられる構造**: 本文は要点で締め、手順・設定値・回避策などの“細かい具体”は別に切り出せる形で持っておく(後工程で本文をコメ欄誘導型に再構成できるよう、具体は素材として豊富に書いておく)
- 長さは指定に従う。フック → 具体テク → ハマり/回避策 → 自分の解釈、の流れを基本に、短い時は1つの気づきを切れ味よく
- 一人称は必ず「自分」。「僕」「俺」は使わない。複数形は「自分たち」(「僕ら」NG)。経営者だが偉ぶらない、現場で手を動かしている当事者の温度
- 文末は「です・ます」の敬体で書く。常体(〜だ/〜である)やタメ口の言い切りは混ぜない
- **技術の具体に踏み込む**: Claude Code / Codex の機能名(CLAUDE.md・サブエージェント・MCP・hooks・plan mode・AGENTS.md 等)、設定、ハマりどころ、つまずいたエラー、回避策など、実際に手を動かした人にしか書けない手触りを入れる。抽象論や精神論で逃げない
- 固有名詞・数字で解像度を上げる(ただし未確定の調達額や顧客名は出さない)
- ただし衒学的・教科書的にはしない。当事者が「これ実際やってみたら」と語る温度を保つ
- 体言止め連発・倒置法の多用はしない。自然な語順で、密度で読ませる
- 啓蒙の型(「〜が重要です。なぜなら〜。まとめると〜」)は禁止。AIが書いた流暢さを出さない
- 毎回ポジティブ総括しない。迷い・弱音・前言撤回も時々出してよい
- 絵文字はほぼ使わない(0〜1個)。ハート/キラキラ/女性的な絵文字は使わない

# 本人プロフィール
- 髙橋敢輝。clear AI株式会社 代表(clearai.jp / 茨城・水戸)
- ロボットで「人手不足 × 危険現場」を解決する起業家。日々 Claude Code / Codex を実務で使い倒して事業を作っている側
- Claude Code / Codex / Gemini を業務に組み込み、日報・SNS・受託・社内ツールを内製/自動化している
- 事業: ヒューマノイド外装ブランド YOROI / ロボットレンタル(RaaS) / AI受託・AIエージェント代行
- 戦略観: 純SaaSは推さず Service-as-Software/成果報酬。AIに置き換わるのは作業、残るのは要件定義
- 自分の武器は「没頭力」。判断軸は「自分が成長する方」
- 関心: Claude Code, Codex CLI, AGENTS.md/CLAUDE.md, MCP, サブエージェント, tool use, structured output, prompt caching, マルチエージェント, API, 自動化(launchd/GitHub Actions)

# 絶対NG
- 他社/他者の名指し批判、煽り、勝ち組/負け組
- 未確定の数字を断定(調達額・売上・取引先名)→ ぼかすか書かない
- 機密(顧客名・契約・未公開の資本政策の細部)
- 政治・宗教・性別対立
- マジ/ガチ連発、過度な絵文字、強い断定の決めつけ

# 出力
- 本文のドラフトだけを返す。説明・前置き・引用符は一切なし
- 仕上げで整える前提なので完成度より、考えの筋と熱量を優先"""


def generate(theme_key: str, theme_label: str, seed: str, avoid: list[str]) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(".env に ANTHROPIC_API_KEY が未設定")

    avoid_block = ""
    if avoid:
        avoid_block = (
            "\n# 直近の自分の投稿(似た角度・似た書き出しを避ける)\n"
            + "\n".join(f"- {t}" for t in avoid)
        )

    user_msg = (
        f"# 今回のテーマ\nカテゴリ: {theme_key} / {theme_label}\nネタの種: {seed}\n"
        + avoid_block
        + "\n\n上記の種を起点に、髙橋本人が今ふと書きたくなって書く長文の思考ツイートのドラフトを1つだけ。"
        "完成形でなくてOK、考えの筋と熱量を素直に載せて。"
    )

    client = Anthropic(api_key=api_key)
    res = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=GENERATE_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = "".join(block.text for block in res.content if block.type == "text").strip()
    return text


def append_log(payload: dict) -> None:
    LOGS.mkdir(exist_ok=True)
    log = LOGS / "generate.log"
    payload = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(), **payload}
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def main() -> int:
    args = sys.argv[1:]
    force = "--force" in args
    if force:
        args.remove("--force")
    theme_forced = None
    if "--theme" in args:
        i = args.index("--theme")
        theme_forced = args[i + 1]

    PENDING.mkdir(parents=True, exist_ok=True)
    existing = [p for p in PENDING.iterdir() if p.is_file() and not p.name.startswith(".")]
    if existing and not force:
        print(f"[skip] pending に {len(existing)} 件残っています。先に投稿してください(--force で追加生成)")
        append_log({"event": "skipped", "pending_count": len(existing)})
        return 0

    k, label, seed = pick_theme(theme_forced)
    print(f"[theme] {k} / {label}\n[seed] {seed}\n")
    avoid = recent_seeds_to_avoid()
    draft = generate(k, label, seed, avoid)
    print(f"[draft]\n{draft}\n")

    fname = f"{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}_{k}_auto.md"
    (PENDING / fname).write_text(draft, encoding="utf-8")
    append_log({"event": "generated", "file": fname, "theme": k, "label": label, "seed": seed, "chars": len(draft)})
    print(f"[saved] drafts/pending/{fname}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
