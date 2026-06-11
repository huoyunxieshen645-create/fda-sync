# FDA Data Sync — CLAUDE.md

## 项目概述

每天从 FDA 自动拉取制药相关的 483 和 Warning Letter 数据，通过 GitHub Actions 运行（国外 IP 绕过 Akamai 拦截），结构化后入库 `knowledge_v2.db`，可发公众号文章。

## 目录结构

```
.github/scripts/
├── fetch_483_pdfs.py       # 下载 483 PDF（链接写死，无增量入口）
├── fetch_warning_letters.py # 抓取制药相关 WL（增量）
├── update_db.py             # 合并数据为 fda_combined.json
├── scan_foia_page.py        # 扫描 OII FOIA 页面找新入口（目前无效）
.github/workflows/fda-sync.yml  # Actions 定义
data/                           # 输出：PDF + JSON + 去重记录
CLAUDE.md                       # 本文件
```

## 处理流程

```
GitHub Actions (UTC 8:00 + push + 手动触发)
  ├── scan OII FOIA 页面（找新入口，目前 Akamai 拦截）
  ├── fetch 17 个已知 483 PDF（写死链接，不增量）
  ├── fetch WL 列表 → 筛选制药 → 下载正文 → 合并
  └── commit data/ 回仓库
        │
        ▼
Termux: python3 ~/sync_from_github.py → knowledge_v2.db
        │
        ▼
Termux: python3 ~/fda_to_wechat.py --case-id N --url U --appsecret S → 微信公众号草稿
```

## 本地脚本

### sync_from_github.py
从 GitHub raw 拉 `data/fda_combined.json` 入库 `knowledge_v2.db`。
用法: `python3 ~/sync_from_github.py`

### fda_to_wechat.py
从 case 或 URL 生成公众号文章并发布到微信草稿箱。
用法:
```bash
# 从数据库 case
python3 ~/fda_to_wechat.py --case-id 42 --appsecret '***'

# 从本地文件（WL 正文）
python3 ~/fda_to_wechat.py --url file:///path/to/wl_text.txt --appsecret '***'

# 不发公众号只看效果
python3 ~/fda_to_wechat.py --case-id 42 --no-upload
```

---

## 已知报错 & 修复

### 1. Found 0 violations / IndexError: list index out of range
**原因**: `fda_to_wechat.py` 的 `extract_info()` fallback 没匹配到违规编号。
**以下为已修好的场景**：
- **raw_text 是无换行的纯文本**（WL 从 JSON 提取）：`re.split(r'\n\s*(?=\d+\.\s)', text)` 不匹配。修复：新增 inline fallback `re.split(r'(?=\b\d+\.\s*(?:Failure|Your|You|The|In))', text)`
- **raw_text 是 JSON 字符串**（case raw_text 里存的是 `{"full_text": "..."}`）：传给 extract_info 时已经是 JSON 字符串而非纯正文。修复：需要先将 raw_text parse 出 full_text 再传
- **patch 时反斜杠被双重转义**：`r'\\d+'` 在 Python 里是字面量 `\\d+` 而不是正则。修复：用 `r'\d+'`

### 2. content_source_url 报 41039
**原因**: 微信 API 说 `content_source_url` 无效（file:// URL 传过去了）。
**修复**: 删掉 draft_data 里的 `content_source_url` 字段（`fda_to_wechat.py:757`）。

### 3. 标题字体太大 (36px)
**原因**: 写死的 `font-size:36px` 在手机端太大。
**修复**: 改为 `font-size:22px`（`fda_to_wechat.py:436`）。

### 4. 封面图和缺陷 1 图片重复
**原因**: `~/fda_cover_0.jpg` 不存在时，代码用第一张缺陷图当封面。
**修复**: 改为 cover 不存在时单独 AI 生成封面图（`fda_to_wechat.py:625-631`）。注意：已发到草稿箱的文章图片是固定的，要重新发文才能消除重复。

### 5. fetch_483_pdfs.py 路径问题
**原因**: 脚本用 `Path("data/")` 相对路径，但从 `.github/scripts/` 目录运行时 `data/` 指向错误位置。
**修复**: 用 `REPO_ROOT = Path(__file__).resolve().parent.parent.parent` 定位到仓库根目录，再用 `REPO_ROOT / "data" / ...`。

### 6. GITHUB_TOKEN push 403
**原因**: 默认 Actions token 只有读权限。
**修复**: 
- Settings → Actions → General → Workflow permissions → Read and write permissions
- push 用 `git remote set-url origin https://x-access-token:${{ secrets.GITHUB_TOKEN }}@github.com/${{ github.repository }}`

### 7. Actions 找不到脚本文件
**原因**: 用 `defaults.run.working-directory` 或 `cd .github/scripts` 时路径错了。
**修复**: 确认文件在 git 里 `git ls-files .github/scripts/` 能看到。脚本内路径用 `REPO_ROOT` 绝对路径。

### 8. Termux 连不上 GitHub
**原因**: 中国移动/电信封 22 和 443 端口。
**修复**: 
```bash
# SSH config
Host github.com
  HostName ssh.github.com
  Port 443
  User git

# 推送时
GIT_SSH_COMMAND="ssh -p 443" git push origin main
```

### 9. FDA 页面全是 404 / 空壳
**原因**: FDA Drupal 改版 + Akamai CDN 拦截中国 ASN。
**已确认失效的入口**:
- RSS: `/contact-fda/stay-informed/rss-feeds/ora-foia-electronic-reading-room/rss.xml` → 404
- ORA 表格: `/ora-foia-electronic-reading-room` → 404
- CDER FOIA: `/drugs/cder-foia-electronic-reading-room` → 重定向到新路径（只含 Untitled Letter）
- OII FOIA: `/about-fda/.../oii-foia-electronic-reading-room` → 纯描述页，Akamai 也拦
**当前方案**: 写死 17 个已知 PDF 链接 + 每天抓 WL 增量。

---

## 常用命令速查

```bash
# Termux 拉最新数据入库
python3 ~/sync_from_github.py

# 查看数据库
python3 -c "
import sqlite3,os
c=sqlite3.connect(os.path.expanduser('~/kali-arm64/root/knowledge_v2.db'))
for r in c.execute('SELECT id,company,source_type,COALESCE(inspection_date,issued_date) FROM cases ORDER BY id DESC'):
    print(r)
"

# 发公众号文章
python3 ~/fda_to_wechat.py --case-id N --appsecret '***'

# 触发 Actions 重新跑
cd ~/fda-sync && date > .trigger && git add . && git commit -m "trigger" && GIT_SSH_COMMAND="ssh -p 443" git push origin main

# 查看 Actions 状态（无 token）
# 打开 https://github.com/huoyunxieshen645-create/fda-sync/actions
```

## 仓库信息
- **GitHub**: `github.com/huoyunxieshen645-create/fda-sync`
- **Termux 推送**: SSH over port 443 (ssh.github.com)
- **数据 raw**: `https://raw.githubusercontent.com/huoyunxieshen645-create/fda-sync/main/data/fda_combined.json`
