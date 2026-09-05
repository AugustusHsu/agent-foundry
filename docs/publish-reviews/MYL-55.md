---
issue: MYL-55
verdict: APPROVED
handbook_commit: 1f1a2d73cc2fa5db7d4b3e0afaf512ea137d6c3a
reviewer: Developer
reviewed_at: 2026-09-05
---

# 發佈審查記錄：MYL-55 精裝站轉可選：tag 觸發 CI ＋ mike 版本化 ＋ Pages 遷回本 repo

## 1. 變更範圍

手冊五章隨 protocol 第 7 節的「第五步」一起改：發佈流程從「四步、全自動」變成
「前四步全自動 ＋ 第五步（發一版精裝站）使用者專屬」，而且對外閱讀面從一個變成兩個。
`06` 只推同步戳記，內容未改。

| 項目 | 值 |
| --- | --- |
| 手冊 commit | `1f1a2d73cc2fa5db7d4b3e0afaf512ea137d6c3a` |
| 變更檔案 | `docs/handbook/02-commands.md`、`03-workflow.md`、`04-decision-points.md`、`06-org-structure.md`（戳記）、`07-workflows.md` |
| 來源工單 | MYL-55 |

## 2. P2 前提逐項自檢

| # | 前提（MYL-23 分級表 P2） | 結果 | 證據 |
| --- | --- | --- | --- |
| 1 | 來源變更已合併進私有 main | ✅ | `1f1a2d7` 經 `7e5599f`（`--no-ff` 合併）進 main，並已 `git push origin main`（`fd44711..7e5599f`）。`git log -1 --format=%H -- docs/handbook` 回 `1f1a2d7…`，與本欄 `handbook_commit` 一致 |
| 2 | 同步範圍僅限既定目錄 `docs/handbook/` | ✅ | 本單同一顆 commit 另動了 protocol、entry 檔、lint、腳本與 CI，但**投影範圍**只有 `docs/handbook/`：`site_docs.build()` 與 `project_docs.project()` 的來源都是 `docs/handbook/*.md`，沒有第二個來源目錄。閘門比對的也是 `git log -1 -- docs/handbook` |
| 3 | 私有連結改寫輸出檢查無異常 | ✅ | `python3 tools/publish-docs/site_docs.py build` 逐章比對全綠（9 章）；抽驗 `07-workflows.md` 三條 `../../skills/…` 相對連結全部改寫成 `https://github.com/AugustusHsu/agent-foundry/blob/main/…`（`link_policy: absolute`，repo 為 public，實測 `private: false`） |

## 3. 公開適切性檢查

- **機敏資訊**：無。新增內容只講發佈流程與關卡歸屬，沒有憑證、內部網址或個資。
- **內部路徑與代號**：新增段落提到 `.foundry/config.yml`、`scripts/publish-wiki.sh`、
  `handbook-v<N>`。repo 是 public，`link_policy: absolute` 讓這些路徑成為可點的
  github.com 連結，對外部讀者讀得通——這正是搬回本 repo 之後多出來的好處（原本要拆成純文字）。
- **連結可達性**：新增的章間連結只有 `03`／`04`／`07` 互指與指向 `02`／`05`，
  皆為既有章節；`--selfcheck` 的 `internal-links`（64 條）與 `anchors`（9 條）全綠。
  ⚠️ 一項**本機驗不了**的殘留：站台實際渲染出來的錨點字串（`X4`：本機沒有 markdown／mkdocs）。
  精裝站與來源同為 Python-Markdown，理論上一致，但**第一次發佈後仍要在實站點一遍**才算驗過。

## 4. 未通過項目

無。

## Verdict

**✅ APPROVED**
