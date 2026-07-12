# 客服 Agent 微调数据集设计

> 日期：2026-07-12
> 状态：待用户审阅
> 目标模型：Qwen3-8B，非思考模式，LoRA/QLoRA SFT
> 训练框架：LLaMA-Factory ShareGPT 格式

## 1. 目标

生成 1000 条不含真实个人信息的合成客服 Agent 数据，用于验证 Qwen3-8B 在以下任务上的能力：

- 识别拼团进度、成团状态、余额额度和规则咨询；
- 选择正确工具并生成完整参数；
- 缺少必要参数时只追问最小信息；
- 根据工具结果回答，不编造实时业务数据；
- 正确处理工具失败、无数据、转人工和越权请求；
- 使用简洁、专业的中文客服话术。

本数据集用于第一版可行性验证，不代表生产数据质量已经达标。测试集需要人工逐条复核后才能作为正式验收基线。

## 2. 非目标

- 不把真实用户、订单、手机号或账户数据写入训练集；
- 不训练模型记忆实时拼团人数、余额或订单状态；
- 不替代 MySQL 工具、Redis 会话或 Qdrant RAG；
- 不生成思维链或隐藏推理过程；
- 不在本阶段启动训练、合并模型或部署服务；
- 不把训练集成绩当成模型泛化能力。

## 3. 输出文件

```text
data/finetune/customer_service_train.jsonl     # 800条
data/finetune/customer_service_val.jsonl       # 100条
data/finetune/customer_service_test.jsonl      # 100条
data/finetune/curated_test_cases.jsonl          # 至少20条人工编写的测试源样本
data/finetune/dataset_info.json                # LLaMA-Factory注册信息
data/finetune/dataset_stats.json               # 数量、分类、Token近似统计
scripts/finetune/generate_customer_dataset.py  # 固定随机种子的可重复生成器
scripts/finetune/validate_customer_dataset.py  # 格式、业务约束和泄漏校验
```

JSONL 使用 UTF-8 编码，每行一个完整 JSON 对象。生成器固定随机种子；相同代码和配置必须产生相同数据与统计结果。

`curated_test_cases.jsonl` 是测试集的受控输入之一，由人工编写并纳入版本管理；生成器将它与自动生成的测试场景合并为最终 100 条测试集，从而同时满足人工质量和可重复生成要求。

## 4. 数据拆分

| 数据集 | 数量 | 是否更新模型 | 用途 |
| --- | ---: | --- | --- |
| Train | 800 | 是 | LoRA/QLoRA 参数学习 |
| Validation | 100 | 否 | 选择训练轮数和最佳 checkpoint |
| Test | 100 | 否 | 最终泛化评测，只在方案确定后使用 |

拆分必须发生在生成具体文本之前。每个拆分使用独立的表达模板、场景组合和实体编号范围，避免先生成近似样本再随机切分造成泄漏。

建议编号范围：

```text
Train:      u_tr_*, TEAM-TR-*, ACT-TR-*
Validation: u_va_*, TEAM-VA-*, ACT-VA-*
Test:       u_te_*, TEAM-TE-*, ACT-TE-*
```

## 5. 场景配额

### 5.1 总体配额

| 类别 | Train | Validation | Test | 总计 |
| --- | ---: | ---: | ---: | ---: |
| 业务工具调用 | 440 | 55 | 55 | 550 |
| RAG 规则问答 | 160 | 20 | 20 | 200 |
| 缺少参数与最小追问 | 80 | 10 | 10 | 100 |
| 工具失败、超时、无数据 | 40 | 5 | 5 | 50 |
| 投诉、争议、转人工 | 40 | 5 | 5 | 50 |
| 闲聊、越权、提示词攻击 | 40 | 5 | 5 | 50 |
| 合计 | 800 | 100 | 100 | 1000 |

### 5.2 工具调用配额

| 工具 | Train | Validation | Test | 总计 |
| --- | ---: | ---: | ---: | ---: |
| `group_buy_progress(user_id, team_id)` | 176 | 22 | 22 | 220 |
| `group_complete(user_id, team_id)` | 120 | 15 | 15 | 150 |
| `balance_usage(user_id)` | 144 | 18 | 18 | 180 |
| 合计 | 440 | 55 | 55 | 550 |

`knowledge_search(query)` 计入 RAG 规则问答类别，共 200 条。

## 6. 工具契约

数据必须与当前代码中的工具契约一致：

```text
group_buy_progress(user_id: str, team_id: str)
group_complete(user_id: str, team_id: str)
balance_usage(user_id: str)
knowledge_search(query: str)
```

禁止生成以下不存在的参数：

```text
activity_id 作为 group_buy_progress 的直接参数
order_id 作为 group_complete 的直接参数
top_k 作为 knowledge_search 的模型参数
```

如果用户只提供 `activity_id`、订单号或模糊指代，而当前工具要求 `team_id`，样本应追问 `team_id`，不能编造或偷偷完成不存在的映射。

## 7. 训练记录格式

采用 LLaMA-Factory ShareGPT 工具调用格式。工具成功样例：

```json
{
  "conversations": [
    {
      "from": "human",
      "value": "帮我看看 TEAM-TR-001 这个团还差几个人？"
    },
    {
      "from": "function_call",
      "value": "{\"name\":\"group_buy_progress\",\"arguments\":{\"user_id\":\"u_tr_001\",\"team_id\":\"TEAM-TR-001\"}}"
    },
    {
      "from": "observation",
      "value": "拼团 TEAM-TR-001：当前 3 人，目标 5 人，还差 2 人成团，截止 2026-08-01 20:00:00。"
    },
    {
      "from": "gpt",
      "value": "您的拼团当前还差2人即可成团，截止时间为2026年8月1日20:00。"
    }
  ],
  "system": "你是拼团平台智能客服。实时业务数据必须依据工具结果，不得编造。回答应简洁、专业。",
  "tools": "[...]",
  "metadata": {
    "sample_id": "train-progress-0001",
    "split": "train",
    "category": "tool_call",
    "scenario": "group_buy_progress"
  }
}
```

缺少参数样例不产生工具调用：

```json
{
  "conversations": [
    {"from": "human", "value": "帮我看看我的团还差几个人。"},
    {"from": "gpt", "value": "请提供需要查询的拼团编号（team_id）。"}
  ],
  "system": "你是拼团平台智能客服。缺少工具必填参数时，只追问最小必要信息。",
  "tools": "[...]",
  "metadata": {
    "sample_id": "train-clarify-0001",
    "split": "train",
    "category": "clarification",
    "scenario": "missing_team_id"
  }
}
```

`metadata` 用于生成质量检查，注册到 LLaMA-Factory 时不作为模型消息列。

### 7.1 关于 tool_call_id

LLaMA-Factory 的 ShareGPT SFT 格式使用相邻的 `function_call → observation` 表达工具轨迹，并不要求保存线上运行时的 `tool_call_id`。因此：

- 数据集校验工具调用顺序、名称和参数；
- 线上 LangChain 的 `AIMessage.tool_calls` 与 `ToolMessage.tool_call_id` 仍由应用测试单独验证；
- 不在训练数据中虚构供应商相关的调用 ID。

## 8. 混合生成策略

生成器由确定性业务状态和表达变体组成，不依赖外部 LLM 批量自由生成。

### 8.1 确定性业务状态

- 拼团进度满足 `current_people + remain_people = target_people`；
- 已成团时 `complete_at` 必须非空；未成团时 `complete_at` 必须为空；
- `remaining = total_quota - used`，且所有额度非负；
- 工具错误样本只能基于错误 observation 生成兜底答复；
- 规则答案只允许引用对应 knowledge observation；
- 动态业务事实不得出现在未调用工具的回答中。

### 8.2 表达多样性

各拆分使用不同短语库，覆盖：

- 标准书面问法；
- 口语、省略、错别字和重复标点；
- 缺少主语或使用“这个团”“刚才那个”等指代；
- 同时询问两个诉求；
- 情绪化但不违规的表达；
- 尝试让模型跳过工具、查询他人信息或泄露系统提示。

不能只替换 user_id/team_id 就把同一模板复制到不同拆分。

## 9. 防泄漏规则

- Train、Validation、Test 的用户表达模板集合互斥；
- 实体编号前缀互斥；
- 多意图组合在 Test 中保留部分训练阶段未出现的组合；
- 对规范化文本计算 SHA-256，禁止精确重复；
- 去掉编号、时间、数字和标点后计算字符 3-gram Jaccard，相似度大于或等于 `0.92` 的跨拆分样本判为失败；
- 测试集至少包含 20 条来自 `curated_test_cases.jsonl` 的完全人工编写或人工重写表达，不能全部由训练模板派生；
- 20 条人工测试源样本固定分配为：工具调用 8（进度3、成团2、余额3）、RAG 4、缺参追问 2、异常 2、转人工 2、安全 2；
- 测试集在训练参数和 checkpoint 选择完成前不得用于调参。

## 10. 数据校验

验证脚本失败时返回非零退出码，并至少检查：

1. 三个 JSONL 文件分别为 800、100、100 行；
2. 每行能被标准 JSON 解析；
3. `sample_id` 全局唯一；
4. split、category、scenario 与目标文件一致；
5. 对话角色顺序符合 ShareGPT 工具格式；
6. function_call 使用允许的工具名和精确参数集合；
7. observation 与最终回答中的人数、额度、状态和时间一致；
8. 缺参数样本不产生 function_call；
9. 实时业务问题未经工具 observation 不得给出具体业务数值；
10. 不包含手机号、身份证、真实邮箱、API Key 或生产数据库连接信息；
11. 没有跨拆分精确重复和超过阈值的近似重复；
12. 分类配额与第 5 节完全一致；
13. `dataset_info.json` 能被解析，文件名和列映射正确；
14. `dataset_stats.json` 与实际扫描结果一致。

## 11. 人工审核

- Train：至少抽检 20%，重点检查工具参数和工具结果一致性；
- Validation：逐条审核；
- Test：逐条审核，并锁定版本；
- 出现严重业务事实错误、越权查询放行或工具契约错误时，整批数据不得进入训练；
- 人工修改后必须重新运行全部验证。

## 12. 验收标准

- 1000 条数据按 800/100/100 精确拆分；
- 综合类别和工具子类别配额完全匹配；
- 所有记录通过 JSON、角色序列、工具契约和业务算术校验；
- 无真实个人信息和生产密钥；
- Train/Validation/Test 不存在精确或高相似泄漏；
- 同一固定种子可重复生成完全相同的文件；
- 测试集已明确标记需要逐条人工确认；
- 生成器、验证器和静态数据均可由项目内命令独立复现与检查。
