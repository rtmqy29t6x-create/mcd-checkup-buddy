#!/usr/bin/env python3
"""解析 list-nutrition-foods 真实返回，生成标准化营养数据（零第三方依赖）。

真实返回的 structuredContent.data 是一个【字符串】，格式：
    [160]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:
      猪柳麦满分,null,1288,308,16,16,24,781,213
      ...
energyKcal 直接给出，无需从 kJ 换算。重复餐品名按首次出现去重。

用法：
    python3 parse_nutrition.py < mcp原始响应.json > foods.json
    python3 parse_nutrition.py --data-string data.txt > foods.json
"""
import argparse
import json
import sys

FIELDS = ("productName", "nutritionDescription", "energyKj", "energyKcal",
          "protein", "fat", "carbohydrate", "sodium", "calcium")

CATEGORY_RULES = [
    ("甜点", ("新地", "麦旋风", "圆筒", "冰淇淋", "派", "拉明顿", "奶冻", "爆珠", "阿芙佳朵")),
    ("饮品", ("可乐", "雪碧", "芬达", "咖啡", "红茶", "绿茶", "奶茶", "奶昔", "豆浆",
              "果汁", "苹果汁", "橙汁", "美汁源", "怡泉", "纯悦", "牛奶", "奶铁",
              "燕麦奶", "黑巧", "抹茶", "朱古力", "雪冰", "玛奇朵", "卡布奇诺",
              "美式", "麦旋酷")),
    ("早餐", ("麦满分", "粥", "油条", "薯饼", "双蛋堡", "早安", "香肠")),
    ("汉堡", ("堡", "巨无霸", "汉堡", "麦香")),
    ("主食", ("卷",)),
]
DEFAULT_CATEGORY = "小食"


def infer_category(name):
    """真实数据无分类字段，按餐品名规则推断（饮品/甜点优先，默认小食）。"""
    for category, keywords in CATEGORY_RULES:
        if any(k in name for k in keywords):
            return category
    return DEFAULT_CATEGORY


def parse_mcp_data(data):
    """把 MCP 返回的 data 字符串解析成标准化餐品列表。"""
    lines = [l.strip() for l in data.splitlines() if l.strip()]
    if not lines or not lines[0].startswith("["):
        raise ValueError("无法识别的 data 格式：%r" % (lines[0] if lines else data[:80]))
    foods = []
    seen = set()
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) != len(FIELDS):
            raise ValueError("行列数不符（期望 %d 列）：%r" % (len(FIELDS), line))
        row = dict(zip(FIELDS, parts))
        name = row["productName"]
        if name in seen:
            continue
        seen.add(name)
        foods.append({
            "name": name,
            "category": infer_category(name),
            "energy_kcal": float(row["energyKcal"]),
            "protein_g": float(row["protein"]),
            "fat_g": float(row["fat"]),
            "carb_g": float(row["carbohydrate"]),
            "sodium_mg": float(row["sodium"]),
            "calcium_mg": float(row["calcium"]),
        })
    return foods


def main():
    parser = argparse.ArgumentParser(description="解析 list-nutrition-foods 返回为标准 JSON")
    parser.add_argument("--data-string", help="直接给 data 字符串的文件；省略时从 stdin 读完整 MCP 响应 JSON")
    args = parser.parse_args()
    if args.data_string:
        with open(args.data_string, encoding="utf-8") as f:
            data = f.read()
    else:
        payload = json.load(sys.stdin)
        data = payload["structuredContent"]["data"]
    print(json.dumps(parse_mcp_data(data), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
