# scripts/

維護用的工具腳本 + distribution build。

## `check-links.py` — 檢查連結是否失效

掃描所有 markdown 檔案中的 URL，回報 4xx / 5xx / timeout。

```bash
# 一次性檢查全部
python scripts/check-links.py

# 只查 GitHub repos（最容易 404 的）
python scripts/check-links.py --fast

# 只印失敗，不印 OK
python scripts/check-links.py --quiet
```

退出 code：失敗時 = 1，全部 OK = 0。可以接 CI。

依賴：`pip install requests`

## `refresh-stars.py` — 比對 markdown 內標註的 stars 跟實際

```bash
# 列出所有差距 ≥ 10% 的 entry
python scripts/refresh-stars.py

# 設定門檻（譬如 ≥ 20%）
python scripts/refresh-stars.py --threshold 20

# CI 模式（差距超過門檻就退 code 1）
python scripts/refresh-stars.py --check
```

依賴：`pip install requests` + `gh` CLI（`gh auth login`）

## `check-catalog-staleness.py` — 找出 dormant / archived 的 catalog entry

`refresh-stars.py` 把星數刷新但不會告訴你哪些 repo 是「殭屍 entry」——一年沒 push、或被
upstream archived。本 script 對 catalog 內每個 GitHub repo 查 `pushed_at` + `archived`、
flag 超過門檻或已 archived 的 entry。**Report-only、不改 markdown**（鏡像
`weekly-catalog-refresh` 「broken link → 開 issue 不自動修」的做法、留人工 judgment）。

```bash
# 預設門檻 12 個月、輸出 plain text
python scripts/check-catalog-staleness.py

# 調門檻（譬如 18 個月以上才算 stale）
python scripts/check-catalog-staleness.py --months 18

# 只看已 archived 的（最 actionable、最該優先處理）
python scripts/check-catalog-staleness.py --include-archived-only

# Markdown 輸出，直接 `gh issue create --body-file -` 開 issue
python scripts/check-catalog-staleness.py --format markdown | gh issue create \
  --title "Catalog staleness report — $(date +%F)" --body-file -

# JSON 輸出（給後續 tooling / dashboard 用）
python scripts/check-catalog-staleness.py --format json

# CI 模式（找到 stale 就 exit 1）
python scripts/check-catalog-staleness.py --check
```

每個 stale entry 報告：repo / archived 或月數 / 最後 push 日期 / star / 出現位置。Maintainer
依下面 4 種行動決策：

1. **Archived 但教學價值還在** → 保留、note 加 `⚠️ Archived (YYYY-MM)`。
2. **沉睡但有 fork / rename 接手** → 改 URL、可選註原本。
3. **沉睡且有替代品** → 換掉、或留作 "historical reference"。
4. **沉睡但無可取代** → 留著、不必註記。

依賴：`gh` CLI（`gh auth login`）

## `snapshot-traffic.py` — 每週把 traffic 14-day window 留檔

`gh api repos/<repo>/traffic/views`（跟 clones）只回**最近 14 天**、過了就抓不回來。
本 script 抓 14-day rolling totals + 每日明細 + top referrers + top paths + 點時間 totals
（stars/forks/open_issues/subscribers）、寫到 `docs/traffic/snapshots/YYYY-MM-DD.json`。
每檔 ~5 KB。

```bash
# 寫今天的 snapshot
python scripts/snapshot-traffic.py

# 試跑印 JSON 不寫
python scripts/snapshot-traffic.py --dry-run

# 自訂位置（譬如 CI artifact）
python scripts/snapshot-traffic.py --out /tmp/traffic.json
```

需要對 repo 有 push 權限（traffic API 限制）。詳見 `docs/traffic/README.md`。

依賴：`gh` CLI（`gh auth login`）

## `refresh-outreach-status.py` — 偵測 outreach matrix 跟 live PR 狀態落差

`.github/channel-partners.md` 手寫紀錄每個 outreach、但 PR 狀態會老化（送出去的 PR 可能
merged / closed / 沉了你還沒注意到）。本 script 讀 matrix、抽所有 PR URL、跑 `gh pr view`、
跟記錄狀態對比、報告 drift。**Report-only**、不改 markdown。

```bash
# 預設報告
python scripts/refresh-outreach-status.py

# 調 ghost threshold（OPEN PR 超過 N 天沒動就建議標 ghosted）
python scripts/refresh-outreach-status.py --ghost-days 21

# Markdown 輸出，pipe 給 gh issue create
python scripts/refresh-outreach-status.py --format markdown | gh issue create \
  --title "Outreach drift — $(date +%F)" --body-file -

# CI 模式（有 drift 就 exit 1）
python scripts/refresh-outreach-status.py --check
```

判斷規則（保守 V1、只 auto-flag 不會誤判的）：
- PR `merged: true` → 建議改 `merged-or-listed`（UPDATE）
- PR `state: CLOSED` 沒 merge → 標 REVIEW（判斷是 declined 還是 abandoned）
- PR `state: OPEN` 且 reviewer `APPROVED` 卻沒 merge → 標 REVIEW（建議改 `replied-positive`）
- PR `state: OPEN` 超過 `--ghost-days` 沒更新 → 標 REVIEW（建議改 `ghosted`）

依賴：`gh` CLI（`gh auth login`）

## 建議的維護節奏

- **每月**：跑一次 `check-links.py --fast` 看 GitHub repo 連結有沒有 404
- **每月**：跑一次 `check-catalog-staleness.py --include-archived-only` 揪剛 archived 的 entry
- **每週**：跑一次 `snapshot-traffic.py` 留 traffic 歷史（一週一檔、檔小）
- **每週**：跑一次 `refresh-outreach-status.py --check` 看 outreach matrix 有沒有 stale
- **每季**：跑一次 `refresh-stars.py` 看大幅成長 / 衰退的 repo
- **每季**：跑一次 `check-catalog-staleness.py` 全量 dormant 盤點
- **每半年**：跑一次完整 `check-links.py`（包含非 GitHub 連結）

可以接到 GitHub Actions 自動跑（見未來 Phase 6 的 CI 設定）。

---

## `build-pdf.sh` — 編譯成單一 PDF

```bash
bash scripts/build-pdf.sh                  # zh-TW 版（預設）
LANG_VARIANT=en bash scripts/build-pdf.sh  # 英文版
```

輸出：`dist/awesome-agentic-ai-zh.pdf`（或 `.en.pdf`）

依賴：
- `pandoc` (>= 3.0)
- `xelatex`（TeX Live with CJK support）
- **CJK 字型**：`Noto Sans CJK TC`（zh-TW + en 共用——en 版也需要，因為章節標題仍含中文）
- **西文字型**：`DejaVu Sans`

### 安裝指令

**macOS**：
```bash
brew install pandoc
brew install --cask mactex-no-gui          # TeX Live + xelatex
brew install --cask font-noto-sans-cjk-tc  # CJK 字型
brew install --cask font-dejavu            # 西文字型
```

**Linux (Debian / Ubuntu)**：
```bash
sudo apt install pandoc texlive-xetex texlive-lang-chinese \
                 fonts-noto-cjk fonts-dejavu
```

**Windows**：
```powershell
choco install pandoc miktex
# 然後手動裝字型：
# Noto Sans CJK TC: https://fonts.google.com/noto/specimen/Noto+Sans+TC
# DejaVu Sans: https://dejavu-fonts.github.io/
```

### 換字型

如果上面的字型沒有，可以改用系統內建的：

```bash
# macOS（已內建 PingFang）
CJK_FONT="PingFang TC" bash scripts/build-pdf.sh
# Windows（已內建 Microsoft JhengHei）
CJK_FONT="Microsoft JhengHei" bash scripts/build-pdf.sh
```

兩個字型 env var 都支援：`CJK_FONT` 跟 `MAIN_FONT`。

**Mermaid 圖**：目前 build-pdf.sh 會把 ` ```mermaid` 退化成普通 code block。要 render 圖需要另外裝 `pandoc-mermaid` filter（複雜度高，預設跳過）。

## `build-mdbook.sh` — 建可瀏覽的網站版

```bash
bash scripts/build-mdbook.sh           # 建到 book/dist/
bash scripts/build-mdbook.sh --serve   # 建好後本機開 server (port 3000)
```

依賴：
- Rust + cargo（[rustup.rs](https://rustup.rs)）
- `cargo install mdbook mdbook-mermaid`
- 第一次跑前：`mdbook-mermaid install .`（會生成 `mermaid.min.js`、`mermaid-init.js`，工作流需要）

**自動部署**：
推 main branch 時，[`.github/workflows/docs.yml`](../.github/workflows/docs.yml) 會自動 build mkdocs 站（`/` 首頁）+ mdBook（`/book/`）並 deploy 到 GitHub Pages。單一 workflow 擁有 Pages（兩個 workflow 各自 deploy 會互搶同一個 root，故已合併、刪除舊的 `deploy-book.yml`）。
要啟用，去 Settings → Pages → Source: GitHub Actions。

## 整體 Phase 5 deploy 流程

1. 推 main → `docs.yml` 自動 build mkdocs（`/` 首頁）+ mdBook（`/book/`）並 deploy 到 `https://wenyuchiou.github.io/awesome-agentic-ai-zh/`
2. PDF：手動跑 `bash scripts/build-pdf.sh`，把 `dist/*.pdf` 上傳到 GitHub Release（或自動化 release workflow，TBD）
