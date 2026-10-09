---
name: mcd-checkup-buddy
description: 麦门体检搭子——把体检报告翻译成麦门点餐白名单。当用户提到体检、体检报告、血脂/尿酸/血糖/血压/BMI/脂肪肝等指标异常，或问"我这种身体情况能吃麦当劳什么/帮我看看体检指标点什么麦当劳"时使用。通过麦当劳 MCP 的 list-nutrition-foods 获取官方六维营养数据，配合本地确定性 Python 脚本完成指标解析、约束求解、餐品三档分类（放心吃/少吃/别碰）与体检风 HTML 报告卡生成。未配置 MCD_MCP_TOKEN 时可用仓库内置真实数据快照离线演示。
---

# 麦门体检搭子（mcd-checkup-buddy）

把用户的体检指标翻译成一份「麦门点餐白名单」，并生成一张体检报告风格的 HTML 分享卡。

## 角色分工（重要）

- **AI（你）**：负责对话、采集指标、调用 MCP 工具、调用本地脚本、组织语言输出。
- **Python 脚本（scripts/）**：负责所有数字计算与判断——指标解析、约束生成、餐品分档、套餐组合。**严禁凭感觉估算任何数值**，所有营养数字必须来自 MCP 工具返回或脚本输出。

## 全流程编排

### 第 1 步：采集体检指标（对话）

请用户口述或粘贴体检指标，支持模糊表述与具体数值混用，例如：
「血脂偏高，尿酸 480，血压 145/95，BMI 26.5，轻度脂肪肝」。

可追问补全以下六个指标（用户不说就跳过，不要强问）：
血脂/胆固醇、尿酸、血糖/糖化血红蛋白、血压、BMI、脂肪肝。

### 第 2 步：指标解析与约束生成（脚本）

```bash
python3 scripts/health_profile.py "<用户的指标文本>" > /tmp/mcd_profile.json
```

输出 JSON 含 `profile`（结构化指标）与 `constraints`（单餐六维营养预算 + 硬规避/软提醒标签）。
把 `constraints` 段单独保存（`profile.json` 已是完整结构，后续脚本可直接读）。

### 第 3 步：获取餐品营养数据（MCP 或离线快照）

- **有 MCD_MCP_TOKEN**：调用麦当劳 MCP 工具 `list-nutrition-foods`。注意其 `structuredContent.data` 是一个**字符串**而非 JSON 数组，格式为 `[160]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:\n  猪柳麦满分,null,1288,308,16,16,24,781,213\n ...`（energyKcal 已直接给出，无需 kJ 换算）。把完整响应 JSON 存为 `/tmp/mcd_nutrition_raw.json`，然后用解析器转成标准格式：

```bash
python3 scripts/parse_nutrition.py < /tmp/mcd_nutrition_raw.json > /tmp/mcd_foods.json
python3 scripts/classify_foods.py --constraints /tmp/mcd_profile.json --foods /tmp/mcd_foods.json > /tmp/mcd_classified.json
```

- **无 Token（离线）**：`classify_foods.py` 不传 `--foods` 时自动使用仓库内的真实数据快照 `scripts/nutrition_snapshot.json`（2026-10-09 经 `list-nutrition-foods` 采集，去重后 158 项）；快照缺失时才回退到内置样例数据。向用户说明当前数据口径。

### 第 4 步：解读结果（对话）

向用户讲清楚三档结论（放心吃 / 少吃 / 别碰）和推荐套餐组合。**不要逐条念清单**，挑重点：
- 哪几项指标决定了今天的预算；
- 「别碰」里最让人意外的 1-2 项及原因；
- 推荐套餐的组合逻辑（为什么这几样能搭在一起）。

### 第 5 步：生成体检风报告卡（脚本）

```bash
python3 scripts/report_card.py --profile /tmp/mcd_profile.json --classified /tmp/mcd_classified.json --out mcd-checkup-report.html --source "麦当劳 MCP list-nutrition-foods（实时数据）"
# dry-run 时 --source 写 "内置样例数据（dry-run，未连接 MCP）"
```

把 HTML 文件路径交给用户，提示可浏览器打开、截图分享。

### 第 6 步：免责与边界（必须说）

- 本结果仅供点餐参考，**不构成医疗建议**，诊疗请遵医嘱；
- MCP 营养数据只有能量/蛋白质/脂肪/碳水/钠/钙六维，**嘌呤不在数据里**，尿酸相关提醒基于人工规则，存在边界；
- 离线模式下数据来自仓库内快照（2026-10-09 采集的真实数据，去重后 158 项），可能与门店实时菜单存在差异。

## 消耗性操作确认门控（红线）

本技能核心流程（查询营养、分类、出报告）**不涉及任何消耗性操作**，可直接执行。

若用户在看完报告后进一步要求"那就按推荐套餐帮我下单"，则进入点餐流程，此时：
1. `auto-bind-coupons`（领券）、`calculate-price`（核价）属于会改变账户状态的操作，执行**前**必须明确告知并征得用户同意；
2. `create-order`（创建订单）执行**前**必须向用户完整复述门店、餐品、价格、取餐方式，得到用户明确确认后才可调用；
3. **严禁**在未确认的情况下静默领券、静默下单；
4. 下单后主动提示可用 `query-order` 查进度、`cancel-order` 取消（取消前同样需确认）。

## MCP 配置

接入地址 `https://mcp.mcd.cn`，Streamable HTTP 协议，请求头 `Authorization: Bearer $MCD_MCP_TOKEN`。配置示例见项目根目录 `mcp-config.example.json`，Token 一律从环境变量 `MCD_MCP_TOKEN` 读取，不得写入任何文件。

## 一键演示（离线，无需 Token，使用真实数据快照）

```bash
python3 scripts/run_demo.py "血脂偏高，尿酸 480，血压 145/95，BMI 26.5，轻度脂肪肝"
# 产物在 output/：profile.json、classified.json、mcd-checkup-report.html
```
