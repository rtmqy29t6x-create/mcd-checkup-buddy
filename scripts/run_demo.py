#!/usr/bin/env python3
"""dry-run 端到端演示：样例指标 → 约束 → 三档分类 → HTML 报告卡。

不访问网络、不需要 MCD_MCP_TOKEN。
用法：
    python3 run_demo.py ["体检指标文本"] [--out 输出目录]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from health_profile import build_constraints, parse_indicators
from classify_foods import classify_all, load_foods
from report_card import write_report

DEFAULT_INPUT = "血脂偏高，尿酸 480，血压 145/95，BMI 26.5，轻度脂肪肝，血糖正常"


def run(text, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    foods, source = load_foods()
    profile = parse_indicators(text)
    constraints = build_constraints(profile)
    classified = classify_all(foods, constraints)

    profile_path = os.path.join(out_dir, "profile.json")
    classified_path = os.path.join(out_dir, "classified.json")
    report_path = os.path.join(out_dir, "mcd-checkup-report.html")
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump({"profile": profile, "constraints": constraints}, f, ensure_ascii=False, indent=2)
    with open(classified_path, "w", encoding="utf-8") as f:
        json.dump(classified, f, ensure_ascii=False, indent=2)
    write_report(report_path, profile, constraints, classified, source)
    return {"profile": profile_path, "classified": classified_path, "report": report_path,
            "source": source, "summary": classified["summary"]}


def main():
    parser = argparse.ArgumentParser(description="麦门体检搭子 dry-run 演示")
    parser.add_argument("text", nargs="?", default=DEFAULT_INPUT, help="体检指标文本")
    parser.add_argument("--out", default="output", help="输出目录")
    args = parser.parse_args()
    result = run(args.text, args.out)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
