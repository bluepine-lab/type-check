#!/usr/bin/env python3
"""タイプ診断スキルの採点スクリプト(Python標準ライブラリのみ)。

  python typecheck.py questions [--part 1..4]       質問(24問。--partで軸ごとの6問)
  python typecheck.py score 回答24桁 [--save]       採点(回答は1〜5の数字を24個。例: 435124…)
  python typecheck.py type INFP                     16タイプのうち1つの説明
  python typecheck.py last                          保存した前回までの結果
  python typecheck.py check                         自己点検

これは医療・心理の診断ではなく、自己理解のきっかけにする読み物です。公式の性格検査(MBTI等)とは別物です。
採点と説明はこのスクリプトが行い、文章(読み解き)は呼び出し側のAIが書く。
保存先は ~/.claude/タイプ診断/results.json(環境変数 TYPE_HOME で変更可)。保存するのは軸の点数と日付だけ。
"""
import argparse
import datetime
import json
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
AXES = [("EI", "E", "I", "外向", "内向", "エネルギーの向き"),
        ("SN", "S", "N", "現実", "直感", "情報の受け取り方"),
        ("TF", "T", "F", "思考", "感情", "決め方"),
        ("JP", "J", "P", "計画", "柔軟", "暮らし方")]
MAX_SCORE = 12     # 1軸6問 × 最大±2
BORDER = 2         # 点数がこの値以内なら「境界(どちらにも寄る)」


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return json.load(f)


def home_dir():
    base = os.environ.get("TYPE_HOME")
    return Path(base) if base else Path.home() / ".claude" / "タイプ診断"


def results_path():
    return home_dir() / "results.json"


def load_results():
    p = results_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def score(answers):
    """回答(1〜5の整数24個)→各軸の結果。"""
    qs = load("questions.json")
    if len(answers) != len(qs):
        raise ValueError("回答は%d個必要です(受け取った数: %d)" % (len(qs), len(answers)))
    if any(a < 1 or a > 5 for a in answers):
        raise ValueError("回答は1〜5の数字で入力してください")
    axes, code, pending = [], "", []
    for key, first, second, name1, name2, label in AXES:
        s = 0
        for q, a in zip(qs, answers):
            if q["軸"] == key:
                s += (a - 3) * (1 if q["向き"] == first else -1)
        if s > 0:
            letter, name = first, name1
        elif s < 0:
            letter, name = second, name2
        else:
            letter, name = None, None
            pending.append(key)
        strength = 50 + round(50 * abs(s) / MAX_SCORE)
        axes.append({"軸": label, "点数": s, "寄り": name or "どちらとも言えない",
                     "強さ%": strength if letter else 50, "境界": abs(s) <= BORDER,
                     "文字": letter or "?"})
        code += letter or "?"
    res = {"タイプ": code, "軸": axes}
    if pending:
        res["保留"] = "同点の軸があるため、タイプは確定しません。「?」の軸はどちらに近いか、本人に選んでもらってください"
    else:
        res["説明"] = describe(code)
    borders = [a["軸"] for a in axes if a["境界"] and a["文字"] != "?"]
    if borders:
        res["境界の軸"] = borders
    return res


def describe(code):
    types = load("types.json")
    if code not in types:
        raise ValueError("そのタイプはありません: %s(例: INFP)" % code)
    d = dict(types[code])
    d["タイプ"] = code
    d["名言テーマ注"] = "つまずきやすい所に合う名言のテーマ(名言スキルの --theme に使える)"
    return d


def cmd_questions(args):
    qs = load("questions.json")
    if args.part:
        key = AXES[args.part - 1][0]
        qs = [q for q in qs if q["軸"] == key]
    return {"回答の目安": "1=まったく当てはまらない 2=あまり 3=どちらとも 4=やや 5=とても当てはまる",
            "質問": [{"番号": q["id"], "文": q["文"]} for q in qs]}


def cmd_score(args):
    digits = [c for c in args.回答 if c.isdigit()]
    res = score([int(c) for c in digits])
    if args.save:
        items = load_results()
        entry = {"日付": datetime.date.today().isoformat(), "タイプ": res["タイプ"],
                 "点数": {a["軸"]: a["点数"] for a in res["軸"]}}
        prev = items[-1] if items else None
        items.append(entry)
        p = results_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        res["保存"] = True
        res["次に受け直す目安"] = (datetime.date.today() + datetime.timedelta(days=90)).isoformat()
        if prev:
            res["前回"] = prev
    return res


def cmd_type(args):
    return describe(args.code.upper())


def cmd_last(args):
    items = load_results()
    return {"件数": len(items), "結果": items[-5:]}


def cmd_check(args):
    qs, types = load("questions.json"), load("types.json")
    ok = True

    def t(good, label):
        nonlocal ok
        print(("OK  " if good else "NG  ") + label)
        ok = ok and good

    t(len(qs) == 24 and len({q["id"] for q in qs}) == 24, "質問は24問・番号が重複しない")
    t(all(sum(1 for q in qs if q["軸"] == k and q["向き"] == f) == 3 for k, f, s, *_ in AXES for f in (f, s)),
      "各軸・各極の質問が3問ずつ")
    t(len(types) == 16 and all(len(c) == 4 for c in types), "16タイプが揃っている")
    need = {"愛称", "強み", "つまずき", "人との関わり", "伸ばすヒント", "名言テーマ"}
    themes = {"学び", "継続", "失敗", "人間関係", "決断", "休息", "時間", "仕事"}
    t(all(set(v["名言テーマ"]) <= themes and v["名言テーマ"] for v in types.values()), "名言テーマが名言スキルのテーマ一覧に収まる")
    t(all(need <= set(v) for v in types.values()), "全タイプに説明の必須項目がある")
    # 全部「5」と答えると、各極6問のうち向きが半々なので0点=保留になる
    t(score([3] * 24)["タイプ"] == "????" and "保留" in score([3] * 24), "全部3は保留になる")
    # 内向・直感・感情・柔軟 の質問にだけ5、反対に1を付けると INFP になる
    towards = {"I", "N", "F", "P"}
    ans = [5 if q["向き"] in towards else 1 for q in qs]
    r = score(ans)
    t(r["タイプ"] == "INFP" and all(a["強さ%"] == 100 for a in r["軸"]), "INFP側に振り切ると INFP・強さ100%")
    ans = [1 if q["向き"] in towards else 5 for q in qs]
    t(score(ans)["タイプ"] == "ESTJ", "反対に振り切ると ESTJ")
    t(score([3] * 23 + [5])["タイプ"] != "", "1問だけ偏ってもエラーにならない")
    sys.exit(0 if ok else 1)



# --- ページ(HTML)の書き出し(形だけの初版。見た目の磨きは後日) ---
def _page_escape(x):
    import html
    return html.escape(str(x))


def render_page(data, skill_name, tpl_path):
    """AIが組み立てた内容(JSON)をHTMLページにする。
    内容の形: {"日付": "…", "副題": "…", "一言": "…", "注記": "…",
              "節": [{"題": "…", "行": [["題","文"],…]} | {"題": "…", "本文": "…"} | {"題": "…", "棒": [["名","値の文",0〜100],…]}]}"""
    e = _page_escape
    secs = []
    for s in data.get("節", []):
        body = ""
        if s.get("行"):
            body += '<dl class="rows">%s</dl>' % "".join(
                '<div class="row"><dt>%s</dt><span class="leader"></span><dd>%s</dd></div>' % (e(a), e(b)) for a, b in s["行"])
        if s.get("本文"):
            body += "".join('<p class="para">%s</p>' % e(p) for p in str(s["本文"]).split("\n") if p.strip())
        if s.get("棒"):
            body += '<ul class="bars">%s</ul>' % "".join(
                '<li class="bar"><span>%s</span><span class="track"><span class="fill" style="width:%d%%"></span></span><span class="val">%s</span></li>'
                % (e(n), max(0, min(100, int(v))), e(t)) for n, t, v in s["棒"])
        secs.append('<section class="sec"><h2>%s</h2>%s</section>' % (e(s.get("題", "")), body))
    with open(tpl_path, encoding="utf-8") as f:
        tpl = f.read()
    vals = {"日付": e(data.get("日付", "")),
            "副題": ('<p class="sub">%s</p>' % e(data["副題"])) if data.get("副題") else "",
            "一言": ('<p class="lead">%s</p>' % e(data["一言"])) if data.get("一言") else "",
            "節": "\n  ".join(secs),
            "注記": ('<p class="note">%s</p>' % e(data["注記"])) if data.get("注記") else ""}
    for k, v in vals.items():
        tpl = tpl.replace("{{%s}}" % k, v)
    return tpl


def cmd_page(args):
    import json as _json
    from pathlib import Path as _Path
    here = _Path(os.path.dirname(os.path.abspath(__file__)))
    data = _json.loads(_Path(args.データ).read_text(encoding="utf-8"))
    _Path(args.out).write_text(render_page(data, "タイプ診断", str(here / "page.html")), encoding="utf-8")
    return {"書き出し": args.out}


def main():
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    _pg = sub.add_parser("page", help="内容(JSON)をHTMLページ(Artifact用)に書き出す")
    _pg.add_argument("--データ", required=True, help="あなた(AI)が組み立てた内容のJSONファイル")
    _pg.add_argument("--out", required=True, help="書き出すHTMLのパス")
    _pg.set_defaults(fn=cmd_page)
    p = sub.add_parser("questions")
    p.add_argument("--part", type=int, choices=[1, 2, 3, 4])
    p.set_defaults(fn=cmd_questions)
    p = sub.add_parser("score")
    p.add_argument("回答")
    p.add_argument("--save", action="store_true")
    p.set_defaults(fn=cmd_score)
    p = sub.add_parser("type")
    p.add_argument("code")
    p.set_defaults(fn=cmd_type)
    p = sub.add_parser("last")
    p.set_defaults(fn=cmd_last)
    p = sub.add_parser("check")
    p.set_defaults(fn=cmd_check)
    args = ap.parse_args()
    try:
        print(json.dumps(args.fn(args), ensure_ascii=False, indent=2))
    except ValueError as e:
        print(json.dumps({"エラー": str(e)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
