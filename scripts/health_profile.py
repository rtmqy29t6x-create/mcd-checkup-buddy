#!/usr/bin/env python3
"""体检指标解析 + 营养约束生成（零第三方依赖）。

输入：用户口述/粘贴的体检指标文本（支持模糊表述与具体数值）。
输出：JSON {"profile": ..., "constraints": ...}

用法：
    python3 health_profile.py "血脂偏高，尿酸 480，血压 145/95，BMI 26.5，轻度脂肪肝"
    echo "血糖偏高" | python3 health_profile.py
"""
import json
import re
import sys

LEVEL_NONE = 0
LEVEL_MILD = 1
LEVEL_HIGH = 2

LEVEL_NAMES = {0: "正常", 1: "偏高", 2: "明显偏高"}

NEGATIVE_WORDS = ("正常", "没事", "阴性", "无恙", "ok", "OK")
MILD_WORDS = ("偏高", "偏高一点", "略高", "稍高", "异常", "超标", "临界", "↑", "有点高")
HIGH_WORDS = ("明显偏高", "很高", "严重", "重度", "高很多", "飙升")

INDICATOR_SPECS = [
    {
        "key": "blood_lipid",
        "name": "血脂/胆固醇",
        "aliases": ["血脂", "胆固醇", "甘油三酯", "低密度脂蛋白", "ldl", "LDL", "总胆固醇"],
        "unit": None,
        "numeric": None,
        "advice": "控制脂肪摄入总量，尤其少吃油炸类餐品。",
    },
    {
        "key": "uric_acid",
        "name": "尿酸",
        "aliases": ["尿酸"],
        "unit": "μmol/L",
        "numeric": {"pattern": r"尿酸[^\d]{0,4}(\d{3}(?:\.\d+)?)", "mild": 420, "high": 480},
        "advice": "控制蛋白质总量，红肉海鲜适量，少喝含糖饮料（果糖会影响尿酸代谢）。",
    },
    {
        "key": "blood_glucose",
        "name": "血糖/糖化血红蛋白",
        "aliases": ["糖化血红蛋白", "糖化", "血糖", "空腹血糖", "HbA1c", "hba1c"],
        "unit": "mmol/L 或 %",
        "numeric": {"pattern": r"(?:血糖|糖化(?:血红蛋白)?)[^\d]{0,4}(\d+(?:\.\d+)?)", "mild": 6.0, "high": 7.0},
        "advice": "控制碳水化合物总量，含糖饮料和甜点先放一放。",
    },
    {
        "key": "blood_pressure",
        "name": "血压",
        "aliases": ["血压"],
        "unit": "mmHg",
        "numeric": None,
        "advice": "控盐控钠，点餐时优先选钠含量低的组合。",
    },
    {
        "key": "bmi",
        "name": "BMI",
        "aliases": ["BMI", "bmi", "体重指数"],
        "unit": "kg/m²",
        "numeric": {"pattern": r"(?:BMI|bmi|体重指数)[^\d]{0,4}(\d+(?:\.\d+)?)", "mild": 24, "high": 28},
        "advice": "控制单餐总能量，先管住份量再谈快乐。",
    },
    {
        "key": "fatty_liver",
        "name": "脂肪肝",
        "aliases": ["脂肪肝"],
        "unit": None,
        "numeric": None,
        "advice": "脂肪和总能量都要收一收，油炸类先说再见。",
    },
]

BP_PATTERN = re.compile(r"(?:血压)?[^\d]{0,4}(1\d{2}|2\d{2})\s*[/／]\s*(\d{2,3})")


def _find_level_by_words(text, alias_span):
    """在指标别名之后的文本里判断严重程度（避免吞掉前一个指标的修饰词）。"""
    window = text[alias_span[0]: alias_span[1] + 12]
    for w in NEGATIVE_WORDS:
        if w in window:
            return LEVEL_NONE
    for w in HIGH_WORDS:
        if w in window:
            return LEVEL_HIGH
    for w in MILD_WORDS:
        if w in window:
            return LEVEL_MILD
    return None


def _numeric_level(value, mild, high):
    if value >= high:
        return LEVEL_HIGH
    if value >= mild:
        return LEVEL_MILD
    return LEVEL_NONE


def parse_indicators(text):
    """把自由文本解析成结构化体检指标 profile。"""
    profile = {"raw_input": text, "indicators": []}
    for spec in INDICATOR_SPECS:
        span = None
        for alias in spec["aliases"]:
            idx = text.find(alias)
            if idx >= 0:
                span = (idx, idx + len(alias))
                break
        if span is None:
            continue

        level = None
        value = None
        if spec["key"] == "blood_pressure":
            m = BP_PATTERN.search(text)
            if m:
                sys_p, dia_p = int(m.group(1)), int(m.group(2))
                value = "%d/%d" % (sys_p, dia_p)
                level = _numeric_level(max(sys_p, dia_p * 1.6), 140, 160)
        elif spec["numeric"]:
            m = re.search(spec["numeric"]["pattern"], text)
            if m:
                value = float(m.group(1))
                level = _numeric_level(value, spec["numeric"]["mild"], spec["numeric"]["high"])
        elif spec["key"] == "fatty_liver":
            if "重度" in text or "中度" in text:
                level = LEVEL_HIGH
            elif "轻度" in text:
                level = LEVEL_MILD

        if level is None:
            level = _find_level_by_words(text, span)
        if level is None:
            level = LEVEL_MILD

        profile["indicators"].append({
            "key": spec["key"],
            "name": spec["name"],
            "value": value,
            "unit": spec["unit"],
            "level": level,
            "level_name": LEVEL_NAMES[level],
            "advice": spec["advice"],
        })
    return profile


def build_constraints(profile):
    """指标 → 单餐营养约束（六维预算 + 硬规避/软提醒标签）。

    预算是"单餐"口径：假设一日三餐，取常见膳食参考量的约 1/3，
    再按异常指标收紧。多项指标同时异常时取最严值。
    """
    constraints = {
        "energy_kcal_max": 700,
        "fat_g_max": 25,
        "carb_g_max": 80,
        "sodium_mg_max": 800,
        "protein_g_max": 45,
        "hard_avoid_tags": [],
        "caution_tags": [],
        "notes": [],
    }
    hard, caution = set(), set()

    def tighten(field, value):
        if value is not None:
            constraints[field] = min(constraints[field], value)

    for ind in profile.get("indicators", []):
        if ind["level"] == LEVEL_NONE:
            continue
        key, lv = ind["key"], ind["level"]
        if key == "blood_lipid":
            tighten("fat_g_max", 15 if lv == 1 else 12)
            (caution if lv == 1 else hard).add("油炸")
            constraints["notes"].append(ind["advice"])
        elif key == "uric_acid":
            tighten("protein_g_max", 30 if lv == 1 else 24)
            caution.update(["红肉", "海鲜"])
            (caution if lv == 1 else hard).add("含糖饮料")
            constraints["notes"].append(ind["advice"] + "（MCP 营养数据不含嘌呤维度，红肉/海鲜按人工规则给出提醒，仅供参考。）")
        elif key == "blood_glucose":
            tighten("carb_g_max", 45 if lv == 1 else 38)
            hard.add("含糖饮料")
            (caution if lv == 1 else hard).add("甜点")
            constraints["notes"].append(ind["advice"])
        elif key == "blood_pressure":
            tighten("sodium_mg_max", 650 if lv == 1 else 550)
            constraints["notes"].append(ind["advice"])
        elif key == "bmi":
            tighten("energy_kcal_max", 500 if lv == 1 else 420)
            (caution if lv == 1 else hard).add("油炸")
            constraints["notes"].append(ind["advice"])
        elif key == "fatty_liver":
            tighten("fat_g_max", 14 if lv == 1 else 11)
            tighten("energy_kcal_max", 550 if lv == 1 else 500)
            (caution if lv == 1 else hard).add("油炸")
            constraints["notes"].append(ind["advice"])

    constraints["hard_avoid_tags"] = sorted(hard)
    constraints["caution_tags"] = sorted(caution - hard)
    return constraints


def main():
    text = " ".join(sys.argv[1:]).strip() or sys.stdin.read().strip()
    if not text:
        print("用法: python3 health_profile.py \"血脂偏高，尿酸 480\"", file=sys.stderr)
        sys.exit(2)
    profile = parse_indicators(text)
    constraints = build_constraints(profile)
    print(json.dumps({"profile": profile, "constraints": constraints},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
