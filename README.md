# openrouter-free-models

📡 OpenRouter 免费模型数据库，每日自动更新。

## 文件说明

| 文件 | 说明 |
|------|------|
| `models-global.json` | 所有免费模型（Prompt 价格 = 0） |
| `models-cn.json` | 国内可访问的免费模型（已移除 Google/OpenAI/Anthropic 等） |
| `fetch_models.py` | 数据抓取脚本（供 cron 调用） |

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

每日 12:00 (UTC+8) 通过 GitHub Actions 自动运行 `fetch_models.py` 并提交更新。

如需手动更新：
```bash
python3 fetch_models.py
git add models-global.json models-cn.json
git commit -m "Update free models $(date +%Y-%m-%d)"
git push
```