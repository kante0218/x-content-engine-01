#!/usr/bin/env python3
"""髙橋敢輝 (@kante0123) 向けに、ドラフトを推敲する。

Usage:
    python3 scripts/polish_draft.py drafts/pending/xxx.md
    echo "原文..." | python3 scripts/polish_draft.py -
    python3 scripts/polish_draft.py xxx.md --length 長文

文字数上限は .env の X_MAX_CHARS(既定280)。
X Premium長文ポストを使う場合は X_MAX_CHARS=900 などにすると、推敲も長文化する。
"""
from __future__ import annotations

import os
import random
import sys
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

MODEL = "claude-opus-4-8"


def _max_chars() -> int:
    try:
        return int(os.getenv("X_MAX_CHARS", "280"))
    except ValueError:
        return 280


SYSTEM_PROMPT = """あなたは「髙橋敢輝(@kante0123)」=clear AI株式会社 代表 本人として、自分のXアカウントに投稿する単体ツイートを書く。
原文ドラフトを、自分の言葉に書き直してください。

# 大前提
- AIが書いたとバレないこと。流暢すぎる説明・三段論法の型・啓蒙臭を消す
- 構成テンプレ(問題提起→理由→まとめ)を毎回踏まない。毎回違う角度から入って、違う場所で終わる
- 「〜しましょう」「〜が大事だと思います」みたいな定型の締めや教え垂れは禁止
- 毎回ポジティブに着地させない。迷い・弱音・前言撤回・割り切れなさも時々残す

# 人物プロフィール(忠実に守る)
- 髙橋敢輝。clear AI株式会社 代表(clearai.jp / 茨城・水戸)
- 肩書きは経営者だが、発信の軸は「ロボットで人手不足×危険現場を解決する起業家」。AIコンサルの人ではない
- 事業: ヒューマノイド外装ブランド YOROI / ロボットレンタル(RaaS) / エネルギー点検ロボOS / AI受託・AIエージェント代行
- 戦略観: 日本はハード本体で米中と殴り合わず「外装×運用×データ飛輪」に集中すべき。純SaaSは推さず、Service-as-Software/AIエージェント代行/成果報酬モデルを軸にする
- 自分の唯一の武器は「没頭力」。判断軸は「自分が成長する方を選ぶ」
- 北極星: ユニコーン/IPO、将来的に大型Exitも視野。茨城・水戸から世界を狙う
- よく触れる技術: Unitree G1/Go2, AGIBOT, Tesla Optimus, Figure, Sim2Real, 強化学習(MuJoCo Playground), AIエージェント(Claude Code/Codex/Gemini), 各種API, 茨城のJAEA/廃炉

# 口調・トーン(絶対ルール)
- 一人称は必ず「自分」。「僕」「俺」は使わない。複数形は「自分たち」(「僕ら」NG)。偉ぶらない、現場で手を動かしている当事者の温度
- 文末は**必ず「です・ます」の敬体で統一**する。「〜だ」「〜である」「〜だった」「〜してた」「〜なんだ」などの常体・タメ口は混ぜない(体言止めの多用も避ける)。丁寧だが固すぎない、自然な敬体で書く
- 固有名詞・数字で解像度を上げる。抽象論で終わらせない
- **技術寄りで書く**: 手法名・パラメータ・ハマりどころ・エラーと回避策など、実際に触った人の手触りを残す。経営論や精神論に薄めない。ただし衒学的・教科書的にはせず、当事者の温度を保つ
- 改行を効かせて読みやすく。長文でも一気に読ませる density を出す
- 言い切るが煽らない。決めつけ・上から目線・勝ち負けの語りはしない
- カタカナ多用は可だが、専門用語は文脈で意味が伝わるように

# 絶対NG表現
- マジ / ガチ の連発、「絶対儲かる」「情弱」「勝ち組/負け組」など強い断定・煽り
- 他社・他者の名指し批判
- 未確定の数字を断定(調達額・売上・取引先名)→ ぼかすか書かない
- 機密(顧客名・契約・未公開の資本政策の細部)
- 政治・宗教・性別対立、炎上狙い、スピリチュアル断定
- 倒置法の多用、体言止めの連発

# 投稿軸(原文がどれに該当するかを判断して書く)
A. ヒューマノイド/ロボティクス最前線(Unitree/Optimus/外装/RaaS/Sim2Real)
B. AIエージェント・自動化の実践(Claude Code等の使い分け、SaaSの終わり、要件定義)
C. API・開発の手触り(APIを叩いて武器を内製、料金の現実、つまずきと回避)
D. 起業家/経営のリアル(0→1、茨城、資金戦略、没頭力、迷いと賭け)
E. 社会課題(人手不足・地方・危険現場・エネルギー点検・廃炉・日本の投資不足)
F. 未来予測・思想(10年後の労働、AIと人の役割、要件定義こそ人間の価値)

# 役割
- フォロワーに見せたい姿は「ロボティクスを社会実装しに行く、思考の解像度が高い起業家」
- ターゲット読者は、テクノロジー/スタートアップ/ロボティクスに関心がある人、未来の仲間・投資家・顧客
- 学びと当事者の熱量を両立させる。教えるのでなく、自分が考えた跡を見せる

# 絵文字
- 基本ほぼ使わない(0〜1個)。このあとユーザーメッセージで指定するパレットに従う
- ハート/キラキラ/花など女性的な絵文字は使わない。男性経営者の硬めトーンを保つ

# 出力フォーマット
推敲後の本文だけ返す。説明・前置き・引用符・「以下が...」は一切出力しない。"""


# 絵文字は控えめ。事業観に合う硬めのものだけ、たまに1個。
EMOJI_POOL = ["🤖", "🦾", "🚀", "🔧", "🌏", "⚙️", "🧠", "📈", "🛠️"]


def _emoji_instruction() -> str:
    r = random.random()
    if r < 0.6:
        return (
            "# 今回の絵文字\n- 今回は**絵文字を使わない**。文章だけで成立させる\n"
        )
    pick = random.choice(EMOJI_POOL)
    return (
        "# 今回の絵文字\n"
        f"- 今回は**絵文字を1個だけ**、`{pick}` を使ってよい(使わなくてもよい)\n"
        "- 文末固定にせず、自然な位置に。ハート/キラキラ/花は禁止\n"
    )


def _length_instruction(forced: str | None = None) -> tuple[str, str]:
    limit = _max_chars()
    if limit <= 300:
        # 通常(無料/280)アカウント: 280以内で密度を出す長文
        modes = [
            (2, "中文", "今回は5〜6行、180〜220文字程度で。"),
            (8, "長文", f"今回は**長文**で。{min(limit-5, 275)}文字前後、**絶対に{limit}文字を超えない**。観察+具体+解釈+賭けの4ブロックで密度を出す。改行を効かせる。"),
        ]
    else:
        # X Premium 長文ポスト: しっかり書き切る
        target = min(limit - 50, 900)
        modes = [
            (3, "中長文", f"今回は400〜600文字で。観察+具体+解釈+賭けを、改行を効かせて読みやすく。"),
            (7, "長文", f"今回は**しっかり長文**で。{target}文字前後を狙い、**絶対に{limit}文字を超えない**。導入で引き込み、具体例と数字で解像度を上げ、自分の解釈と賭けている方向で締める。段落を分けて一気に読ませる。"),
        ]
    if forced:
        for _, label, instr in modes:
            if label == forced:
                return label, instr
        raise ValueError(f"length は {[m[1] for m in modes]} のいずれか")
    weights = [w for w, _, _ in modes]
    choice = random.choices(modes, weights=weights, k=1)[0]
    return choice[1], choice[2]


def polish(draft: str, length: str | None = None) -> str:
    draft = draft.strip()
    if not draft:
        raise ValueError("空のドラフトは推敲できません")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(".env に ANTHROPIC_API_KEY が未設定")

    limit = _max_chars()
    client = Anthropic(api_key=api_key)

    # 上限超過は自動でリトライ: 2回目以降は短い長さモードを強制し、明示的に上限を伝える。
    fallback_lengths = [None, "中長文", "中文"] if limit > 300 else [None, "中文", "短文"]
    if length is not None:
        fallback_lengths = [length, "中文", "短文"]

    last_text = ""
    for attempt, len_mode in enumerate(fallback_lengths, start=1):
        try:
            label, length_instruction = _length_instruction(len_mode)
        except ValueError:
            label, length_instruction = _length_instruction(None)
        emoji_instruction = _emoji_instruction()
        over_note = ""
        if attempt > 1:
            over_note = (
                f"\n# 重要(前回オーバー)\n- 前回は{len(last_text)}文字で上限{limit}を超えました。"
                f"今回は**必ず{limit}文字以内**に収めてください。内容を削ってでも短くする。\n"
            )
        user_msg = (
            "以下のドラフトをXに投稿する自分のツイートに書き直してください。\n\n"
            f"{length_instruction}\n\n"
            f"{emoji_instruction}"
            f"{over_note}\n"
            "---\n"
            f"{draft}\n"
            "---"
        )
        res = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = "".join(block.text for block in res.content if block.type == "text").strip()
        last_text = text
        if len(text) <= limit:
            sys.stderr.write(f"[length_mode={label} chars={len(text)} limit={limit} attempt={attempt}]\n")
            return text
        sys.stderr.write(f"[over limit] {len(text)}>{limit} (attempt={attempt}/{len(fallback_lengths)}) → 短く再推敲\n")

    raise RuntimeError(f"推敲結果が{len(last_text)}文字>{limit}。{len(fallback_lengths)}回試しても収まりませんでした")


def main() -> int:
    args = sys.argv[1:]
    length = None
    if "--length" in args:
        i = args.index("--length")
        length = args.pop(i + 1)
        args.pop(i)
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    arg = args[0]
    if arg == "-":
        draft = sys.stdin.read()
    else:
        draft = Path(arg).read_text(encoding="utf-8")
    print(polish(draft, length=length))
    return 0


if __name__ == "__main__":
    sys.exit(main())
