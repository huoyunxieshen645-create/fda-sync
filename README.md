# FDA Data Sync

每天自动从 FDA 拉取制药相关的 483 和 Warning Letter 数据。

## 数据输出

- `data/fda_combined.json` — 合并后的结构化数据
- `data/483_pdfs/` — 下载的 PDF 原文
- `data/warning_letters/` — WL 正文文本
- `data/483_download_log.json` — 下载日志

## 在你的 Termux 上拉取数据

```bash
wget -q -O ~/fda_latest.json https://raw.githubusercontent.com/{你的用户名}/fda-sync/main/data/fda_combined.json
```

然后跑个入库脚本合并到 knowledge_v2.db。
