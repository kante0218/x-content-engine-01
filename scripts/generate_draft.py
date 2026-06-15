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

# テーマA-F: persona_axis.md と同期
THEMES = {
    "A": {
        "label": "ヒューマノイド/ロボティクス最前線",
        "ratio": 25,
        "seeds": [
            "Unitree G1を実際に動かして感じた、デモ映像と現場のギャップ",
            "日本のロボットスタートアップがハード本体で米中と殴り合うのは筋が悪い理由",
            "外装(YOROI)に振り切る戦略——機体は仕入れ、勝負は見た目と運用とデータ",
            "Tesla OptimusやFigureを見て、日本が取りに行くべき空白はどこか",
            "Sim2Real:シミュレータで歩いたロボットが現実で転ぶ瞬間に学んだこと",
            "強化学習(MuJoCo Playground)で四足歩行を学習させた手応え",
            "ロボットを『買う』時代から『借りる』(RaaS)時代へ移る必然",
            "ヒューマノイドが工場でなく、まず変電所や点検現場から来る理由",
            "中国のロボット量産スピードを見て、日本が勝てる土俵を再定義した話",
        ],
    },
    "B": {
        "label": "AIエージェント・自動化の実践",
        "ratio": 20,
        "seeds": [
            "自分のSNS運用も日報もlaunchdとAIエージェントで全自動化している話",
            "Claude Code / Codex / Gemini を実務でどう使い分けているか",
            "AIエージェントが代行できる『人の作業』の境界線は今どこにあるか",
            "純SaaSはもう終わり——Service-as-Software/成果報酬に賭ける理由",
            "AIに置き換わるのは『作業』、残るのは『要件定義』という確信",
            "一人の経営者がAIエージェント10体を率いて回す日常のリアル",
            "受託開発がAIで原価崩壊する中、価値はどこに移動するか",
            "社内バックオフィスをAIで全自動化して、本業に時間を寄せた話",
        ],
    },
    "C": {
        "label": "API・開発の手触り",
        "ratio": 15,
        "seeds": [
            "X APIを叩いて自動投稿を組んだとき、URL付き投稿の原価に驚いた話",
            "Anthropic APIで自分専用の業務エージェントを内製している話",
            "個人や小チームがAPIを組み合わせて武器を自作できる時代になった",
            "APIの料金設計を読むと、その会社が何で稼ぐつもりかが透けて見える",
            "つまずいたAPIエラーと、その回避策の地味だけど効く話",
            "コードを書けなくてもAIと一緒なら作れる、の実際の限界と可能性",
            "自前で作った方が速い/安い領域が、AIで一気に広がった実感",
        ],
    },
    "D": {
        "label": "起業家/経営のリアル",
        "ratio": 15,
        "seeds": [
            "茨城・水戸から世界を狙うと決めた理由",
            "0→1で一番怖いのは失敗より『動かないこと』だと気づいた話",
            "補助金で滑走路を作り、ディープテックVCで大型化する資金戦略の現実",
            "自分の唯一の武器は『没頭力』だと腹を括った話",
            "完璧主義とスピードの間で、今日もスピードを選んだ理由",
            "経営の意思決定で、迷ったら『自分が成長する方』を選ぶ基準",
            "資本政策や役員報酬で学んだ、後から効いてくる地味な判断",
            "ユニコーンを本気で目指すと言葉にしてから変わったこと",
        ],
    },
    "E": {
        "label": "社会課題(人手不足・地方・危険現場)",
        "ratio": 15,
        "seeds": [
            "変電所・火力・原子力廃炉の点検を、人からロボットへ移すべき理由",
            "地方の労働力枯渇は『気合』では解けない、構造の話",
            "危険作業に人を行かせ続ける現場を、テクノロジーで変えたい",
            "エネルギー業種に特化する——広く浅くやらないと決めた理由",
            "日本のAI/ロボット投資が世界より一桁小さい現実への危機感",
            "人手不足はピンチではなく、ロボット社会実装の最大の追い風",
            "茨城のJAEA/廃炉という現場が、世界に通じる堀になりうる話",
        ],
    },
    "F": {
        "label": "未来予測・思想",
        "ratio": 10,
        "seeds": [
            "10年後、ヒューマノイドが家庭に来る日を本気で逆算する",
            "AIと人間の役割分担は『判断』と『作業』で線が引かれていく",
            "技術楽観だけでも現場主義だけでもダメ、両輪で見る視点",
            "便利になるほど、人間に残る仕事は『意味を決めること』になる",
            "労働の定義が変わる時代に、子ども世代に何を残せるか",
            "ロボットが当たり前になった世界で、人は何に時間を使うか",
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
- 固有名詞・数字で解像度を上げる(ただし未確定の調達額や顧客名は出さない)
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
