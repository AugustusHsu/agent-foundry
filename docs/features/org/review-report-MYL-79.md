# 審查報告：MYL-79 T7 規則層回填（PM 落地、`O4` 暫代條款、`org.yml` 權限來源註記）

| 欄位 | 值 |
| --- | --- |
| 工單 | MYL-79（審查單 MYL-95） |
| 分支 | `myl-79-t7-platform-apply`（tip `6d6bb32`，`git ls-remote` 實查與本地一致） |
| 審查範圍 | `main...HEAD` 共 10 檔、+144/-33，三顆 commit `866537c`／`8416f66`／`6d6bb32`。第 2 輪新增的是 `6d6bb32`（5 檔、+33/-20） |
| 審查者 | Code Reviewer |
| 日期 | 2026-09-06 |
| 輪次 | 第 2 輪（第 1 輪 ❌ CHANGES REQUESTED，報告見 MYL-95 留言 `957e5546`） |

平台側（建 PM、授權、掛 skill）依工單描述不在本單審查範圍。

## 0. 機械層（第 1 層）

| 項目 | 結果 |
| --- | --- |
| `make check` | **exit 0**（隔離 clone 實跑：`--selfcheck` 13 ✅ ＋ `mirror-recon` ⏭，200＋15＋34＋107 測試全過） |
| `--selfcheck`（真 workspace） | **14 項全綠**，`mirror-recon` 在此實際執行並通過（來源端 39 張、鏡像端 27 張）。clone 側的 ⏭ 是沒有真 remote 所致，非缺陷 |
| 夾帶檔案 | 無。`6d6bb32` 恰為宣稱的 5 檔 |
| commit 訊息 | gitmoji ＋繁體中文標題，合格 |

## 1. 七項退件逐項複審

判準：**不採信對方的敘述與表格**，每一項自己重打 API／重跑突變。

| # | 位置 | 結果 | 我自己的證據 |
| --- | --- | --- | --- |
| 1 | `SKILL.md:596`／`:598` | ✅ | `rule-marks` 覆蓋：main **26** → 分支 **27**。六發突變見下表 |
| 2 | `org.yml:22-27` | ✅ | `GET /api/agents/{id}` 逐名撈：`taskAssignSource` 計數 `{ceo_role:1, explicit_grant:1, none:6, simple_default:1}` ⇒ CEO／PM 以外 7 名確為 **6 個 `none` ＋ FV `simple_default`**。`access` 物件的欄位聯集是 `[canAssignTasks, grants, membership, taskAssignSource]`——**確實沒有 `canCreateSkills`**；9 名 `permissions.canCreateSkills` 全 `true` |
| 3 | `org.yml:52-57`／`:86-89` | ✅ | grant `c30a19e3` = `permissionKey: tasks:assign`、`grantedByUserId: ntx8Ty4MWI7KU8edugyZTyrsTkJLekTH`。全公司 4 條 grant 中**唯一** granter 非 null 的一條，與新文字逐字相符。PM 的 `41fd8b90` 確為 `grantedByUserId: null` ＋ `explicit_grant` |
| 4 | `paperclip.md:223`／`:229`／`:344` | ✅ | CEO 平台 `title` 現為 `'CEO'`。9 名逐一比對宣告 `title` ↔ 平台 `title`，**只有 `Developer` ↔ `Developer（全端）` 分岔** ⇒「差異剩一項」成立、「其餘 6 個角色三欄一致」成立。附錄 B `:344` 第二份副本已同步 |
| 5 | `known-drift` `L24` | ✅ | `GET /api/openapi.json`：`PATCH /api/agents/{id}/permissions` 的 `properties` 恰為 5 個、`required` 恰為 `[canCreateAgents, canAssignTasks]`、`trustPreset` enum 恰為 `[standard, low_trust_review]`、`authorizationPolicy` 子欄位恰為文中列的 5 個。**另外查證了條目引用的路徑名**：`…/members/{memberId}/role-and-grants` 確實存在於 spec，且對我回 **403**（見次要建議 3），`board-only` 宣稱成立 |
| 6 | `known-drift` `S5` | ✅ | 現象欄／正解欄方向已對調正確、422 前提已補在正解欄開頭。**歸屬查核**：條目寫「2026-09-06 MYL-95 覆驗；該路徑是原子的，同批送的 `priority` 也沒寫進去」——我撈回自己第 1 輪報告原文比對，這確實是我做過並寫下的實測，**非虛構歸屬**。表格欄數：全檔 3 個表、**0 列**與表頭不符（`8416f66` 那列 4 格已併回 3 格） |
| 7 | `06-org-structure.md:69`／`:71`、`org.yml:12-13` | ✅ | 過度宣稱已收斂為「除一處刻意保留的例外外」。FV 旗標狀態實查：`access.canAssignTasks: true`／`permissions.canAssignTasks: false`，與手冊「平台上這個旗標解出來是開的」相符。「只有你動得了」一半經我實測背書（見次要建議 2） |

### 瑕疵 1 的突變組（前兩發重跑對方的，後四發是對方沒跑過的）

在 `clone --shared` 的隔離副本操作，每發都斷言「改後字串必須與改前不同」，避免退化成 no-op。

| # | 突變 | `rule-marks` | 判定 |
| --- | --- | --- | --- |
| 基準 | 無 | ✅ 27 行違反段 | — |
| A | 拿掉 `:596` 的 `【自律】` | ❌ 指名 `SKILL.md:596（決策權矩陣）` | 擋得住 |
| B | 拿掉 `:598` 的 `【自律】` | ❌ 指名 `SKILL.md:598（決策權矩陣）` | 擋得住 |
| C | `:596` 標記順序顛倒為 `【機械】＋【自律】` | ❌ 指名不是合法字面 | 擋得住 |
| D | `:598` 換成第三種值 `【半機械】` | ❌ 指名不是合法字面 | 擋得住 |
| **E** | **`:596` 還原成第 1 輪的行首界定詞寫法** | **✅ 綠，但覆蓋 27 → 26** | **重現原缺陷** |
| **F** | **`:598` 還原成第 1 輪的行首界定詞寫法** | **✅ 綠，但覆蓋 27 → 26** | **重現原缺陷** |

E／F 是決定性的兩發：它們把每一行對覆蓋的貢獻**單獨隔離**出來，證明 27 這個數字確實來自這兩行回到覆蓋內，而不是別處的巧合；同時精確重現了第 1 輪「檢查照樣綠、覆蓋卻悄悄少兩段」的失效形態。

### 對方自行追加的兩處，我一併核了

- **`8416f66` 遺留的 4 格表列**（對方自己抓到、我第 1 輪漏掉）：確認已併回 3 格，且全檔 0 處欄數不符。這是真缺陷——多出來的那格裝著整個正解欄，渲染時**靜默丟掉**，與 `L13`／`L21` 同族。
- **搭便車訂正 `canCreateSkills` 的來源**（`org.yml:24-27`）：**訂正正確且必要**。原文「讀 `access.*`，不讀面板的 `permissions.*`」緊接著報告一個 `access.*` 裡根本不存在的欄位，是自我否定；新文字把「會相反」限縮到 `canAssignTasks` 並附 FV 實例，我逐欄實查全部相符。

## 2. 四維檢查

- **正確性**：無發現。第 1 輪的七項事實錯誤全部消除，且**每一項的替代敘述我都重新實測過**，不是確認對方改了字。
- **規格符合度**：`rule-marks` 覆蓋回到 27（＝main 的 26 ＋ `O4` 新增的一段），機械後盾恢復完整。`O4` 條文本體仍忠於使用者核可原文（第 1 輪已逐字比對，本輪未動）。
- **安全性**：無發現。本輪 5 檔皆為敘述性文字與 YAML 註解，無可執行路徑變更；無機敏資料落地（grant id 與 `grantedByUserId` 屬公司內部識別碼，且原已存在於 repo 體例中）。
- **可維護性**：無發現。第 1 輪確認的測試分層（可攜 vs 規則本體專屬）本輪未動；三項超範圍改進已明確回報 Scrum Master 開新單，未夾帶。

## 3. 重大瑕疵清單

**無。** 七項全數修正並經獨立覆驗。

## 4. 次要建議（不擋結案）

1. **兩份文件各自宣稱「只剩一項」，但指的不是同一項。** `org.yml:12-13` 說「除 FV 的 `canAssignTasks` 外其餘逐格一致」，同一分支的 `paperclip.md:230` 說 `Developer` 的顯示名分岔「**這是現在唯一剩下的那一項差異**」。兩者**不矛盾**——`config-schema.md:239` 定義 `org.yml` 的 `title` 對接的是 protocol 第 9 節組織圖節點名（非平台顯示名），而 §8.2 對帳鍵是平台 `name`，Developer 的判定確為 ✅——但讀者要跨三份文件才能推出這一點。建議在 `org.yml` 那句補一個指向 §8.2「第五種差異」的括號。
2. **`06:71`「能真正清乾淨的設定點只有你（在面板上）動得了」的兩半證據強度不同。** 「只有你」這一半我實測背書：agent 身分對 `PATCH …/members/{id}/permissions` 與 `…/role-and-grants` **兩支都回 403**，`GET …/members` 亦 403。但「面板做得到」那一半仍是推論，沒有人示範過——而且**只有使用者驗得到**，不該要求交付者補。建議措辭把已驗證的那半與推論的那半分開講。
3. **本 repo 的 `L22` 授權推論技法在這支端點上會給出假陽性，值得另立條目。** `L22` 立下的判準是「回驗證錯誤而非 403 ＝ 授權通過」。我照這個技法探 `role-and-grants`：送 `{"__invalid__":1}` 回 **400**、送 `{"grants":[]}` 回 **400 要我補 `membershipRole or status`**——照 `L22` 讀會結論「授權通過、不是 board-only」。但送**完整**合法 body（`{"membershipRole":"viewer","grants":[]}`）就回 **403**：這支端點的 **body 驗證跑在授權檢查之前**。⇒ 用驗證錯誤反推授權時，**必須送到完整合法 body 才算數**。這條會影響日後所有沿用該技法的判斷，建議開單收進 known-drift（與次要建議 1、2 及對方回報的三項一併交 Scrum Master）。

以上皆超出本單範圍，不影響 Verdict。

## 5. 分支收尾檢查

- **分支狀態：待合併。** 依 protocol `:322`，掛有審查單的分支在 APPROVED 後才合併 main——本報告即該條件。合併由 MYL-79 承接。
- **合併後仍有義務未了**（不由本單認定完成）：
  - `docs/handbook/06`／`07` 兩章有**實質內容變更**（非僅推戳記）⇒ 須走 protocol 第 7 節手冊發佈四步，並用 `templates/publish-review.md` 寫審查記錄、`handbook_commit` 填實際 sha。
  - **兩件已知證據缺口**，雙方同意不作為退件條件、交接到後續：`L25` 的 `runtimeConfig`（`/configuration` 對我 403、`GET agents/{id}` 一律回 `{}` ⇒ 單人觀測）與 `S5` 的 (a)(c) 兩發（需一張 `blocked` 單，唯一那張是 MYL-79 本身，依 `L23` 不拿在途工單試）。**我同意這個處置**：補驗的正確時機是下次有人建 agent／出現第二張 `blocked` 單時順手做，而不是為了讓我簽得下去去製造可驗環境。
  - AC6（6 名 `runtimeConfig` 補齊）依使用者未答、按 C＝不做，本輪維持。

## Verdict

**✅ APPROVED**
