# openrouter-free-models

📡 OpenRouter 免费模型数据库，每日自动更新。

## 文件说明

| 文件 | 排序方式 | 说明 |
|------|---------|------|
| `models-global.json` | context 长度 | 所有免费模型（Prompt 价格 = 0） |
| `models-cn.json` | context 长度 | 国内可访问的免费模型（已移除 Google/OpenAI/Anthropic 等） |
| `models-strong-global.json` | 强 → 弱 | 同上，按能力强弱排序 |
| `models-strong-cn.json` | 强 → 弱 | 同上，按能力强弱排序 |
| `fetch_models.py` | — | 数据抓取脚本（供 cron 调用） |

## 强→弱排序规则（厂商分层 + 参数估算 + 上下文兜底）

启发式排序，分三层：

1. **厂商分层**（数字越小越强）
   - **Tier 0** frontier 级：DeepSeek / Qwen / Z-AI(GLM) / Moonshotai(Kimi)
   - **Tier 1** 强开源 70B+：Meta-Llama / NousResearch / NVIDIA(旗舰) / Poolside / Nex-AGI
   - **Tier 2** 中等 20B-32B：Mistral / 部分 Nemotron Nano
   - **Tier 3** 小模型 <20B：Dolphin 衍生
   - **Tier 4** 极小/特殊：Liquid 1.2B / OpenRouter 路由器 / 内容安全分类器
2. **同 tier 内**：从 id/name 提取 `Nb`（支持 MoE 写法 `120b-a12b` 取总参 120），从大到小
3. **同参数量**：context_length 兜底
4. 最后按 id 保稳定

## models-cn.json 排除的机构

`google`, `openai`, `anthropic`, `google/`, `openai/`, `anyscale`, `replicate`, `cohere`, `mistralai`, `meta-llama`, `ai21`, `stabilityai`, `azure`, `amazon`, `x-ai`, `x.ai`

## 数据结构

```json
{
  "version": "1.0",
  "updated": "2025-05-30T12:00:00Z",
  "count": 19,
  "models": [
    {
      "id": "deepseek/deepseek-v4-flash:free",
      "name": "DeepSeek V4 Flash (free)",
      "context_length": 1048576,
      "input_modalities": ["text"]
    }
  ]
}
```

## 自动更新

每日 12:00 (UTC+8) 由本地 cron (`orfm_sync.sh`) 自动运行 `fetch_models.py` 并提交到 main 分支。

如需手动更新：
```bash
python3 fetch_models.py
git add models-global.json models-cn.json models-strong-global.json models-strong-cn.json
git commit -m "Update free models $(date +%Y-%m-%d)"
git push
```
