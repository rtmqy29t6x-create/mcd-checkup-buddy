import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from health_profile import (
    LEVEL_HIGH,
    LEVEL_MILD,
    LEVEL_NONE,
    build_constraints,
    parse_indicators,
)
from classify_foods import (
    TIER_GREEN,
    TIER_RED,
    TIER_YELLOW,
    build_combos,
    classify_all,
    classify_item,
    derive_tags,
)
from sample_data import SAMPLE_FOODS
from parse_nutrition import infer_category, parse_mcp_data
from classify_foods import load_foods
from report_card import render_html, write_report
from run_demo import run

SNAPSHOT_PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "nutrition_snapshot.json")


def load_snapshot():
    with open(SNAPSHOT_PATH, encoding="utf-8") as f:
        return json.load(f)


def indicator(profile, key):
    for ind in profile["indicators"]:
        if ind["key"] == key:
            return ind
    return None


class TestParseIndicators(unittest.TestCase):
    def test_fuzzy_words(self):
        p = parse_indicators("血脂偏高，血糖有点高")
        self.assertEqual(indicator(p, "blood_lipid")["level"], LEVEL_MILD)
        self.assertEqual(indicator(p, "blood_glucose")["level"], LEVEL_MILD)

    def test_negative_word(self):
        p = parse_indicators("血糖正常，血压偏高")
        self.assertEqual(indicator(p, "blood_glucose")["level"], LEVEL_NONE)
        self.assertEqual(indicator(p, "blood_pressure")["level"], LEVEL_MILD)

    def test_numeric_uric_acid(self):
        p = parse_indicators("尿酸 480")
        ind = indicator(p, "uric_acid")
        self.assertEqual(ind["value"], 480.0)
        self.assertEqual(ind["level"], LEVEL_HIGH)

    def test_numeric_uric_acid_borderline(self):
        p = parse_indicators("尿酸 430")
        self.assertEqual(indicator(p, "uric_acid")["level"], LEVEL_MILD)

    def test_blood_pressure_pair(self):
        p = parse_indicators("血压 145/95")
        ind = indicator(p, "blood_pressure")
        self.assertEqual(ind["value"], "145/95")
        self.assertEqual(ind["level"], LEVEL_MILD)

    def test_blood_pressure_high(self):
        p = parse_indicators("血压 165/105")
        self.assertEqual(indicator(p, "blood_pressure")["level"], LEVEL_HIGH)

    def test_bmi_levels(self):
        self.assertEqual(indicator(parse_indicators("BMI 26.5"), "bmi")["level"], LEVEL_MILD)
        self.assertEqual(indicator(parse_indicators("BMI 29"), "bmi")["level"], LEVEL_HIGH)

    def test_fatty_liver_degree(self):
        self.assertEqual(indicator(parse_indicators("轻度脂肪肝"), "fatty_liver")["level"], LEVEL_MILD)
        self.assertEqual(indicator(parse_indicators("中度脂肪肝"), "fatty_liver")["level"], LEVEL_HIGH)

    def test_mentioned_without_words_defaults_mild(self):
        p = parse_indicators("体检查出胆固醇")
        self.assertEqual(indicator(p, "blood_lipid")["level"], LEVEL_MILD)

    def test_unmentioned_absent(self):
        p = parse_indicators("尿酸偏高")
        self.assertIsNone(indicator(p, "bmi"))


class TestBuildConstraints(unittest.TestCase):
    def test_blood_pressure_tightens_sodium(self):
        c = build_constraints(parse_indicators("血压 145/95"))
        self.assertEqual(c["sodium_mg_max"], 650)

    def test_multiple_indicators_take_min(self):
        c = build_constraints(parse_indicators("血脂明显偏高，中度脂肪肝"))
        self.assertEqual(c["fat_g_max"], 11)

    def test_glucose_hard_avoids_sugary_drinks(self):
        c = build_constraints(parse_indicators("血糖偏高"))
        self.assertIn("含糖饮料", c["hard_avoid_tags"])
        self.assertEqual(c["carb_g_max"], 45)

    def test_uric_acid_protein_cap_and_purine_caution(self):
        c = build_constraints(parse_indicators("尿酸 500"))
        self.assertEqual(c["protein_g_max"], 24)
        self.assertIn("红肉", c["caution_tags"])
        self.assertIn("含糖饮料", c["hard_avoid_tags"])

    def test_normal_indicator_keeps_defaults(self):
        c = build_constraints(parse_indicators("血糖正常"))
        self.assertEqual(c["carb_g_max"], 80)
        self.assertEqual(c["hard_avoid_tags"], [])

    def test_bmi_energy_cap(self):
        c = build_constraints(parse_indicators("BMI 29"))
        self.assertEqual(c["energy_kcal_max"], 420)
        self.assertIn("油炸", c["hard_avoid_tags"])

    def test_hard_beats_caution(self):
        c = build_constraints(parse_indicators("血脂明显偏高，BMI 25"))
        self.assertIn("油炸", c["hard_avoid_tags"])
        self.assertNotIn("油炸", c["caution_tags"])


class TestDeriveTags(unittest.TestCase):
    def test_sugary_drink(self):
        tags = derive_tags({"name": "可口可乐(中)", "category": "饮品"})
        self.assertIn("含糖饮料", tags)

    def test_zero_sugar_overrides(self):
        tags = derive_tags({"name": "零度可口可乐(中)", "category": "饮品"})
        self.assertNotIn("含糖饮料", tags)
        self.assertIn("零糖饮品", tags)

    def test_fried(self):
        self.assertIn("油炸", derive_tags({"name": "麦辣鸡翅(2块)", "category": "小食"}))
        self.assertIn("油炸", derive_tags({"name": "薯条(中)", "category": "小食"}))

    def test_red_meat_and_dessert(self):
        self.assertIn("红肉", derive_tags({"name": "巨无霸", "category": "汉堡"}))
        self.assertIn("甜点", derive_tags({"name": "奥利奥麦旋风", "category": "甜点"}))

    def test_plain_milk_no_flags(self):
        tags = derive_tags({"name": "纯牛奶", "category": "饮品"})
        self.assertEqual(tags, [])


class TestClassifyItem(unittest.TestCase):
    def setUp(self):
        self.constraints = build_constraints(parse_indicators("血糖偏高，血脂偏高，血压 145/95"))

    def test_sugary_coke_is_red(self):
        coke = next(f for f in SAMPLE_FOODS if f["name"] == "可口可乐(中)")
        r = classify_item(coke, self.constraints)
        self.assertEqual(r["tier"], TIER_RED)

    def test_apple_slices_green(self):
        apple = next(f for f in SAMPLE_FOODS if f["name"] == "苹果片")
        r = classify_item(apple, self.constraints)
        self.assertEqual(r["tier"], TIER_GREEN)

    def test_big_mac_red_by_sodium(self):
        bigmac = next(f for f in SAMPLE_FOODS if f["name"] == "巨无霸")
        r = classify_item(bigmac, self.constraints)
        self.assertEqual(r["tier"], TIER_RED)
        self.assertTrue(any("钠" in reason for reason in r["reasons"]))

    def test_fries_yellow_by_fat_ratio(self):
        fries = next(f for f in SAMPLE_FOODS if f["name"] == "薯条(中)")
        r = classify_item(fries, self.constraints)
        self.assertIn(r["tier"], (TIER_YELLOW, TIER_RED))

    def test_tier_names_present(self):
        r = classify_item(SAMPLE_FOODS[0], self.constraints)
        self.assertIn(r["tier_name"], ("放心吃", "少吃", "别碰"))


class TestClassifyAllAndCombos(unittest.TestCase):
    def test_summary_counts_cover_all(self):
        constraints = build_constraints(parse_indicators("尿酸 480，血压 145/95"))
        result = classify_all(SAMPLE_FOODS, constraints)
        total = sum(result["summary"].values())
        self.assertEqual(total, len(SAMPLE_FOODS))

    def test_combos_fit_budget(self):
        constraints = build_constraints(parse_indicators("血脂偏高，血糖偏高，血压 145/95"))
        result = classify_all(SAMPLE_FOODS, constraints)
        self.assertTrue(result["combos"], "约束下应至少组合出一套套餐")
        for combo in result["combos"]:
            n = combo["nutrition"]
            self.assertLessEqual(n["energy_kcal"], constraints["energy_kcal_max"])
            self.assertLessEqual(n["fat_g"], constraints["fat_g_max"])
            self.assertLessEqual(n["carb_g"], constraints["carb_g_max"])
            self.assertLessEqual(n["sodium_mg"], constraints["sodium_mg_max"])
            self.assertLessEqual(n["protein_g"], constraints["protein_g_max"])

    def test_combos_contain_main_and_drink(self):
        constraints = build_constraints(parse_indicators("尿酸偏高"))
        result = classify_all(SAMPLE_FOODS, constraints)
        self.assertTrue(result["combos"])
        for combo in result["combos"]:
            cats = {c["category"] for c in result["items"] if c["name"] in combo["items"]}
            self.assertTrue(cats & {"汉堡", "早餐", "主食"})
            self.assertIn("饮品", cats)

    def test_combo_size_limit(self):
        constraints = build_constraints(parse_indicators("尿酸偏高"))
        classified = [classify_item(f, constraints) for f in SAMPLE_FOODS]
        combos = build_combos(classified, constraints, top_n=3)
        self.assertLessEqual(len(combos), 3)

    def test_green_items_never_exceed_caps(self):
        constraints = build_constraints(parse_indicators("血压 165/105"))
        result = classify_all(SAMPLE_FOODS, constraints)
        for item in result["items"]:
            if item["tier"] == TIER_GREEN:
                self.assertLessEqual(item["nutrition"]["sodium_mg"], constraints["sodium_mg_max"])


class TestReportCard(unittest.TestCase):
    def test_render_contains_key_sections(self):
        profile = parse_indicators("血脂偏高，尿酸 480")
        constraints = build_constraints(profile)
        classified = classify_all(SAMPLE_FOODS, constraints)
        html_text = render_html(profile, constraints, classified, "内置样例数据（dry-run）")
        for needle in ("麦门体检报告卡", "不构成医疗", "放心吃", "别碰", "推荐套餐组合", "尿酸"):
            self.assertIn(needle, html_text)

    def test_escapes_user_input(self):
        profile = parse_indicators("血脂偏高<script>alert(1)</script>")
        constraints = build_constraints(profile)
        classified = classify_all(SAMPLE_FOODS, constraints)
        html_text = render_html(profile, constraints, classified, "x")
        self.assertNotIn("<script>", html_text)

    def test_write_report_file(self):
        profile = parse_indicators("BMI 26")
        constraints = build_constraints(profile)
        classified = classify_all(SAMPLE_FOODS, constraints)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "r.html")
            write_report(path, profile, constraints, classified, "测试")
            with open(path, encoding="utf-8") as f:
                self.assertIn("麦门体检报告卡", f.read())


class TestDryRunDemo(unittest.TestCase):
    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            result = run("血脂偏高，尿酸 480，血压 145/95", d)
            for key in ("profile", "classified", "report"):
                self.assertTrue(os.path.exists(result[key]))
            foods, _ = load_foods()
            self.assertEqual(sum(result["summary"].values()), len(foods))
            with open(result["report"], encoding="utf-8") as f:
                content = f.read()
            self.assertIn("麦门体检报告卡", content)
            self.assertIn("不构成医疗", content)


class TestParseMcpData(unittest.TestCase):
    RAW = ("[4]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:\n"
           "  猪柳麦满分,null,1550,370,19,16,33,830,150\n"
           "  可乐中杯,null,630,150,0,0,40,10,0\n"
           "  猪柳麦满分,null,1550,370,19,16,33,830,150\n"
           "  苹果片,null,146,35,0,0,8,0,5\n")

    def test_parse_fields_and_dedupe(self):
        foods = parse_mcp_data(self.RAW)
        self.assertEqual(len(foods), 3)
        first = foods[0]
        self.assertEqual(first["name"], "猪柳麦满分")
        self.assertEqual(first["energy_kcal"], 370.0)
        self.assertEqual(first["sodium_mg"], 830.0)
        self.assertEqual(first["category"], "早餐")

    def test_bad_format_raises(self):
        with self.assertRaises(ValueError):
            parse_mcp_data("这不是合法的data字符串")

    def test_category_inference(self):
        self.assertEqual(infer_category("麦香鱼"), "汉堡")
        self.assertEqual(infer_category("蜜汁BBQ风味薄皮脆汁鸡-琵琶腿"), "小食")
        self.assertEqual(infer_category("蜜汁快乐"), "小食")
        self.assertEqual(infer_category("朱古力新地"), "甜点")
        self.assertEqual(infer_category("热朱古力"), "饮品")
        self.assertEqual(infer_category("酥酥多笋卷"), "主食")
        self.assertEqual(infer_category("烟肉蛋麦满分"), "早餐")


class TestRealSnapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = load_snapshot()
        cls.foods = cls.snapshot["foods"]

    def test_snapshot_integrity(self):
        self.assertGreaterEqual(len(self.foods), 150)
        self.assertEqual(self.snapshot["meta"]["deduped_count"], len(self.foods))
        names = [f["name"] for f in self.foods]
        self.assertEqual(len(names), len(set(names)))
        for f in self.foods:
            for field in ("energy_kcal", "protein_g", "fat_g", "carb_g", "sodium_mg", "calcium_mg"):
                self.assertIsInstance(f[field], (int, float), "%s 缺少 %s" % (f["name"], field))
            self.assertIn(f["category"], ("汉堡", "早餐", "小食", "饮品", "甜点", "主食"))

    def test_summary_covers_snapshot(self):
        constraints = build_constraints(parse_indicators("血脂偏高，尿酸 480，血压 145/95，BMI 26.5"))
        result = classify_all(self.foods, constraints)
        self.assertEqual(sum(result["summary"].values()), len(self.foods))

    def test_sugary_drinks_red_when_glucose_high(self):
        constraints = build_constraints(parse_indicators("血糖偏高"))
        result = classify_all(self.foods, constraints)
        by_name = {i["name"]: i for i in result["items"]}
        self.assertEqual(by_name["可乐中杯"]["tier"], TIER_RED)
        self.assertEqual(by_name["雪碧大杯"]["tier"], TIER_RED)
        self.assertEqual(by_name["无糖可口可乐中杯"]["tier"], TIER_GREEN)
        self.assertEqual(by_name["热美式中杯"]["tier"], TIER_GREEN)

    def test_fried_chicken_flagged(self):
        constraints = build_constraints(parse_indicators("血脂明显偏高"))
        result = classify_all(self.foods, constraints)
        by_name = {i["name"]: i for i in result["items"]}
        for fried in ("麦辣鸡翅-2块", "麦麦脆汁鸡-琵琶腿", "中薯条", "麦乐鸡5块"):
            self.assertIn("油炸", by_name[fried]["tags"])
            self.assertNotEqual(by_name[fried]["tier"], TIER_GREEN)

    def test_combos_fit_budget_on_snapshot(self):
        constraints = build_constraints(parse_indicators("血脂偏高，尿酸 480，血压 145/95，BMI 26.5"))
        result = classify_all(self.foods, constraints)
        self.assertTrue(result["combos"])
        for combo in result["combos"]:
            n = combo["nutrition"]
            self.assertLessEqual(n["energy_kcal"], constraints["energy_kcal_max"])
            self.assertLessEqual(n["fat_g"], constraints["fat_g_max"])
            self.assertLessEqual(n["sodium_mg"], constraints["sodium_mg_max"])
            self.assertLessEqual(n["protein_g"], constraints["protein_g_max"])

    def test_report_with_snapshot(self):
        profile = parse_indicators("血脂偏高，尿酸 480")
        constraints = build_constraints(profile)
        classified = classify_all(self.foods, constraints)
        html_text = render_html(profile, constraints, classified,
                                self.snapshot["meta"]["source"])
        self.assertIn("共 %d 项" % len(self.foods), html_text)
        self.assertIn("巨无霸", html_text)


if __name__ == "__main__":
    unittest.main()
