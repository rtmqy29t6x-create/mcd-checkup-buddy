#!/usr/bin/env python3
"""生成「体检风」HTML 分享报告卡（零第三方依赖）。

用法：
    python3 report_card.py --profile p.json --classified c.json --out report.html
p.json 为 health_profile.py 的完整输出；c.json 为 classify_foods.py 的完整输出。
"""
import argparse
import datetime
import html
import json
import sys

DIM_LABELS = [
    ("energy_kcal_max", "能量", "kcal"),
    ("protein_g_max", "蛋白质", "g"),
    ("fat_g_max", "脂肪", "g"),
    ("carb_g_max", "碳水化合物", "g"),
    ("sodium_mg_max", "钠", "mg"),
]

TIER_EMOJI = {"green": "🟢", "yellow": "🟡", "red": "🔴"}

DOCTOR_ORDERS = [
    "薯条可以吃，但盐包先别撕，快乐留一手。",
    "含糖饮料这季度先停诊，零糖饮品转正当替班。",
    "汉堡不是不能吃，是要挑着吃——报告卡就是你的处方笺。",
    "每周复查一次本报告，指标好了，白名单自动扩容。",
]


def _esc(s):
    return html.escape(str(s), quote=True)


def _indicator_rows(profile):
    rows = []
    for ind in profile.get("indicators", []):
        value = _esc(ind["value"]) if ind.get("value") is not None else "—"
        unit = _esc(ind.get("unit") or "")
        flag = "▲" if ind["level"] == 1 else ("▲▲" if ind["level"] == 2 else "正常")
        rows.append(
            "<tr><td>%s</td><td>%s %s</td><td class=\"%s\">%s</td><td>%s</td></tr>" % (
                _esc(ind["name"]), value, unit,
                "abnormal" if ind["level"] else "normal",
                flag, _esc(ind["advice"]),
            )
        )
    return "\n".join(rows) or "<tr><td colspan=\"4\">未录入指标</td></tr>"


def _constraint_rows(constraints):
    rows = []
    for field, label, unit in DIM_LABELS:
        value = constraints.get(field)
        rows.append("<tr><td>%s</td><td>≤ %s %s / 餐</td></tr>" % (
            label, _esc(value if value is not None else "不限"), unit))
    return "\n".join(rows)


def _tier_block(classified, tier, title):
    items = [c for c in classified["items"] if c["tier"] == tier]
    if not items:
        return ""
    lis = "\n".join(
        "<li><b>%s</b><span class=\"cat\">%s</span><span class=\"why\">%s</span></li>" % (
            _esc(c["name"]), _esc(c["category"]), _esc("；".join(c["reasons"]) or "各维度均在预算内"))
        for c in items)
    return "<section class=\"tier tier-%s\"><h3>%s %s（%d 项）</h3><ul>%s</ul></section>" % (
        tier, TIER_EMOJI[tier], title, len(items), lis)


def _combo_block(classified):
    combos = classified.get("combos", [])
    if not combos:
        return "<p>当前约束下没有组合出完全达标的套餐，建议从「放心吃」里单点主食 + 零糖饮品。</p>"
    cards = []
    for i, combo in enumerate(combos, 1):
        n = combo["nutrition"]
        cards.append(
            "<div class=\"combo\"><h4>方案 %d</h4><p class=\"items\">%s</p>"
            "<p class=\"nums\">能量 %.0f kcal · 蛋白质 %.0f g · 脂肪 %.0f g · 碳水 %.0f g · 钠 %.0f mg</p></div>" % (
                i, _esc(" + ".join(combo["items"])),
                n["energy_kcal"], n["protein_g"], n["fat_g"], n["carb_g"], n["sodium_mg"]))
    return "\n".join(cards)


def render_html(profile, constraints, classified, source_note, generated_at=None):
    generated_at = generated_at or datetime.date.today().isoformat()
    notes = "\n".join("<li>%s</li>" % _esc(n) for n in constraints.get("notes", []))
    orders = "\n".join("<li>%s</li>" % _esc(o) for o in DOCTOR_ORDERS)
    s = classified["summary"]
    template = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>麦门体检报告卡</title>
<style>
:root { --red:#c8102e; --yellow:#ffc72c; --ink:#222; --line:#d8d2c4; }
* { box-sizing:border-box; margin:0; padding:0; }
body { background:#f4efe6; font-family:"Songti SC","Noto Serif SC",serif; color:var(--ink); padding:24px; }
.card { max-width:760px; margin:0 auto; background:#fffdf8; border:2px solid var(--ink); box-shadow:8px 8px 0 var(--yellow); }
header { border-bottom:2px solid var(--ink); padding:20px 24px; display:flex; justify-content:space-between; align-items:baseline; }
header h1 { font-size:26px; letter-spacing:2px; }
header .no { font-size:12px; color:#777; }
.meta { padding:12px 24px; border-bottom:1px dashed var(--line); font-size:13px; color:#555; display:flex; gap:24px; flex-wrap:wrap; }
section { padding:18px 24px; border-bottom:1px dashed var(--line); }
h2 { font-size:17px; margin-bottom:10px; padding-left:10px; border-left:6px solid var(--red); }
table { width:100%; border-collapse:collapse; font-size:13px; }
th, td { border:1px solid var(--line); padding:6px 8px; text-align:left; }
th { background:#faf5e8; }
.abnormal { color:var(--red); font-weight:bold; }
.normal { color:#2e7d32; }
.tier h3 { font-size:15px; margin-bottom:8px; }
.tier ul { list-style:none; }
.tier li { padding:6px 0; border-bottom:1px dotted var(--line); font-size:13px; }
.tier .cat { color:#888; font-size:12px; margin-left:8px; }
.tier .why { display:block; color:#777; font-size:12px; margin-top:2px; }
.combo { border:1px solid var(--line); background:#fff; padding:10px 12px; margin-bottom:10px; }
.combo h4 { color:var(--red); margin-bottom:4px; }
.combo .nums { font-size:12px; color:#666; margin-top:4px; }
.orders li, .notes li { font-size:13px; margin:6px 0 6px 18px; }
footer { padding:16px 24px; font-size:12px; color:#888; line-height:1.7; }
.stamp { display:inline-block; border:2px solid var(--red); color:var(--red); border-radius:6px; padding:2px 10px; font-size:12px; transform:rotate(-6deg); margin-top:8px; }
</style>
</head>
<body>
<div class="card">
<header><h1>麦门体检报告卡</h1><span class="no">编号 MCD-CHECKUP-__DATE__</span></header>
<div class="meta"><span>体检人：亲爱的程序员</span><span>报告日期：__DATE__</span><span>数据来源：__SOURCE__</span></div>
<section><h2>一、本次录入指标</h2><table><thead><tr><th>指标</th><th>结果</th><th>提示</th><th>麦门医嘱</th></tr></thead><tbody>
__INDICATOR_ROWS__
</tbody></table></section>
<section><h2>二、营养处方（单餐预算）</h2><table><thead><tr><th>维度</th><th>上限</th></tr></thead><tbody>
__CONSTRAINT_ROWS__
</tbody></table><ul class="notes">__NOTES__</ul></section>
__TIER_BLOCKS__
<section><h2>五、推荐套餐组合</h2>__COMBO_BLOCK__</section>
<section><h2>六、医嘱</h2><ul class="orders">__ORDERS__</ul><span class="stamp">已阅 · 麦门体检中心</span></section>
<footer>
本报告由「麦门体检搭子」生成，仅供娱乐与点餐参考，<b>不构成医疗、营养或其他专业建议</b>；具体诊疗请遵医嘱。
餐品营养信息以麦当劳官方渠道实时数据为准。麦当劳 MCP 营养数据仅含能量/蛋白质/脂肪/碳水/钠/钙六维，
嘌呤等维度未覆盖，相关提醒基于人工整理的规则，存在边界，请知悉。
</footer>
</div>
</body>
</html>
"""
    replacements = {
        "__DATE__": _esc(generated_at),
        "__SOURCE__": _esc(source_note),
        "__INDICATOR_ROWS__": _indicator_rows(profile),
        "__CONSTRAINT_ROWS__": _constraint_rows(constraints),
        "__NOTES__": notes,
        "__TIER_BLOCKS__": (
            "<section><h2>三、麦门白名单分档（共 %d 项）</h2></section>" % sum(s.values())
            + _tier_block(classified, "green", "放心吃")
            + _tier_block(classified, "yellow", "少吃")
            + _tier_block(classified, "red", "别碰")
        ),
        "__COMBO_BLOCK__": _combo_block(classified),
        "__ORDERS__": orders,
    }
    for token, value in replacements.items():
        template = template.replace(token, value)
    return template


def write_report(path, profile, constraints, classified, source_note):
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_html(profile, constraints, classified, source_note))
    return path


def main():
    parser = argparse.ArgumentParser(description="生成体检风 HTML 报告卡")
    parser.add_argument("--profile", required=True, help="health_profile.py 输出 JSON")
    parser.add_argument("--classified", required=True, help="classify_foods.py 输出 JSON")
    parser.add_argument("--out", default="mcd-checkup-report.html", help="输出 HTML 路径")
    parser.add_argument("--source", default="内置样例数据（dry-run）", help="数据来源说明")
    args = parser.parse_args()

    with open(args.profile, encoding="utf-8") as f:
        p = json.load(f)
    with open(args.classified, encoding="utf-8") as f:
        c = json.load(f)
    write_report(args.out, p["profile"], p["constraints"], c, args.source)
    print("报告已生成: %s" % args.out)


if __name__ == "__main__":
    sys.exit(main())
