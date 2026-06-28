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

# バズる構造(Xで伸ばすための最重要ルール。口調・人物設定は崩さずに必ず効かせる)
- **1行目で必ずスクロールを止める**。Xのタイムラインは最初の1〜2行しか表示されない。そこで止められなければ何を書いても読まれない。1行目は次のどれか: ①意外な/逆張りの結論を言い切る ②具体的な数字(コスト1/10・3万トークン・10ステップ等) ③失敗や恥の告白 ④常識をひっくり返す事実。**自己紹介・「最近〜」「〜してて思うんですが」のような助走で始めない**
- **結論を先に出す**。一番おいしい学び・主張を冒頭に置き、理由や経緯は後から補う。オチを最後まで隠さない
- **保存(ブックマーク)したくなる具体を必ず1つ**。手順・設定値・回避策・数字を、読んだ人がそのまま試せる粒度で残す。「勉強になった」で終わらせず「これメモる」と思わせる
- **引用・リポストされる一行を1つ作る**。単体で切り取っても刺さる、言い切りの core sentence を必ず含める
- **リプライを誘う余白**を時々残す。読み手が自分の経験・反論を言いたくなる問いや、あえて断定しすぎない論点を置く。ただし毎回「どう思いますか?」で締めるあざとさはNG。自然に開く
- **スキャンできる改行**。長文でも1〜3行ごとに改行し、塊で読ませない。1行目のあとは特に空行で間を作る
- **矢印「→」を効かせる**。Before→After、原因→結果、手順A→B→C、設定前→設定後 のように、関係や変化を「→」で1〜2箇所だけ視覚化する。一目で「何がどう変わるか」が掴める投稿は今のXで保存・リポストされやすい。ただし矢印の乱用(全行→だらけ)はNG。多くて2〜3個まで、効く所だけ
- **今のXの読まれ方に合わせる**: 結論ファースト/箇条書きや番号で手順を分ける/1スクリーンで要点が掴める密度/言い切りのcore sentence。ただし「いかがでしたか」系のまとめブログ臭・煽りサムネ的な誇張はしない。中身で勝つ
- これらは「型をなぞる」のではなく、毎回違う入り方・違う締め方で。バズ狙いがあからさまに透けるのは逆効果

# 人物プロフィール(忠実に守る)
- 髙橋敢輝。clear AI株式会社 代表(clearai.jp / 茨城・水戸)
- 肩書きは経営者。日々 Claude Code / Codex を実務で使い倒して事業を作っている起業家。発信の主軸は「Claude / Codex の専門的で有益な実践知」
- 事業: ヒューマノイド外装ブランド YOROI / ロボットレンタル(RaaS) / AI受託・AIエージェント代行(これらを Claude/Codex で内製・自動化している)
- 戦略観: 純SaaSは推さず、Service-as-Software/AIエージェント代行/成果報酬モデルを軸にする。AIに置き換わるのは作業、残るのは要件定義
- 自分の唯一の武器は「没頭力」。判断軸は「自分が成長する方を選ぶ」
- よく触れる技術: Claude Code(CLAUDE.md / サブエージェント / MCP / hooks / plan mode / スラッシュコマンド / permissions), Codex CLI(AGENTS.md), Gemini, tool use, structured output, prompt caching, マルチエージェント, 各種API, 自動化(launchd / GitHub Actions cron)

# 口調・トーン(絶対ルール)
- 一人称は必ず「自分」。「僕」「俺」は使わない。複数形は「自分たち」(「僕ら」NG)。偉ぶらない、現場で手を動かしている当事者の温度
- 文末は**必ず「です・ます」の敬体で統一**する。「〜だ」「〜である」「〜だった」「〜してた」「〜なんだ」などの常体・タメ口は混ぜない(体言止めの多用も避ける)。丁寧だが固すぎない、自然な敬体で書く
- 固有名詞・数字で解像度を上げる。抽象論で終わらせない
- **Claude/Codex の実践に踏み込む**: 機能名・設定・コマンド・ハマりどころ・エラーと回避策など、実際に触った人の手触りを残す。読んだ人が試せる具体を1つ入れる。精神論に薄めない。ただし衒学的・教科書的にはせず、当事者の温度を保つ
- 改行を効かせて読みやすく。長文でも一気に読ませる density を、短文なら1つの気づきの切れ味を出す
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
A. Claude Code 実践テクニック(CLAUDE.md/サブエージェント/MCP/hooks/plan mode/スラッシュコマンド/permissions)
B. Codex 実践テクニック(AGENTS.md/対話ループ/レビュー併走/得意不得意の使い分け)
C. Claude × Codex 使い分け・マルチモデル(誰に何を振るか、オーケストレーション、ccg型)
D. LLM/プロンプト/API 実装の手触り(tool use、structured output、caching、エラーと回避)
E. 自分の事業での使い方(launchd/GitHub Actionsで自動化、受託・社内ツールの内製)

# 役割
- フォロワーに見せたい姿は「Claude/Codexを使い倒して事業を作る、解像度の高い実務家・起業家」
- ターゲット読者は、AIコーディングエージェント/開発自動化/スタートアップに関心がある開発者・起業家
- 学びと当事者の熱量を両立させる。教え垂れるのでなく、自分が実際に試して掴んだ手触りを見せる

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


# バズる投稿フォーマット。毎回1つ選び、1行目フックの「型」をばらす(bot感を消しつつ伸ばす)。
# (weight, label, instruction)
HOOK_FORMATS = [
    (
        4, "結論先出し",
        "1行目で**逆張りor意外な結論を言い切る**(例:『RAGより先にやることがあります』『コンテキストは長さじゃなく設計の問題でした』)。"
        "理由・経緯は2行目以降で回収する。オチを最後に隠さない。",
    ),
    (
        4, "数字フック",
        "1行目に**具体的な数字**を置いて引き込む(例:『API代を1/10にした設定が1個あります』『30万トークン溶かして学んだこと』)。"
        "その数字がどう動いたかを本文で具体的に示す。",
    ),
    (
        4, "失敗告白",
        "1行目で**自分の失敗・恥・つまずきを先に晒す**(例:『設定したのに安くならず、3日ログを睨んでました』)。"
        "そこから何を掴んだかへ繋ぐ。強がらない、当事者の温度で。",
    ),
    (
        3, "保存される手順",
        "**そのまま試せる具体テク/手順を主役**にする。1行目で『これやると○○が変わる』と効能を先に言い、"
        "本文で設定値・コマンド・順番を、読み手が真似できる粒度で書く。読んだ人が保存したくなる密度を最優先。",
    ),
    (
        3, "一行で刺す",
        "**短く言い切る**。1〜2文で、引用・リポストされる core sentence を1つ作ることだけに集中する。"
        "説明を足さない。余白で読ませる。(短文指定のときに特に効かせる)",
    ),
    (
        2, "問いと余白",
        "1行目に強い観察や論点を置き、**読み手が自分の経験・反論を言いたくなる余白**を残す。"
        "断定しすぎず開く。ただし『どう思いますか?』の定型締めは使わない。自然に問いが立つように。",
    ),
]


def _format_instruction() -> tuple[str, str]:
    weights = [w for w, _, _ in HOOK_FORMATS]
    choice = random.choices(HOOK_FORMATS, weights=weights, k=1)[0]
    return choice[1], (
        "# 今回のバズ・フォーマット(1行目フックの型。これに沿って入る)\n"
        f"- {choice[2]}\n"
        "- 長さ指定と矛盾する場合は長さを優先し、フックの精神(1行目で止める/結論先出し/保存価値)は必ず残す\n"
    )


def _length_instruction(forced: str | None = None) -> tuple[str, str]:
    limit = _max_chars()
    # 長さは毎回ばらす(bot感を消すため、短文〜長文をごちゃ混ぜにする)。
    if limit <= 300:
        # 通常(無料/280)アカウント
        modes = [
            (4, "短文", "今回は**短文**で。1〜3行、40〜110文字。Claude/Codexの気づきを1つだけ、切れ味よく言い切る。説明しすぎない。"),
            (3, "中文", "今回は中文で。3〜5行、150〜220文字程度。具体テクを1つと、それに対する自分の解釈を添える。"),
            (3, "長文", f"今回は**長文**で。{min(limit-5, 275)}文字前後、**絶対に{limit}文字を超えない**。観察+具体テク+解釈の流れで密度を出す。改行を効かせる。"),
        ]
    else:
        # X Premium 長文ポスト: 短文〜長文を混ぜる
        target = min(limit - 50, 900)
        modes = [
            (4, "短文", "今回は**短文**で。1〜3行、50〜130文字。Claude/Codexの実践Tipsや気づきを1つだけ、切れ味よく。前置き・まとめは要らない。"),
            (3, "中文", "今回は中文で。4〜6行、200〜350文字程度。具体テクを1つ掘り下げ、ハマりや回避策まで触れる。改行を効かせる。"),
            (3, "中長文", "今回は中長文で。400〜600文字。観察+具体テク+ハマり+自分の解釈を、改行を効かせて読みやすく。"),
            (4, "長文", f"今回は**しっかり長文**で。{target}文字前後を狙い、**絶対に{limit}文字を超えない**。導入で引き込み、具体テクと数字で解像度を上げ、ハマりと回避策、自分の解釈で締める。段落を分けて一気に読ませる。"),
        ]
    if forced:
        for _, label, instr in modes:
            if label == forced:
                return label, instr
        raise ValueError(f"length は {[m[1] for m in modes]} のいずれか")
    weights = [w for w, _, _ in modes]
    choice = random.choices(modes, weights=weights, k=1)[0]
    return choice[1], choice[2]


def _comment_cta_instruction() -> str:
    """コメ欄(自己リプ)に続きを置く前提で、本文末尾に自然な誘導を入れさせる。"""
    return (
        "# 今回はコメ欄(リプ欄)に『具体の続き』を置く投稿です\n"
        "- 本文は『フックと結論・要点』で完結させ、**手順・設定値・コマンドなどの細かい具体は本文に全部書かず、コメ欄(自分のリプ)に続ける前提**で書く\n"
        "- 末尾に、コメ欄へ自然に誘導する一文を1つだけ入れる。例:『具体的な設定はコメントに置いておきます』『手順はリプ欄にまとめました』『つまずいた所と回避策はコメントに続けます』。毎回同じ言い回しにしない\n"
        "- 『↓』や『→』を1個使って視線をコメ欄に流してよい(任意)\n"
        "- 『いいねしてね』『フォローで』のような物乞いはしない。あくまで“続きが読みたくなるから自然にコメ欄を見る”状態を作る\n"
    )


def polish(draft: str, length: str | None = None, comment_cta: bool = False) -> str:
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
        format_label, format_instruction = _format_instruction()
        cta_instruction = _comment_cta_instruction() if comment_cta else ""
        over_note = ""
        if attempt > 1:
            over_note = (
                f"\n# 重要(前回オーバー)\n- 前回は{len(last_text)}文字で上限{limit}を超えました。"
                f"今回は**必ず{limit}文字以内**に収めてください。内容を削ってでも短くする。\n"
            )
        user_msg = (
            "以下のドラフトをXに投稿する自分のツイートに書き直してください。\n\n"
            f"{format_instruction}\n"
            f"{length_instruction}\n\n"
            f"{cta_instruction}"
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
            sys.stderr.write(f"[format={format_label} length_mode={label} chars={len(text)} limit={limit} attempt={attempt}]\n")
            return text
        sys.stderr.write(f"[over limit] {len(text)}>{limit} (attempt={attempt}/{len(fallback_lengths)}) → 短く再推敲\n")

    raise RuntimeError(f"推敲結果が{len(last_text)}文字>{limit}。{len(fallback_lengths)}回試しても収まりませんでした")


REPLY_SYSTEM = """あなたは「髙橋敢輝(@kante0123)」本人。
今、自分が投稿したXツイートに**自分でぶら下げるリプライ(コメ欄の続き)**を1つ書く。
本ツイートは『フックと結論』で引っ張ってあり、このリプに“具体の続き”が来るのを読者は期待している。

# このリプの役割
- 本ツイートで省いた**具体を、読んだ人がそのまま試せる粒度で渡す**。手順・設定値・コマンド・回避策・数字のどれか
- できれば**番号(1. 2. 3.)か矢印(→)で手順・変化を構造化**し、一目で追えるようにする。Before→After / 原因→対策 を「→」で1〜2箇所
- 最後に、**読み手が自分の経験や質問をコメントしたくなる自然な余白**を1つ残してよい(『ここのTTLどう運用してるか気になる人いたら聞いてください』等)。『どう思いますか?』の定型やいいね/フォロー物乞いはしない

# 口調(本ツイートと完全に揃える)
- 一人称は必ず「自分」(「僕」「俺」NG、複数は「自分たち」)
- 文末は必ず「です・ます」の敬体。常体・タメ口は混ぜない
- 偉ぶらず、手を動かした当事者の温度。煽らない、決めつけない
- 絵文字は基本なし(0〜1個)。ハート/キラキラ/花は禁止

# 出力
- リプ本文だけを返す。『リプ:』等の前置き・引用符・説明は一切なし
- 本ツイートと同じ話題の“続き”として自然に繋がること。本ツイートの文をそのまま繰り返さない"""


def generate_reply(main_text: str, draft: str) -> str:
    """投稿済み本ツイートにぶら下げる『コメ欄の続き』リプ本文を生成する。"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(".env に ANTHROPIC_API_KEY が未設定")
    limit = _max_chars()
    # リプは本文より短く、具体に絞る。長文契約でも詰め込みすぎない。
    reply_cap = min(limit, 600)
    client = Anthropic(api_key=api_key)

    base_user = (
        "以下が今投稿した本ツイートです。これにぶら下げる『具体の続き』リプを1つ書いてください。\n\n"
        f"# 本ツイート\n---\n{main_text}\n---\n\n"
        f"# 元になった自分の素ドラフト(具体の出どころ。ここから手順・設定・回避策を拾ってよい)\n---\n{draft[:1500]}\n---\n\n"
        f"- {reply_cap}文字以内。番号か『→』で手順・変化を構造化して、読んだ人がそのまま試せる具体を渡す\n"
        "- 末尾にコメントしたくなる自然な余白を1つ(任意)"
    )

    last = ""
    for attempt in range(1, 4):
        over = ""
        if attempt > 1:
            over = f"\n# 重要: 前回は{len(last)}文字で{reply_cap}を超えました。今回は必ず{reply_cap}文字以内に。\n"
        res = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=REPLY_SYSTEM,
            messages=[{"role": "user", "content": base_user + over}],
        )
        text = "".join(b.text for b in res.content if b.type == "text").strip()
        last = text
        if text and len(text) <= reply_cap:
            return text
    raise RuntimeError(f"リプ生成が{len(last)}文字>{reply_cap}に収まりませんでした")


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
