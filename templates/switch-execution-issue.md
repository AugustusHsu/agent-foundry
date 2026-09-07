---
title: 模型 profile 切換：{{previous_active}} → {{profile}}（{{applied_date}}）
---

# 切換執行單模板

> **這一份不是給人手填的。** 它由 `tools/model-routing/apply_profile.py --create-issue`
> 讀進去機械填寫，產出的是**一張工單的描述欄**，不是一份 repo 文件。要改切換執行單長什麼樣
> 就改這一份——工具那邊不留第二份拷貝，改了會漂。
>
> **三個給工具讀的形狀，動了會壞**：
>
> - frontmatter 的 `title:` 那一行＝新單標題。其餘 frontmatter 欄位工具不讀。
> - 名為 `FOUNDRY:ISSUE-BODY` 的那一行 HTML 註解**以下**才是工單描述；以上（含本說明段）
>   不會進工單。⚠️ 本說明段刻意不把那串標記原樣寫出來——工具是切**第一次**出現的位置，
>   說明段裡多一份就會把自己也切進工單描述裡。
> - 佔位符一律 `{{名稱}}`。工具填完會斷言一個都不剩：漏掉一個是**報錯**，不是把 `{{…}}`
>   原樣送上平台。
>
> **為什麼工具開出來的單一開出來就是 `done`**：它是**已經發生過的事**的稽核紀錄——套用與逐角色
> 回查都在開單之前跑完了，下方每一條驗收標準在開單當下就已成立。開成 `todo` 會多喚醒一個 agent
> 去做一件做完的事，那是純付費空轉。
>
> **鏡像義務刻意不寫成下方的驗收標準**：新單開出來的那一刻鏡像還不存在，把它列成 AC 等於開一張
> 自帶未達成 AC 的 `done` 單。工具改為建單後把 `skills/foundry-platform/adapters/github.md`
> 時機 1＋時機 3 的步驟印出來，由執行者接著做完。

<!-- FOUNDRY:ISSUE-BODY -->
**Inputs**

- 套用的 profile：`{{profile}}`（切換前 active：`{{previous_active}}`）
- profile 內容的唯一真相：`.foundry/config.yml` 的 `model_routing.profiles.{{profile}}`
- 授權依據：`skills/foundry-protocol/SKILL.md` 第 8 節 `M6` **第 1 級**（已核可 profile 之間的整批切換，常設授權；本次 profile 內容一字未改，改了就不是第 1 級）
- 供應商 → adapterType 登記表：`tools/model-routing/probe_providers.py` 的 `PROVIDERS`
- 執行者：{{executor}}（agent `{{executor_agent_id}}`）；執行時間：{{applied_at}}

**上游**：{{parent}}——本單是該單觸發的這一次切換的稽核紀錄。上游就是上位單，所以依 protocol 第 1 節 `I2` 上游那一欄的第二條路寫在描述裡，**不填進依賴欄**：把母單掛成自己的 blocker 會做出一張醒不來的單。

**Outputs**

- `.foundry/config.yml` 的 `model_routing.active` ＝ `{{profile}}`（工具只換這個指標）
- 平台側 {{role_count}} 名 agent 的 `adapterType` 與 `adapterConfig` 已與 `{{profile}}` 一致
- 本單描述下半段的執行報告：切換前後逐角色對照、逐角色回查證據、回退指令、套用當下的 waiver 現況

**驗收標準**

1. 跑 `python3 tools/model-routing/apply_profile.py --check`，exit 0（平台實況與 active profile 逐格一致）。有任何一格不符它會印出差異表並 exit 1；exit 3 是第三態「讀不到平台實況」，那代表這條 AC **還沒被驗過**，不是驗過了不合格——換 CEO 或使用者的 board 金鑰重跑。
2. `git show HEAD:.foundry/config.yml` 裡 `model_routing.active` 的值為 `{{profile}}`。
3. 本單描述「## 逐角色回查」底下共 {{role_count}} 個 `### 回查：<角色>` 小節，每節三列（`adapterType`、`adapterConfig.model`、以及該 adapter 真正消費的 effort 鍵——`claude_local` 是 `adapterConfig.effort`、`codex_local` 是 `adapterConfig.modelReasoningEffort`，權威在 `probe_providers.PROVIDERS` 的 `effort_key`）的「結果」欄全為 ✅。任一列是 ❌ 時工具會停在那個角色、不續套下一個，所以出現 ❌ 就代表這次切換沒跑完。
4. 把「## 回退」段那一行指令原樣執行後，`--check` 會再度 exit 0；本次的回退指令是 `{{rollback}}`。
5. 跑 `python3 tools/foundry-lint/foundry_lint.py --selfcheck`，`model-routing-sync` 那一項為 ✅（active 指標指到已登記 profile、角色名在 `.foundry/org.yml` 值域內、供應商在登記表內）。⚠️ 這一項**只驗 repo 內宣告的自洽性**，它綠不代表平台對得上——平台那一半歸第 1 條。

**未決事項**

{{open_questions}}

---

{{report}}
