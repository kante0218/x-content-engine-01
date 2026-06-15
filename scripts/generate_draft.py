#!/usr/bin/env python3
"""髙橋敢輝(@kante0123) 用に、ペルソナ準拠の新規ドラフトを自動生成する。

- 6カテゴリ × 複数シードからランダム抽出(AI/テクノロジー/API/ヒューマノイド軸)
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

# テーマA-F: persona_axis.md と同期。技術寄りに比率を傾斜(A+B+C=80%)。
THEMES = {
    "A": {
        "label": "ロボティクス技術(制御・学習・ハード)",
        "ratio": 28,
        "seeds": [
            "Sim2Realのギャップを埋めるドメインrandomization——摩擦・質量・遅延をどう振るか",
            "MuJoCo Playgroundで四足歩行をPPO学習させたときの報酬設計のハマりどころ",
            "ヒューマノイドのロコモーション制御、ZMPベースとRLベースの実際の使い分け",
            "アクチュエータのトルク制御と減速比、ここが歩行の安定性を握っている話",
            "VLA(Vision-Language-Action)モデルがロボット制御を変えつつある実感",
            "Unitree G1のSDKを叩いて関節を動かすまでの、ドキュメントと現実の差",
            "Sim上で歩けたポリシーが実機で転ぶ理由——センサノイズと制御周期の壁",
            "外装(YOROI)設計が放熱・重心・メンテ性という制御外の制約に効いてくる話",
            "強化学習のsim高速化(GPU並列・JAX)が学習時間を桁で変えた話",
            "ロボットの自己位置推定(SLAM)が点検現場の照明・粉塵で崩れる現実",
        ],
    },
    "B": {
        "label": "AIエージェント・LLM実装",
        "ratio": 27,
        "seeds": [
            "AIエージェントにtool useをやらせる時、ツール定義の粒度が精度を決める話",
            "Claude Code / Codex / Gemini を実務でどう使い分けているか(具体タスク別)",
            "launchd × LLMで日報もSNSも自動化、枯れた仕組みとの組み合わせが一番安定する",
            "RAGより先にやることがある——プロンプトの構造化とコンテキスト設計の効き",
            "マルチエージェントを組むと、オーケストレーションの設計が9割という実感",
            "LLMの出力をスキーマで縛る(structured output)と運用が一気に楽になる",
            "エージェントに任せる/人が握るの線引きが、そのまま受託の品質になる話",
            "コンテキスト長とコストのトレードオフ、キャッシュをどう効かせるか",
            "AIに置き換わるのは『作業』、残るのは『要件定義』という確信の実装的根拠",
        ],
    },
    "C": {
        "label": "API・開発・自作の手触り",
        "ratio": 25,
        "seeds": [
            "X API v2をOAuth1.0aで叩いて自動投稿を組んだ、権限とトークンのハマり",
            "APIの料金設計(従量・トークン単価)を読むと、その会社の稼ぎ方が透ける",
            "Anthropic APIで自分専用の業務エージェントを内製した構成の話",
            "つまずいたAPIエラー(403/429/レート制限)と、地味だけど効く回避策",
            "個人や小チームがAPIを組み合わせて武器を自作できる時代の実際",
            "Webhookとcron(GitHub Actions)で、サーバ常駐なしに自動化を回す設計",
            "型とテストを先に書くと、AIに書かせるコードの事故が激減する話",
            "自前で作った方が速い/安い領域が、AIで一気に広がった実感(具体例)",
        ],
    },
    "D": {
        "label": "技術起点の事業判断",
        "ratio": 10,
        "seeds": [
            "ハードの試作は金と時間がかかる——技術ロードマップと資金繰りの噛み合わせ",
            "『作れる』と『売れる』の間にある運用・保守・データの厚みをどう積むか",
            "技術選定で『枯れた技術＋最新の一点』に張ると事故が減る経験則",
            "自前実装かSaaS採用か、内製の境界を技術と人員から引く基準",
            "0→1で一番怖いのは失敗より『動かないこと』だと気づいた話",
        ],
    },
    "E": {
        "label": "技術で解く社会課題(点検・危険現場)",
        "ratio": 6,
        "seeds": [
            "変電所・火力・廃炉の点検を、自律移動＋センサ＋遠隔でどう置き換えるか",
            "危険現場の点検データを溜める飛輪が、そのまま技術的な堀になる話",
            "エネルギー業種特化——汎用でなく現場制約に最適化する技術判断",
            "日本のAI/ロボット投資が世界より一桁小さい現実への危機感",
        ],
    },
    "F": {
        "label": "技術の未来予測",
        "ratio": 4,
        "seeds": [
            "VLAと基盤モデルがロボットの『汎化』をどこまで連れて行くかの読み",
            "Sim2Realが解けた先に、ロボット実装の何がボトルネックとして残るか",
            "AIと人間の役割分担は『判断』と『作業』で線が引かれていく",
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
- **基本は長文**。観察 → 具体 → 自分の解釈 → 自分が賭けている方向、まで思考を書き切る
- 一人称は必ず「自分」。「僕」「俺」は使わない。複数形は「自分たち」(「僕ら」NG)。経営者だが偉ぶらない、現場で手を動かしている当事者の温度
- **技術の具体に踏み込む**: 手法名・パラメータ・ハマりどころ・つまずいたエラー・回避策など、実際に手を動かした人にしか書けない手触りを入れる。経営論や抽象論で逃げない
- 固有名詞・数字で解像度を上げる(ただし未確定の調達額や顧客名は出さない)
- ただし衒学的・教科書的にはしない。当事者が「これ実際やってみたら」と語る温度を保つ
- 体言止め連発・倒置法の多用はしない。自然な語順で、密度で読ませる
- 啓蒙の型(「〜が重要です。なぜなら〜。まとめると〜」)は禁止。AIが書いた流暢さを出さない
- 毎回ポジティブ総括しない。迷い・弱音・前言撤回も時々出してよい
- 絵文字はほぼ使わない(0〜1個)。ハート/キラキラ/女性的な絵文字は使わない

# 本人プロフィール
- 髙橋敢輝。clear AI株式会社 代表(clearai.jp / 茨城・水戸)
- ロボットで「人手不足 × 危険現場」を解決する起業家。AIコンサルではなくロボティクスを社会実装する側
- 事業: ヒューマノイド外装ブランド YOROI / ロボットレンタル(RaaS) / エネルギー点検ロボOS / AI受託・AIエージェント代行
- 戦略観: 日本はハード本体で米中と殴り合わず、外装×運用×データ飛輪に集中すべき。純SaaSは推さず Service-as-Software/成果報酬
- 自分の武器は「没頭力」。判断軸は「自分が成長する方」
- 北極星: ユニコーン/IPO、将来的に大型Exitも視野
- 関心: Unitree G1/Go2, AGIBOT, Optimus, Figure, Sim2Real, 強化学習(MuJoCo), AIエージェント, API, 茨城の廃炉(JAEA)

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
