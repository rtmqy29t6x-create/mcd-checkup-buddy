#!/usr/bin/env python3
"""餐品三档分类 + 推荐套餐组合求解（零第三方依赖）。

输入：餐品营养 JSON（list-nutrition-foods 返回结构或样例数据）+ 约束 JSON。
输出：{"items": [...三档分类...], "combos": [...推荐套餐...], "summary": {...}}

用法：
    python3 classify_foods.py --constraints c.json --foods foods.json
    python3 classify_foods.py --constraints c.json            # 不传 --foods 时用内置样例
"""
import argparse
import json
import os
import sys

DIMENSIONS = [
    ("energy_kcal", "energy_kcal_max", "能量"),
    ("fat_g", "fat_g_max", "脂肪"),
    ("carb_g", "carb_g_max", "碳水化合物"),
    ("sodium_mg", "sodium_mg_max", "钠"),
    ("protein_g", "protein_g_max", "蛋白质"),
]

TAG_RULES = [
    ("含糖饮料", ("饮品",), ("可乐", "雪碧", "芬达", "奶茶", "奶昔", "柠檬", "果汁",
                             "苹果汁", "橙汁", "美汁源", "怡泉", "朱古力", "雪冰",
                             "玛奇朵", "麦旋酷", "黑巧", "抹茶牛奶")),
    ("油炸", None, ("麦乐鸡", "辣鸡", "鸡排", "鸡扒", "薯条", "薯饼", "油条", "脆薯",
                    "香骨鸡", "派", "脆汁鸡", "V翅", "趣鸡球", "翅")),
    ("红肉", ("汉堡", "早餐", "小食", "主食"), ("牛", "巨无霸", "吉士", "培根", "猪柳",
                                            "安格斯", "烟肉", "火腿", "香肠")),
    ("海鲜", None, ("鱼", "虾", "鳕鱼")),
    ("甜点", ("甜点",), ("麦旋风", "新地", "圆筒", "冰淇淋", "派", "拉明顿", "奶冻",
                        "爆珠", "阿芙佳朵")),
]
ZERO_SUGAR_HINTS = ("零度", "无糖", "纤维+")

TIER_GREEN = "green"
TIER_YELLOW = "yellow"
TIER_RED = "red"
TIER_NAMES = {"green": "放心吃", "yellow": "少吃", "red": "别碰"}

MAIN_CATEGORIES = ("汉堡", "早餐", "主食")
DRINK_CATEGORY = "饮品"
CAUTION_RATIO = 0.55


def derive_tags(item):
    """按餐品名称与分类做规则化标签推断（MCP 数据无嘌呤等维度，靠规则补齐）。"""
    name = item.get("name", "")
    category = item.get("category", "")
    tags = set()
    for tag, categories, keywords in TAG_RULES:
        if categories and category not in categories:
            continue
        if any(k in name for k in keywords):
            tags.add(tag)
    if "含糖饮料" in tags and any(k in name for k in ZERO_SUGAR_HINTS):
        tags.discard("含糖饮料")
        tags.add("零糖饮品")
    return sorted(tags)


def classify_item(item, constraints):
    """单项餐品 → 三档结论 + 理由。"""
    tags = derive_tags(item)
    hard = set(constraints.get("hard_avoid_tags", []))
    caution = set(constraints.get("caution_tags", []))
    reasons = []
    tier = TIER_GREEN

    hit_hard = sorted(hard & set(tags))
    if hit_hard:
        tier = TIER_RED
        reasons.append("命中硬规避类别：%s" % "、".join(hit_hard))

    for field, cap_field, label in DIMENSIONS:
        cap = constraints.get(cap_field)
        value = item.get(field)
        if cap is None or value is None:
            continue
        if value > cap:
            if tier != TIER_RED:
                tier = TIER_RED
            reasons.append("%s %.0f 超过单餐预算 %.0f" % (label, value, cap))
        elif value > cap * CAUTION_RATIO:
            if tier == TIER_GREEN:
                tier = TIER_YELLOW
            reasons.append("%s %.0f 占单餐预算 %.0f%%" % (label, value, value / cap * 100))

    hit_caution = sorted(caution & set(tags))
    if hit_caution:
        if tier == TIER_GREEN:
            tier = TIER_YELLOW
        reasons.append("需留意类别：%s" % "、".join(hit_caution))

    return {
        "name": item.get("name", ""),
        "category": item.get("category", ""),
        "tier": tier,
        "tier_name": TIER_NAMES[tier],
        "tags": tags,
        "reasons": reasons,
        "nutrition": {f: item.get(f) for f, _, _ in DIMENSIONS} | {"calcium_mg": item.get("calcium_mg")},
    }


def _combo_totals(items):
    totals = {f: 0 for f, _, _ in DIMENSIONS}
    totals["calcium_mg"] = 0
    for it in items:
        for f in totals:
            totals[f] += it.get(f) or 0
    return totals


def _fits_budget(totals, constraints):
    for field, cap_field, _ in DIMENSIONS:
        cap = constraints.get(cap_field)
        if cap is not None and totals[field] > cap:
            return False
    return True


def _combo_score(totals, constraints, yellow_count):
    protein = totals["protein_g"]
    satiety = protein * 2 + totals["calcium_mg"] * 0.05
    sodium_ratio = totals["sodium_mg"] / max(constraints.get("sodium_mg_max") or 1, 1)
    energy_ratio = totals["energy_kcal"] / max(constraints.get("energy_kcal_max") or 1, 1)
    return satiety - (sodium_ratio + energy_ratio) * 15 - yellow_count * 8


def build_combos(classified, constraints, top_n=3, with_side=True):
    """组合 主食+饮品(+小食)：排除「别碰」，总量须全部满足预算，「放心吃」优先。"""
    ok = [c for c in classified if c["tier"] != TIER_RED]
    lookup = {c["name"]: c for c in ok}

    def originals(names):
        return [lookup[n] for n in names]

    mains = [c["name"] for c in ok if c["category"] in MAIN_CATEGORIES]
    drinks = [c["name"] for c in ok if c["category"] == DRINK_CATEGORY]
    sides = [c["name"] for c in ok if c["category"] not in MAIN_CATEGORIES + (DRINK_CATEGORY,)]

    combos = []
    seen = set()
    for main in mains:
        for drink in drinks:
            base = [main, drink]
            candidates = [base]
            if with_side:
                candidates += [base + [s] for s in sides]
            for names in candidates:
                key = tuple(sorted(names))
                if key in seen:
                    continue
                seen.add(key)
                members = originals(names)
                nutrition = {}
                for c in members:
                    for f, v in c["nutrition"].items():
                        nutrition[f] = nutrition.get(f, 0) + (v or 0)
                if not _fits_budget(nutrition, constraints):
                    continue
                yellow_count = sum(1 for c in members if c["tier"] == TIER_YELLOW)
                combos.append({
                    "items": names,
                    "nutrition": nutrition,
                    "score": round(_combo_score(nutrition, constraints, yellow_count), 2),
                })
    combos.sort(key=lambda c: c["score"], reverse=True)
    return combos[:top_n]


def classify_all(foods, constraints):
    classified = [classify_item(item, constraints) for item in foods]
    order = {TIER_GREEN: 0, TIER_YELLOW: 1, TIER_RED: 2}
    classified.sort(key=lambda c: (order[c["tier"]], c["category"], c["name"]))
    summary = {TIER_NAMES[t]: sum(1 for c in classified if c["tier"] == t)
               for t in (TIER_GREEN, TIER_YELLOW, TIER_RED)}
    return {
        "items": classified,
        "combos": build_combos(classified, constraints),
        "summary": summary,
    }


def load_foods(path=None):
    """加载餐品数据：支持裸数组或 {\"foods\": [...]} 包装（如真实数据快照）。"""
    if path is None:
        default = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "nutrition_snapshot.json")
        path = default if os.path.exists(default) else None
    if path is None:
        from sample_data import SAMPLE_FOODS
        return SAMPLE_FOODS, "内置样例数据（dry-run）"
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if isinstance(payload, dict):
        source = payload.get("meta", {}).get("source", path)
        return payload["foods"], source
    return payload, path


def main():
    parser = argparse.ArgumentParser(description="麦门体检搭子：餐品三档分类求解")
    parser.add_argument("--constraints", required=True, help="约束 JSON 文件路径（health_profile.py 输出中的 constraints 段）")
    parser.add_argument("--foods", help="餐品营养 JSON 文件路径；省略时优先用真实数据快照，其次内置样例")
    args = parser.parse_args()

    with open(args.constraints, encoding="utf-8") as f:
        payload = json.load(f)
    constraints = payload.get("constraints", payload)

    foods, _ = load_foods(args.foods)
    print(json.dumps(classify_all(foods, constraints), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
