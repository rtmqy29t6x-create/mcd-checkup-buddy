# MCP 集成说明：麦门体检搭子

本文档说明本项目实际使用的麦当劳 MCP Server、Tool、调用流程与业务价值。

## MCP Server

- 接入地址：`https://mcp.mcd.cn`
- 传输协议：Streamable HTTP
- 认证方式：请求头 `Authorization: Bearer $MCD_MCP_TOKEN`（Token 从环境变量读取，不落盘）
- 配置示例：见根目录 `mcp-config.example.json`（仅含环境变量占位符）

## 实际使用的 Tool

| Tool | 用途 | 调用时机 |
|---|---|---|
| `list-nutrition-foods` | 获取麦当劳常见餐品的六维营养数据（能量/蛋白质/脂肪/碳水/钠/钙），作为餐品分档与套餐求解的唯一数据来源 | 核心流程第 3 步，每次生成报告前调用一次，保证数据实时 |

### list-nutrition-foods 实测返回格式（2026-10-09 联调确认）

- 返回 `structuredContent.data` 是一个**字符串**（非 JSON 数组），格式为
  `[160]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:` 后跟逐行 CSV 记录；
- `energyKcal` 字段直接给出千卡值，**无需从 kJ 换算**；
- 无餐品分类字段，`scripts/parse_nutrition.py` 负责解析该字符串、按餐品名规则推断分类（汉堡/早餐/小食/饮品/甜点/主食）、按名称去重（实测 160 行去重后 158 项）；
- 项目内置快照 `scripts/nutrition_snapshot.json`（2026-10-09 采集），供离线演示与单元测试使用。

核心流程**只读取数据，不产生任何账户变更**，因此无需对 `list-nutrition-foods` 做确认门控。

### 可选扩展（用户主动要求下单时才进入）

若用户看完报告后主动要求"按推荐套餐下单"，流程延伸使用以下 Tool，且全部受确认门控约束（详见 `SKILL.md`）：

| Tool | 用途 | 门控 |
|---|---|---|
| `query-nearby-stores` | 定位用户附近可下单门店 | 只读，无需确认 |
| `query-meals` / `query-meal-detail` | 核对推荐套餐内餐品在当店是否在售、套餐组成 | 只读，无需确认 |
| `auto-bind-coupons` | 一键领取麦麦省优惠券 | **执行前需用户明确同意** |
| `calculate-price` | 核对含券价格 | 领券后、下单前，向用户展示明细 |
| `create-order` | 创建订单 | **复述门店/餐品/价格/取餐方式并获确认后才调用** |
| `query-order` / `cancel-order` | 订单进度查询与取消 | 取消前需再次确认 |

## 调用流程

```
用户口述体检指标
      │
      ▼
scripts/health_profile.py        ← 确定性脚本：指标解析 + 单餐营养预算
      │  {"profile": ..., "constraints": ...}
      ▼
MCP: list-nutrition-foods        ← 官方实时餐品营养数据（离线时用 scripts/nutrition_snapshot.json 真实快照）
      │  data 字符串
      ▼
scripts/parse_nutrition.py       ← 确定性脚本：解析 data 字符串 + 分类推断 + 去重
      │  foods.json
      ▼
scripts/classify_foods.py        ← 确定性脚本：三档分类（放心吃/少吃/别碰）+ 套餐组合求解
      │  {"items": ..., "combos": ..., "summary": ...}
      ▼
AI 对话解读（不估算任何数字）
      │
      ▼
scripts/report_card.py           ← 确定性脚本：生成体检风 HTML 报告卡
      │
      ▼
用户分享 /（可选）确认后进入点餐扩展流程
```

设计原则：**AI 只做编排和对话，所有数字判断（约束阈值、分档、组合求和）都在零依赖 Python 脚本内完成**，避免大模型对营养数值进行估算或编造。脚本输入输出均为 JSON 文件，便于审计与复现。

## 业务价值

1. **盘活营养数据的真实场景**：`list-nutrition-foods` 从"查热量工具"升级为"体检季点餐决策"——六维营养 × 六类体检指标的约束映射，让官方数据直接服务用户最焦虑的时刻。
2. **差异化**：不做通用"低热量套餐"计算器，而是按个人体检指标生成**千人千面的白名单**，血脂高与尿酸高的用户得到不同结果。
3. **可传播**：体检报告风格的 HTML 报告卡天然适合社交分享，为麦当劳 MCP 带来二次曝光。
4. **可延伸**：分档结果可直接对接点餐工具链（门店→菜单→核价→下单），从"建议"到"履约"闭环，且全程确认门控。

## 已知边界

- MCP 营养数据仅六维，**不含嘌呤、膳食纤维、糖含量**；尿酸相关提醒由 `scripts/health_profile.py` 内的人工规则知识库补齐，属于经验性提示，已在 README 与报告卡中向用户明示。
- 离线快照（`scripts/nutrition_snapshot.json`，2026-10-09 采集，158 项）为真实接口数据的历史截面，可能与门店实时菜单存在差异；`scripts/sample_data.py`（33 项）仅作为快照缺失时的兜底与单元测试夹具。
