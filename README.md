# 麦门体检搭子（mcd-checkup-buddy）

> 体检报告上的箭头 ▲，翻译成麦当劳菜单上的绿灯 🟢。

每年体检季，程序员们都要经历一次灵魂拷问：报告上那几个向上的箭头，到底意味着什么？
意味着你妈会说"别吃外卖了"，意味着你自己对着麦当劳 App 犹豫了三十秒——**巨无霸还能点吗？**

「麦门体检搭子」就是来回答这个问题的。
把你的体检指标（血脂、尿酸、血糖、血压、BMI、脂肪肝）丢给它，它会：

1. 把指标翻译成一份**单餐营养处方**（能量/蛋白质/脂肪/碳水/钠/钙六维预算）；
2. 通过**麦当劳官方 MCP 服务**拉取全部餐品的真实营养数据；
3. 用确定性 Python 求解器把菜单分成三档：**🟢 放心吃 / 🟡 少吃 / 🔴 别碰**；
4. 自动组合出几套**全部达标的推荐套餐**；
5. 生成一张**体检报告风格的 HTML 报告卡**——指标、结论、医嘱一应俱全，截图就能发朋友圈/小红书。

不是"热量 ≤ 600"那种粗暴一刀切。血脂高和尿酸高的人，拿到的白名单是不一样的——这才叫"搭子"，不是计算器。

## 效果示例

输入：

```
血脂偏高，尿酸 480，血压 145/95，BMI 26.5，轻度脂肪肝
```

输出（基于 2026-10-09 真实接口数据，158 项餐品，节选）：

- 营养处方：能量 ≤ 500 kcal/餐、脂肪 ≤ 15 g/餐、钠 ≤ 650 mg/餐、蛋白质 ≤ 24 g/餐
- 🟢 放心吃 51 项｜🟡 少吃 33 项｜🔴 别碰 74 项
- 推荐套餐：烟肉蛋麦满分 + 冰奶铁小杯 + 小杯玉米杯（能量 399 kcal · 钠 528 mg · 蛋白质 23 g，全部达标）
- 一张「麦门体检报告卡」HTML：含指标解读、麦门医嘱、免责声明，排版致敬体检报告

## 目标用户

- 每年体检季对着报告发愁的**程序员**（久坐、外卖、奶茶三件套受害者）
- 体检指标个别偏高、但又不想完全戒掉快乐的**都市打工人**
- 想把"吃得克制"变成一件有梗、可分享的事的**麦门信徒**

## 安装与配置

本项目是 **Agent Skill + Python 脚本**的混合形态：

- `SKILL.md`：教 AI（Cursor / Trae / Cherry Studio / WorkBuddy 等任意支持 MCP 的客户端）如何编排整个流程；
- `scripts/`：零第三方依赖的 Python 3 脚本，负责全部数字计算；
- 无构建步骤，`python3 --version ≥ 3.9` 即可。

### 1. 申请麦当劳 MCP Token

前往 [麦当劳 MCP 开放平台](https://open.mcd.cn/mcp)，手机号登录后在控制台激活 Token。

### 2. 配置 MCP 客户端

复制 `mcp-config.example.json` 的内容到你的 MCP 客户端配置中，Token 通过环境变量注入：

```bash
export MCD_MCP_TOKEN="你的Token"
```

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": { "Authorization": "Bearer ${MCD_MCP_TOKEN}" }
    }
  }
}
```

### 3. 加载 Skill

把本仓库的 `SKILL.md` 作为技能/规则文件加入你的 AI 客户端（各客户端加载方式不同，Cursor 可放 `.cursor/rules`，其他客户端参考其技能加载文档）。

## 使用示例

### 对话模式（有 Token）

> 你：我体检血脂偏高、尿酸 480，帮我看看麦当劳还能吃啥
>
> AI：（解析指标 → 调用 list-nutrition-foods → 运行求解脚本 → 生成报告卡）
> "你的单餐预算是脂肪 ≤ 15g、蛋白质 ≤ 24g。放心吃 8 项，推荐麦香鱼 + 锡兰红茶。报告卡已生成：mcd-checkup-report.html"

### dry-run 演示（无 Token，离线可跑，使用真实数据快照）

仓库内置 `scripts/nutrition_snapshot.json`——2026-10-09 经 `list-nutrition-foods` 采集的真实数据快照（去重后 158 项），无需 Token 即可完整体验：

```bash
python3 scripts/run_demo.py "血脂偏高，尿酸 480，血压 145/95，BMI 26.5，轻度脂肪肝"
# 产物在 output/：profile.json、classified.json、mcd-checkup-report.html
```

### 分步手动跑

```bash
# 1. 指标 → 营养约束
python3 scripts/health_profile.py "血糖偏高，血压 145/95" > profile.json

# 2a. 有 Token：调用 list-nutrition-foods，解析真实返回（data 为 CSV 风格字符串）
python3 scripts/parse_nutrition.py < mcp_raw_response.json > foods.json

# 2b. 餐品分档 + 套餐组合（不传 --foods 自动用真实快照）
python3 scripts/classify_foods.py --constraints profile.json --foods foods.json > classified.json

# 3. 生成体检风报告卡
python3 scripts/report_card.py --profile profile.json --classified classified.json --out report.html
```

### 运行测试

```bash
python3 -m unittest discover -s tests
```

45 个离线单元测试（含真实数据快照夹具），不依赖网络与 Token。

## 诚实的边界说明

- **不构成医疗建议。** 本项目输出仅供点餐参考与娱乐，诊疗请遵医嘱。
- **嘌呤不在 MCP 数据里。** 麦当劳 MCP 营养数据只有能量/蛋白质/脂肪/碳水/钠/钙六维。尿酸相关的"红肉/海鲜适量"提醒来自人工整理的规则知识库，是经验性提示，不是精确计算。
- **阈值是通用参考值。** 指标分级（如尿酸 420/480 μmol/L、血压 140/160 mmHg）采用公开通用的参考界值，个体差异请咨询医生。
- **dry-run 数据是真实数据的历史快照。** 离线模式使用 2026-10-09 采集的 `list-nutrition-foods` 真实返回（158 项），与门店实时菜单可能有差异；连接 MCP 后自动切换为实时数据。

## 合规与安全

- Token 一律从环境变量 `MCD_MCP_TOKEN` 读取，仓库内不含任何真实凭证；
- 核心流程（查营养、分类、出报告）**零消耗性操作**；若延伸到点餐，领券/下单均需用户明确确认后才执行（见 `SKILL.md` 确认门控）；
- 参赛声明见 `CONTEST_DECLARATION.md`；MCP 使用细节见 `MCP_INTEGRATION.md`。

## 目录结构

```
mcd-checkup-buddy/
├── README.md                  # 本文件
├── SKILL.md                   # Agent Skill 编排说明
├── CONTEST_DECLARATION.md     # 参赛声明
├── MCP_INTEGRATION.md         # MCP 集成说明
├── mcp-config.example.json    # 脱敏 MCP 配置示例
├── scripts/
│   ├── health_profile.py      # 体检指标解析 → 营养约束
│   ├── parse_nutrition.py     # list-nutrition-foods 真实返回解析（data 字符串 → 标准 JSON）
│   ├── classify_foods.py      # 餐品三档分类 + 套餐组合求解
│   ├── report_card.py         # 体检风 HTML 报告卡生成
│   ├── nutrition_snapshot.json# 真实数据快照（2026-10-09 采集，158 项）
│   ├── sample_data.py         # 兜底演示样例数据
│   └── run_demo.py            # 离线端到端演示入口
└── tests/
    └── test_checkup.py        # 45 个离线单元测试（含快照夹具）
```

---

如果这个项目让你在体检季多了一点快乐，欢迎点个 Star ⭐
