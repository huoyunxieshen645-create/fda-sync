# FDA Data Sync — CLAUDE.md

## 项目概述

每天从 FDA 自动拉取制药相关的 483 和 Warning Letter 数据，通过 GitHub Actions 运行（国外 IP 绕过 Akamai 拦截），结构化后入库 `knowledge_v2.db`。

## 目录结构

```
.github/scripts/
├── fetch_483_pdfs.py       # 下载 483 PDF（链接写死，无增量入口）
├── fetch_warning_letters.py # 抓取制药相关 WL（增量）
├── update_db.py             # 合并数据为 fda_combined.json
├── scan_foia_page.py        # 扫描 OII FOIA 页面找新入口
workflows/fda-sync.yml       # Actions 定义
data/                        # 输出：PDF + JSON + 去重记录
```

## 处理流程

```
GitHub Actions (UTC 8:00)
  ├── scan OII FOIA 页面（找新入口，目前无效）
  ├── fetch 17 个已知 483 PDF（写死的，不增量）
  ├── fetch WL 列表 → 筛选制药 → 下载正文 → 合并
  └── commit data/ 回仓库
        │
        ▼
Termux: python3 ~/sync_from_github.py → knowledge_v2.db
```

## 已知问题

### 483 无增量入口（2026-06-11 起）
- RSS feed（`/ora-foia-electronic-reading-room/rss.xml`）→ 404
- ORA FOIA 表格页（`/ora-foia-electronic-reading-room`）→ 404
- 新 OII FOIA 页面（`/about-fda/.../oii-foia-electronic-reading-room`）→ 纯描述页，被 Akamai 全局拦截
- 替代方案写在 skill `fda-483-china` 里

### Akamai 拦截
- 中国移动/电信 ASN 被 Akamai 在 CDN 层封禁
- 即使在 GitHub Actions（AWS 美国 IP）上，OII FOIA 页面也返回空壳
- 普通 /media/NNN/download 路径可用

### Actions 注意事项
- 必须手动在 Settings → Actions → General 开启 **Read and write permissions**
- push 触发需要 `GITHUB_TOKEN` + `x-access-token` 方式
- Node.js 20 deprecation 警告无害

## 常用命令

```bash
# Termux 拉最新数据入库
python3 ~/sync_from_github.py

# 手动查看数据库
python3 -c "import sqlite3;c=sqlite3.connect('~/kali-arm64/root/knowledge_v2.db');[print(r) for r in c.execute('SELECT company,source_type,issued_date FROM cases ORDER BY id DESC')]"

# 触发 Actions 重新跑
cd ~/fda-sync && date > .trigger && git add . && git commit -m "trigger" && GIT_SSH_COMMAND="ssh -p 443" git push origin main
```

## 仓库
- GitHub: `github.com/huoyunxieshen645-create/fda-sync`
- Termux 推送: SSH over port 443 (ssh.github.com)
- 数据: `data/fda_combined.json` (raw 可拉)
