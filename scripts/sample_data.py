#!/usr/bin/env python3
"""麦当劳餐品六维营养演示样例数据（零第三方依赖）。

仅在未配置 MCD_MCP_TOKEN 的 dry-run 模式下使用。
数值为按公开信息整理的演示近似值，单位：能量 kcal、蛋白质/脂肪/碳水 g、钠/钙 mg。
真实使用时请以 list-nutrition-foods 工具返回的官方实时数据为准。

用法：
    python3 sample_data.py            # 打印全部样例 JSON
"""
import json
import sys

SAMPLE_FOODS = [
    {"name": "巨无霸", "category": "汉堡", "energy_kcal": 512, "protein_g": 26, "fat_g": 26, "carb_g": 42, "sodium_mg": 1010, "calcium_mg": 220},
    {"name": "双层吉士汉堡", "category": "汉堡", "energy_kcal": 437, "protein_g": 25, "fat_g": 23, "carb_g": 34, "sodium_mg": 1080, "calcium_mg": 250},
    {"name": "吉士汉堡", "category": "汉堡", "energy_kcal": 299, "protein_g": 15, "fat_g": 12, "carb_g": 33, "sodium_mg": 720, "calcium_mg": 150},
    {"name": "汉堡包", "category": "汉堡", "energy_kcal": 248, "protein_g": 12, "fat_g": 8, "carb_g": 32, "sodium_mg": 490, "calcium_mg": 60},
    {"name": "麦香鱼", "category": "汉堡", "energy_kcal": 340, "protein_g": 15, "fat_g": 13, "carb_g": 39, "sodium_mg": 560, "calcium_mg": 120},
    {"name": "麦香鸡", "category": "汉堡", "energy_kcal": 386, "protein_g": 14, "fat_g": 17, "carb_g": 45, "sodium_mg": 720, "calcium_mg": 60},
    {"name": "板烧鸡腿堡", "category": "汉堡", "energy_kcal": 404, "protein_g": 23, "fat_g": 15, "carb_g": 44, "sodium_mg": 920, "calcium_mg": 80},
    {"name": "麦辣鸡腿堡", "category": "汉堡", "energy_kcal": 485, "protein_g": 22, "fat_g": 21, "carb_g": 53, "sodium_mg": 1090, "calcium_mg": 80},
    {"name": "培根蔬萃双层牛堡", "category": "汉堡", "energy_kcal": 460, "protein_g": 27, "fat_g": 22, "carb_g": 38, "sodium_mg": 1050, "calcium_mg": 180},
    {"name": "麦乐鸡(4块)", "category": "小食", "energy_kcal": 190, "protein_g": 11, "fat_g": 11, "carb_g": 12, "sodium_mg": 430, "calcium_mg": 10},
    {"name": "麦辣鸡翅(2块)", "category": "小食", "energy_kcal": 260, "protein_g": 15, "fat_g": 17, "carb_g": 12, "sodium_mg": 640, "calcium_mg": 15},
    {"name": "那么大鸡排", "category": "小食", "energy_kcal": 362, "protein_g": 21, "fat_g": 20, "carb_g": 25, "sodium_mg": 780, "calcium_mg": 20},
    {"name": "薯条(中)", "category": "小食", "energy_kcal": 337, "protein_g": 4, "fat_g": 17, "carb_g": 42, "sodium_mg": 270, "calcium_mg": 10},
    {"name": "玉米杯", "category": "小食", "energy_kcal": 70, "protein_g": 2, "fat_g": 1, "carb_g": 14, "sodium_mg": 5, "calcium_mg": 5},
    {"name": "苹果片", "category": "小食", "energy_kcal": 35, "protein_g": 0, "fat_g": 0, "carb_g": 8, "sodium_mg": 0, "calcium_mg": 5},
    {"name": "美味蔬菜杯", "category": "小食", "energy_kcal": 20, "protein_g": 1, "fat_g": 0, "carb_g": 4, "sodium_mg": 15, "calcium_mg": 20},
    {"name": "猪柳蛋麦满分", "category": "早餐", "energy_kcal": 389, "protein_g": 21, "fat_g": 17, "carb_g": 34, "sodium_mg": 840, "calcium_mg": 150},
    {"name": "吉士蛋麦满分", "category": "早餐", "energy_kcal": 295, "protein_g": 14, "fat_g": 12, "carb_g": 31, "sodium_mg": 670, "calcium_mg": 140},
    {"name": "皮蛋瘦肉粥", "category": "早餐", "energy_kcal": 145, "protein_g": 6, "fat_g": 2, "carb_g": 25, "sodium_mg": 590, "calcium_mg": 15},
    {"name": "脆香油条", "category": "早餐", "energy_kcal": 230, "protein_g": 5, "fat_g": 12, "carb_g": 26, "sodium_mg": 320, "calcium_mg": 10},
    {"name": "薯饼", "category": "早餐", "energy_kcal": 145, "protein_g": 1, "fat_g": 9, "carb_g": 15, "sodium_mg": 360, "calcium_mg": 10},
    {"name": "可口可乐(中)", "category": "饮品", "energy_kcal": 210, "protein_g": 0, "fat_g": 0, "carb_g": 56, "sodium_mg": 15, "calcium_mg": 0},
    {"name": "零度可口可乐(中)", "category": "饮品", "energy_kcal": 0, "protein_g": 0, "fat_g": 0, "carb_g": 0, "sodium_mg": 20, "calcium_mg": 0},
    {"name": "雪碧(中)", "category": "饮品", "energy_kcal": 205, "protein_g": 0, "fat_g": 0, "carb_g": 54, "sodium_mg": 35, "calcium_mg": 0},
    {"name": "纯牛奶", "category": "饮品", "energy_kcal": 130, "protein_g": 7, "fat_g": 7, "carb_g": 10, "sodium_mg": 90, "calcium_mg": 240},
    {"name": "热美式咖啡", "category": "饮品", "energy_kcal": 6, "protein_g": 0, "fat_g": 0, "carb_g": 1, "sodium_mg": 5, "calcium_mg": 0},
    {"name": "锡兰红茶", "category": "饮品", "energy_kcal": 2, "protein_g": 0, "fat_g": 0, "carb_g": 0, "sodium_mg": 5, "calcium_mg": 0},
    {"name": "美汁源橙汁", "category": "饮品", "energy_kcal": 180, "protein_g": 1, "fat_g": 0, "carb_g": 43, "sodium_mg": 10, "calcium_mg": 20},
    {"name": "珍珠奶茶", "category": "饮品", "energy_kcal": 320, "protein_g": 3, "fat_g": 6, "carb_g": 62, "sodium_mg": 60, "calcium_mg": 80},
    {"name": "圆筒冰淇淋", "category": "甜点", "energy_kcal": 130, "protein_g": 3, "fat_g": 4, "carb_g": 21, "sodium_mg": 60, "calcium_mg": 100},
    {"name": "奥利奥麦旋风", "category": "甜点", "energy_kcal": 340, "protein_g": 6, "fat_g": 11, "carb_g": 55, "sodium_mg": 180, "calcium_mg": 200},
    {"name": "香芋派", "category": "甜点", "energy_kcal": 240, "protein_g": 2, "fat_g": 12, "carb_g": 31, "sodium_mg": 180, "calcium_mg": 10},
    {"name": "菠萝派", "category": "甜点", "energy_kcal": 235, "protein_g": 2, "fat_g": 11, "carb_g": 32, "sodium_mg": 170, "calcium_mg": 10},
]


def main():
    print(json.dumps(SAMPLE_FOODS, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
