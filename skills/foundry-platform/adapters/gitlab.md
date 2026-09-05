# adapter：gitlab

`devtools_platform: gitlab` 時的動詞對照。介面語意見 `../SKILL.md`，本文只翻譯成具體指令。
本檔同時是文檔投影宿主（`publish_docs`，見下方同名一節），兩個身分互相獨立——
`docs` 段選那一節，`devtools_platform` 選這一節，一個專案可以只用其中一邊（`../SKILL.md` §5）。

⚠️ **讀本文前先看附錄 B 的查證狀態。** 本 repo **沒有 GitLab 實例**，本文的指令分三個
證據等級（來源專案實測／官方 API 文件／版本分岔推定），附錄 B 逐條標明是哪一級。
把「照文件寫得出來」當成「驗過」，是本文最容易造成的傷害。

**怎麼讀**（本檔超過 20KB，依 `C1` 不要整份載入）：任何一次使用都先讀「前置條件」與
「版本分岔」兩節——後者決定四個動詞走哪條路；再跳到你要用的那一個動詞。
要做文檔投影就只讀 `publish_docs` 那一節，執行層動詞全部可以跳過（反之亦然）。

ℹ️ **本 adapter 沒有「鏡像模式」一節**，所以 `mirror_platform: gitlab` 依
`../config-schema.md` 的合法性規則**不合法**——那一節要另外定義三個時機、對應標記與對帳欄位，
目前只有 `adapters/github.md` 有。這是刻意的缺，不是漏寫：沒有規格就自行推導一套出來，
得到的會是兩邊都對不上的鏡像。`devtools_platform: gitlab`（執行層）與 `docs` 指向 gitlab（文檔面）
都不受這一條影響。

## 前置條件

- **實例 URL 與專案路徑**：GitLab 不像 GitHub 只有一個 `github.com`——自架實例遍地都是，
  所以每一條指令都要顯式帶實例位址，不能靠 CLI 猜。
  ```sh
  export GITLAB_URL="https://gitlab.example.com"      # 自架實例填自己的
  export GITLAB_PROJECT="group/subgroup/project"       # 完整命名空間路徑
  export GITLAB_TOKEN="glpat-…"                        # PAT，scope: api（唯讀動詞 read_api 即可）
  # 專案路徑要整段 URL-encode（斜線變 %2F），API base 因此固定長這樣：
  export GL_API="${GITLAB_URL}/api/v4/projects/$(printf '%s' "$GITLAB_PROJECT" | jq -sRr @uri)"
  export GL_AUTH="PRIVATE-TOKEN: ${GITLAB_TOKEN}"
  ```
- `curl` 與 `jq` 可用。
- **`glab` CLI 是選配，本文不依賴它**。理由有二：自架實例要另外 `glab auth login --hostname`，
  而 REST v4 一條 `curl` 就到；且 `glab` 未必裝得到（撰寫本文的機器就沒有）。
  裝了 `glab` 的人可以用它取代下面的 `curl`，但**查證仍以本文的 API 回傳為準**。
- **不要用 `git remote` 判斷平台。** 來源專案 SuperOD 的正本在自架 GitLab、本機 clone 的
  `origin` 卻指向 GitHub 鏡像——照 remote 判會判成 github。平台一律讀 `.foundry/config.yml`
  的 `devtools_platform`（`../SKILL.md` §1 第 5 點）。
- **佔位符慣例**：`<IID>`＝issue 在專案內的編號（`#12` 的 `12`）、`<MID>`＝milestone 的數字 id、
  `<BID>`＝board 的數字 id。GitLab 的 issue 有兩個編號，本文一律用 `iid`，理由見附錄 A。

## 版本分岔：本文最需要先確認的一件事

GitLab 的**方案等級（Free／Premium／Ultimate）決定四個動詞怎麼走**。先查一次，寫進工單，
之後照著分岔走；不要每次臨場猜：

```sh
curl -s -H "$GL_AUTH" "${GITLAB_URL}/api/v4/version" | jq '{version, enterprise}'
# 自架 CE（enterprise: false）＝一定是 Free 路徑。EE 版另需確認實際授權等級：
curl -s -H "$GL_AUTH" "${GITLAB_URL}/api/v4/license" | jq '.plan'   # 需 admin，非 admin 回 403
```

非 admin 拿不到 `license` 時，用能力探測代替：對一張測試單試 `link_type: blocks`（見
`link_issues`），回 `404`／`403` 就走 Free 路徑。**探測結果寫進工單**，別讓下一個人再試一次。

| 動詞 | Free | Premium 以上 |
| --- | --- | --- |
| `update_status` | scoped label **不互斥**，adapter 自己 read-modify-write | scoped label 平台保證互斥 |
| `link_issues` `blocked_by` | 退回 `blocked` label ＋ `Blocked-by:` 留言慣例 | `link_type: is_blocked_by` |
| `link_issues` `parent` | 父單描述的 task list `- [ ] #<IID>` | 同左（epic 是另一種東西，見平台限制） |
| `init_structure` roadmap view | 無 roadmap，退回 milestone 清單頁 | Roadmap（epic 時間軸） |

## 動詞對照

### init_structure

1. 建標準 label。GitLab 的 `POST /labels` 在同名時回 **409**，所以冪等靠「先查再建」：

   ```sh
   existing=$(curl -s -H "$GL_AUTH" "$GL_API/labels?per_page=100" | jq -r '.[].name')
   mklabel() {  # $1=名稱 $2=色碼 $3=說明
     printf '%s\n' "$existing" | grep -qxF "$1" && return 0
     curl -s -X POST -H "$GL_AUTH" "$GL_API/labels" \
       --data-urlencode "name=$1" --data-urlencode "color=$2" --data-urlencode "description=$3" >/dev/null
   }
   for l in type:brd type:prd type:hld type:lld type:impl type:review type:test type:docs; do
     mklabel "$l" "#5319E7" "Foundry 工單類型"; done
   for l in role:product-analyst role:scrum-master role:tech-lead role:developer role:code-reviewer role:qa; do
     mklabel "$l" "#0E8A16" "Foundry 角色"; done
   for l in size:small size:medium size:large; do
     mklabel "$l" "#FBCA04" "Foundry 工單規模"; done
   # status 用 scoped label（`::`）——這是 GitLab 承載六態的方式，見 update_status
   for s in todo in_progress in_review blocked done cancelled; do
     mklabel "status::$s" "#1F75CB" "Foundry 六態"; done
   ```

   ⚠️ **色碼要帶 `#`**（`color=#5319E7`）；GitHub 的 `gh label create` 是不帶 `#` 的六碼，
   照抄過去會被 GitLab 拒收。

2. 建 milestone（查重後建）：

   ```sh
   curl -s -H "$GL_AUTH" "$GL_API/milestones?per_page=100" | jq -r '.[].title'   # 查重
   curl -s -X POST -H "$GL_AUTH" "$GL_API/milestones" \
     --data-urlencode "title=<里程碑名>" --data-urlencode "description=<說明>" \
     --data-urlencode "due_date=2026-12-31"
   ```

3. 三個 view。**這一步是 GitLab 與 GitHub 結構差最大的地方**：GitHub 要另建一個 ProjectV2
   物件再在裡面建 view；GitLab 的工單清單與看板是專案內建頁面，多數不必「建」：

   | view | GitLab 的對應 | 要做什麼 |
   | --- | --- | --- |
   | board（依 status 分欄） | 專案的 Issue Board | 專案預設已有一個 board，取它再補 list（下方指令） |
   | table（全欄位清單） | 專案的 Issues 列表頁 | **不必建**，內建頁面 `/-/issues` |
   | roadmap（依 milestone 時間軸） | Free **沒有** | 退回 milestone 清單頁 `/-/milestones`（有起訖日與 burndown）。Premium 的 Roadmap 是 epic 時間軸、不是 milestone，語意本來就不同——**別為了湊滿三個 view 去建 epic** |

   ```sh
   BID=$(curl -s -H "$GL_AUTH" "$GL_API/boards" | jq '.[0].id')   # 預設 board
   # 依六態順序建 list（每個 list 綁一個 status:: label；重複建同一 label 回 400，視為冪等成功）
   for s in todo in_progress in_review blocked done; do
     lid=$(curl -s -H "$GL_AUTH" "$GL_API/labels?search=status::$s" | jq ".[]|select(.name==\"status::$s\")|.id")
     curl -s -X POST -H "$GL_AUTH" "$GL_API/boards/$BID/lists" -d "label_id=$lid" >/dev/null
   done
   ```

   `cancelled` 刻意不建 list——board 只顯示 open issue，而 `cancelled` 已關單，建了永遠是空欄。

   ⚠️ **Free 版每專案只有一個 board**，`POST /boards` 建第二個會失敗。這不是錯誤處理的對象，
   是能力邊界：照上面取 `[0]` 就對了。

4. 裝 CI 閘門：把 `foundry-lint` 放進 `.gitlab-ci.yml`。**這是 gitlab 模式相對其他平台的實質優勢**
   （與 github 模式同性質）——關卡在多數平台靠 agent 自覺遵守，在 GitLab 上規範可以有機械執行力：

   ```yaml
   foundry-lint:
     stage: test
     image: python:3.12-slim
     script:
       - python3 tools/foundry-lint/foundry_lint.py --selfcheck
       - python3 -m unittest discover tools/foundry-lint
     rules:
       - if: $CI_PIPELINE_SOURCE == "merge_request_event"
       - if: $CI_COMMIT_BRANCH == "main"
   ```

   要讓它真的擋得住合併，還需在專案 Settings → Merge requests 勾 **Pipelines must succeed**。
   那是**改動專案保護設定**，屬使用者權限範圍，agent 不得代設；列入 init 報告待辦。
   ⚠️ 來源專案 SuperOD 刻意**關掉**這個開關（維護者自己看管線），所以「有 CI」不等於「擋得住」——
   要宣稱機械執行力，得先確認這個勾有勾。

- **查證**：`curl -s -H "$GL_AUTH" "$GL_API/labels?per_page=100" | jq '[.[]|select(.name|startswith("type:"))]|length'`
  得 8；`$GL_API/boards/$BID/lists` 列得到五個 list；重跑步驟 1–3 無報錯、無重複。

### create_issue

```sh
curl -s -X POST -H "$GL_AUTH" "$GL_API/issues" \
  --data-urlencode "title=<標題>" \
  --data-urlencode "description@<body.md>" \
  --data-urlencode "labels=<type_label>,status::todo[,<其他label>]" \
  [--data-urlencode "milestone_id=<MID>"] \
  [--data-urlencode "assignee_ids=<user id>"] | jq '{iid, web_url}'
```

- 工單內文的欄位名是 **`description`**（GitHub 叫 `body`）。
- 開單即掛 `status::todo`——GitLab 沒有獨立的 status 欄位，六態全靠 scoped label 承載。
- `assignee_ids` 要的是**數字 user id**，不是帳號名：`curl -s -H "$GL_AUTH" "${GITLAB_URL}/api/v4/users?username=<帳號>" | jq '.[0].id'`。
- **查證**：`curl -s -H "$GL_AUTH" "$GL_API/issues/<IID>" | jq '{title,labels,milestone,assignees}'` 欄位正確。

### update_status

兩件事都要做，缺一狀態就對不上。

**① 換 `status::` scoped label**：

```sh
# Premium 以上：scoped label 平台保證互斥，加新的即可，舊的自動移除
curl -s -X PUT -H "$GL_AUTH" "$GL_API/issues/<IID>" --data-urlencode "add_labels=status::<新狀態>"

# Free：不互斥，必須先讀出舊的 status:: 再顯式移除（read-modify-write）
old=$(curl -s -H "$GL_AUTH" "$GL_API/issues/<IID>" | jq -r '.labels[]|select(startswith("status::"))' | paste -sd,)
curl -s -X PUT -H "$GL_AUTH" "$GL_API/issues/<IID>" \
  --data-urlencode "remove_labels=$old" --data-urlencode "add_labels=status::<新狀態>"
```

`add_labels`／`remove_labels` 是**增量**參數，不動其他 label——符合介面「不得整批覆蓋」。
（另有一個 `labels=` 參數是**全量替換**，本文全篇不用它，用了就會把 `type:*`／`role:*` 一起洗掉。）

**② 同步開關狀態**：

```sh
curl -s -X PUT -H "$GL_AUTH" "$GL_API/issues/<IID>" -d "state_event=close"    # 進 done／cancelled
curl -s -X PUT -H "$GL_AUTH" "$GL_API/issues/<IID>" -d "state_event=reopen"   # 自 done／cancelled 離開
```

⚠️ **GitLab 的關單沒有 reason**（GitHub 有 `completed`／`not planned`）。`done` 與 `cancelled`
在平台上長得一模一樣，**唯一的區別就是 `status::` label**——所以 ① 不是裝飾，是這兩態的唯一載體。
漏做 ① 的話，`cancelled` 的單會被後續查詢當成 `done`，而且沒有任何地方會報錯。

- **查證**：`curl -s -H "$GL_AUTH" "$GL_API/issues/<IID>" | jq '{state, s:[.labels[]|select(startswith("status::"))]}'`
  ——`s` 陣列**必須恰好一個元素**。長度 2 就是 Free 版漏了 read-modify-write，這是本 adapter 最常見的錯。

### comment

```sh
curl -s -X POST -H "$GL_AUTH" "$GL_API/issues/<IID>/notes" --data-urlencode "body@<comment.md>"
```

GitLab 把留言叫 **note**。`@<檔案>` 形式可避免長內文被 shell 截斷或吃掉跳脫字元。

- **查證**：`curl -s -H "$GL_AUTH" "$GL_API/issues/<IID>/notes?sort=desc&per_page=1" | jq -r '.[0].body'`
  為剛發的留言，且**內容完整未截斷**（比對字元數，不要只看開頭）。

### set_labels

```sh
curl -s -X PUT -H "$GL_AUTH" "$GL_API/issues/<IID>" \
  --data-urlencode "add_labels=<label1>,<label2>" --data-urlencode "remove_labels=<label3>"
```

- **查證**：`curl -s -H "$GL_AUTH" "$GL_API/issues/<IID>" | jq '.labels'`——add 全在、remove 全不在。

### set_milestone

GitLab 用 milestone 的**數字 id**，不是名稱，所以永遠是兩步：

```sh
MID=$(curl -s -H "$GL_AUTH" "$GL_API/milestones?title=<里程碑名>" | jq '.[0].id')
[ -n "$MID" ] && [ "$MID" != "null" ] || { echo "milestone 不存在：<里程碑名>" >&2; exit 1; }
curl -s -X PUT -H "$GL_AUTH" "$GL_API/issues/<IID>" -d "milestone_id=$MID"   # 設定
curl -s -X PUT -H "$GL_AUTH" "$GL_API/issues/<IID>" -d "milestone_id=0"      # 移除（milestone=none）
```

上面第二行的存在性檢查**不能省**：查不到時 `MID` 是空字串或 `null`，直接送出去等於送
`milestone_id=`，GitLab 會照收並把 milestone 清掉——介面要求「不存在時報錯、不自動建立」，
少了這行就會變成「不存在時靜靜清空」，比報錯糟得多。

- **查證**：`curl -s -H "$GL_AUTH" "$GL_API/issues/<IID>" | jq -r '.milestone.title // "none"'`。

### list_issues

```sh
curl -s -H "$GL_AUTH" -G "$GL_API/issues" \
  --data-urlencode "state=all" --data-urlencode "per_page=100" \
  [--data-urlencode "labels=status::<狀態>[,<其他label>]"] \
  [--data-urlencode "milestone=<里程碑名>"] \
  [--data-urlencode "assignee_username=<帳號>"] \
  | jq '[.[]|{iid, title, state, labels, milestone: .milestone.title, assignees: [.assignees[].username]}]'
```

- status 過濾就是 label 過濾（`labels=status::in_progress`）——不必像 github 那樣兵分兩路查
  project 欄位再交集。**這是 GitLab 在本介面上最順的一個動詞。**
- `milestone` 這裡吃**名稱**（`set_milestone` 吃 id）。同一個概念兩種參數形態，是 GitLab 自己的
  不一致，不是筆誤。
- 空結果回 `[]` 不報錯，符合介面要求。
- ⚠️ **分頁**：`per_page` 上限 100。單數超過時要跟著 `x-next-page` 標頭翻頁，
  不要把第一頁當成全部——這種漏數不會報錯，只會讓對帳靜靜少幾筆：
  ```sh
  curl -sI -H "$GL_AUTH" -G "$GL_API/issues" --data-urlencode "per_page=100" | grep -i '^x-total\|^x-next-page'
  ```
- 本動詞唯讀，不改任何資料。

### link_issues

- **`blocked_by`（標記 `<IID>` 被 `<B>` 阻塞）**

  Premium 以上有原生關聯：

  ```sh
  PID=$(curl -s -H "$GL_AUTH" "$GL_API" | jq '.id')     # 本專案的數字 id
  curl -s -X POST -H "$GL_AUTH" "$GL_API/issues/<IID>/links" \
    -d "target_project_id=$PID" -d "target_issue_iid=<B>" -d "link_type=is_blocked_by"
  ```

  Free 沒有這個 link_type（回 404／403）。**退回與 `adapters/github.md` 相同的慣例**，兩步皆必做：
  1. `curl -s -X PUT -H "$GL_AUTH" "$GL_API/issues/<IID>" --data-urlencode "add_labels=blocked"`
     （`blocked` 是 `init_structure` 之外唯一允許臨時建立的 label）
  2. 在 `<IID>` 留言一行、格式固定：`Blocked-by: #<B>`（一個 blocker 一行；解除時再留言 `Unblocked-by: #<B>`）

  兩個平台用同一套慣例是刻意的：`local-md` ↔ `github` ↔ `gitlab` 之間搬工單時，這行留言原樣可讀。

- **`parent`（把 `<IID>` 掛為 `<P>` 的子單）**

  在父單 `<P>` 的描述末尾維護一份 task list，一子單一行：

  ```sh
  desc=$(curl -s -H "$GL_AUTH" "$GL_API/issues/<P>" | jq -r '.description')
  printf '%s\n' "$desc" | grep -qF -- "- [ ] #<IID>" || \
    curl -s -X PUT -H "$GL_AUTH" "$GL_API/issues/<P>" \
      --data-urlencode "description=${desc}"$'\n'"- [ ] #<IID>"
  ```

  上面的 `grep` 就是冪等保證——**這一步是 read-modify-write，跳過查重會把同一行加兩次**。
  GitLab 會把 `- [ ] #<IID>` 渲染成真的子任務關聯（顯示標題與狀態），不只是文字。
  ⚠️ **不要改用 epic 表達父子**：epic 是 Premium、屬 group 層（不是專案層），語意是「跨專案的
  大題目」而非「本單的子單」。用它承載 `parent` 會在 Free 版整個消失，且在 Premium 版把工單
  結構掛到 group 上——那是換一個東西，不是換一種寫法。

- **查證**：`blocked_by` → Premium：`curl -s -H "$GL_AUTH" "$GL_API/issues/<IID>/links" | jq '.[].iid'`；
  Free：`curl -s -H "$GL_AUTH" "$GL_API/issues/<IID>/notes" | jq -r '.[].body' | grep 'Blocked-by:'`。
  `parent` → `curl -s -H "$GL_AUTH" "$GL_API/issues/<P>" | jq -r '.task_completion_status'`。

## publish_docs（文檔投影目標面）

介面定義見 `../SKILL.md` §3.9，判準只有一條：**機械投影不是第二份真相，人只改源頭。**
本節在「宿主平台是 gitlab」時適用——宿主的判定同 `../config-schema.md` 的 `docs` 合法性規則：
`mirror_platform` 有值取它、否則取 `devtools_platform`。

| 設定 | 載體 | 定位 | 觸發時機 |
| --- | --- | --- | --- |
| `docs.primary: wiki` | GitLab Wiki（獨立 git repo ＋ REST API） | 主閱讀面 | `merge`（合併 main 即同步） |
| `docs.mirror_site` | GitLab Pages（`pages` job ＋ `public/` artifact） | 精裝面 | `tag`（`rules: if: $CI_COMMIT_TAG`） |

⚠️ **這張表的第二列在來源專案 SuperOD 上沒有實例。** SuperOD 用 wiki 當導覽面、用 tag 觸發打包，
但**沒有 `pages` job、也沒有 mkdocs**。Pages 那一列是照 GitLab 官方 CI 規格寫的，屬附錄 B 的
第 ② 級證據。不要因為它排在 SuperOD 的欄位旁邊就以為它被實務背書過。

### `primary: wiki` 的轉換規則

GitLab wiki 與 GitHub wiki 是**兩種不同的載體**，`adapters/github.md` 的四條規則不能照抄：

| # | 規則 | 與 GitHub wiki 的差異 |
| --- | --- | --- |
| 1 | `index.md` → `home`（**小寫**） | GitHub 是 `Home.md`。大小寫在這裡是硬要求，不是風格 |
| 2 | 章節可**保留目錄層級**（slug 允許含 `/`，如 `Dev/superod`） | GitHub wiki 頁面是平的，必須壓成單層。GitLab 不必壓——壓了反而丟掉結構 |
| 3 | 章間連結去掉 `.md` | 同 GitHub。去掉之後是單純的相對 URL 解析，不倚賴 wiki 專屬的連結改寫魔法 |
| 4 | 側欄檔名是 `_sidebar`（**小寫、無副檔名時亦可**） | GitHub 是 `_Sidebar.md`。且 GitLab 的 `_sidebar` 一旦存在就**取代**預設頁面列表——新頁不會自動出現，必須同時更新它 |
| 5 | 指向 repo 內部路徑的相對連結依 `docs.link_policy` 改寫 | 同 GitHub，只是絕對 URL 形狀不同：`${GITLAB_URL}/<project-path>/-/blob/main/<路徑>` |

側欄由私有 `mkdocs.yml` 的 nav 轉寫，**不另手寫一份**——手寫就會變成 known-drift 記的
「兩份 nav」再加一份。

⚠️ **錨點：本文不給換算規則，因為沒有人驗過。** `L16` 記的是 mkdocs slug ↔ GitHub slug
對不上、而且**失敗是無聲的**（頁面照常渲染、連結照常可按，只是按了不會跳，沒有任何一支 lint 會叫）。
GitLab 用的是自己的渲染器，slug 演算法與 GitHub **不保證相同**。⇒ 首次投影到 GitLab wiki
**必須**抓實站渲染出來的 `id=` 集合，與投影算出來的錨點逐一比對，把結果寫進工單；
在那份比對存在之前，`docs.primary: wiki` 對 gitlab 宿主**只能算未驗證**。
把 `github_slug()` 直接套到 GitLab 上是本節最可能出的錯。

### `primary: wiki` 的防手改偵測

**走 git，不走 REST API。** GitLab wiki 兩條路都通得了，但只有 git 這條留得下證據：

```sh
git clone "${GITLAB_URL}/${GITLAB_PROJECT}.wiki.git" <暫存目錄>
```

投影 commit 的訊息帶兩行 trailer（與 `adapters/github.md` 同格式，刻意一致）：

```
Foundry-Projection: <來源手冊 commit sha>
Foundry-Projection-Digest: <投影內容的 sha256>
```

同步前的判定，兩層都要過：wiki HEAD 的訊息**必須帶 trailer**（UI 或 API 寫入留下的是 GitLab
自己產的訊息，trailer 當場消失）；且 wiki 現況重算的摘要**必須等於** trailer 記的那個。
任一層不過就**拒絕覆蓋並報錯**，不得自行覆寫。

⚠️ **這正是不用 REST API 寫入的原因**：`PUT /projects/:id/wikis/:slug` 寫得進去，但
commit message 由 GitLab 產生、呼叫端控制不了，於是**每一次 API 寫入都會抹掉自己的 trailer**，
下一次同步必定判成「被人手改過」。API 適合唯讀盤點（見下方查證），不適合當投影的寫入路徑。

### 精裝面：GitLab Pages ＋ tag 觸發

```yaml
pages:
  stage: deploy
  image: python:3.12-slim
  script:
    - pip install mkdocs mkdocs-material
    - mkdocs build --site-dir public      # artifact 目錄名固定是 public/，改了 Pages 就吃不到
  artifacts:
    paths: [public]
  rules:
    - if: $CI_COMMIT_TAG =~ /^handbook-v\d+\.\d+\.\d+\.\d+$/   # 對應 docs.mirror_site.tag_pattern
```

- `tag_pattern` 的 glob（`handbook-v*.*.*.*`，四碼版本號見 protocol `V4`）要手工翻成
  GitLab 的正則——**兩種語法，不是同一個字串**，照抄 glob 進 `=~` 不會報錯，只會永遠不命中。
- ⚠️ 翻過去之後**兩邊的嚴格程度不一樣，而且是正則這邊比較嚴**：`fnmatch` 只數點不看內容，
  `handbook-v0.0.0.1.2`（多一位）與 `handbook-v0.0.0.x`（非數字）在 GitHub 側是通得過的
  （protocol `V4` 違反段列的兩個已知缺口），上面的 `\d+` 版正則則會擋下。**這不是 bug，
  但要知道它在**：同一個 tag 在兩個平台上的發佈結果可能不同，跨平台對照時別假設兩邊等價。
- ⚠️ **`rules:` 少了 `if:` 的 catch-all 會在 MR 事件也命中**，於是同一份 commit 跑出兩條管線
  （來源專案 `.gitlab-ci.yml` 就為此在註解裡留了警告）。每條 rule 都要顯式夾條件。
- 自架實例的 Pages 需要管理員先啟用（`gitlab_pages` 設定）；沒啟用時 job 會綠、站台不存在。
  **這是最會騙人的一種綠燈**——查證要看站台，不要看 job 狀態。

### 查證（動詞的成功判準）

逐章比對表（標題文字／章節數／內部連結目標／規則層戳記行）是動詞的成功判準，
**任一格紅就 exit 1、不推送**；腳本自己回報成功不算查證（`X2` 踩過：發佈互蓋時腳本也說成功）。
GitLab 這邊多一項 GitHub 沒有的便利——wiki 有 REST API，可以直接把整份現況抓下來對：

```sh
curl -s -H "$GL_AUTH" "$GL_API/wikis?with_content=1&per_page=100" | jq -r '.[]|"\(.slug)\t\(.title)"'
```

⚠️ 對照表證得了「投影自我一致」，**證不了** GitLab 實際算出來的錨點等於我們算的那個（見上方
轉換規則的警告，同 `X4`／`L16` 的形狀）。錨點另列一欄標「待實站驗」。

### 三個 wiki 實測坑（來源專案 2026-09-04）

| 坑 | 後果 | 正解 |
| --- | --- | --- |
| 用 API 更新**巢狀頁**（slug 含 `/`）時 PUT 只帶 `content` | GitLab **靜默**把該頁搬回根層 | PUT 必須同時帶 `title=<完整路徑>` |
| `_sidebar` 一旦存在就**取代**預設頁面列表 | 新增的頁在側欄上不會出現，讀者等於看不到 | 每次投影同時重寫 `_sidebar`（由 nav 轉寫，見轉換規則 4） |
| wiki 頁**改名不留重導向** | 舊 slug 直接 404，且指向它的舊連結全斷 | 改名視為破壞性操作：先跑一次全 repo 的反向連結檢查再改 |

### 開通目標面不在本節授權內

啟用 wiki、開 Pages、新建公開鏡像專案——都是**新開對外資源**，屬關卡 C
（`gates.external_actions: user`，不可調降），發卡請使用者執行。本節只負責**已開通管道**的例行同步。

ℹ️ GitHub 的 `L15`（開 wiki 是兩步：開開關之後還要用 UI 建第一頁，wiki 的 git repo 才成形）
**在 GitLab 上不確定是否同形**：GitLab 有 wiki 的建頁 API（`POST /projects/:id/wikis`），
所以第二步理論上可自動化。但這條**沒有實測**，屬附錄 B 第 ② 級。第一次開通時照 `L15` 的謹慎
做法走：先跑一次 clone 對照組，確認 `Repository not found` 不是認證問題再往下判。

## 平台限制（本 adapter 專屬，不上升為流程規則）

下列是 GitLab 的產品特性。遇到時照本節處理，**不要把它們寫進 foundry-protocol**——換平台時不成立。

| 限制 | 處理方式 |
| --- | --- |
| 關單沒有 reason，`done` 與 `cancelled` 在平台上無從區分 | 兩態的唯一載體是 `status::` label，`update_status` 的 ① 不可省 |
| scoped label 的互斥性是 **Premium** 功能 | Free 版由 adapter 做 read-modify-write；查證看「`status::` 恰好一個」 |
| `blocks`／`is_blocked_by` 關聯是 **Premium** 功能 | Free 版退回 `blocked` label ＋ `Blocked-by:` 留言慣例（與 github adapter 同一套） |
| epic／Roadmap 屬 **Premium** 且在 **group 層**，不是專案層 | 不用它承載 `parent`／roadmap view；Free 用 task list 與 milestone 清單頁 |
| Free 版每專案只有一個 issue board | `init_structure` 取 `boards[0]`，不新建 |
| `set_milestone` 吃數字 id、`list_issues` 吃名稱 | 同一概念兩種參數形態，是 GitLab 自身的不一致，照本文各自的寫法 |
| `PUT /issues/:iid` 的 `labels=` 是全量替換 | 全篇一律用 `add_labels`／`remove_labels`，不用 `labels=` |
| `per_page` 上限 100 | 超過要跟 `x-next-page` 翻頁；漏翻不報錯，只會少筆 |
| 自架實例的 URL、SSH port、Pages 啟用狀態各不相同 | 全部走環境變數（見前置條件），不寫死；**不得用 `git remote` 推斷平台** |

**不屬本表的東西**：來源專案那台實例曾出現「單筆 MR 端點回 500」「合併後刪除來源分支未生效」
——那是**該實例的狀況**，不是 GitLab 的產品特性。寫進 adapter 會讓所有 GitLab 專案繼承一個
不存在的限制。實例層的異常留在該專案自己的文件裡。

## 組織層：`provision_team` 在本軸不適用

`provision_team`（`../SKILL.md` §8）由 `ai_platform` 分派，而 **`gitlab` 不是 `ai_platform`
的合法值**（枚舉是 `paperclip`｜`claude-code`｜`codex`，權威在 `../config-schema.md`）。
本節**不是**「GitLab 上的 `provision_team` 怎麼降級」——降級的前提是同一條軸上能力不足，
**這裡是根本不在這一軸**。GitLab 沒有 agent 註冊表，它有的是「人」與「權限」，
沒有「可以被指派、而且會醒過來的角色」（`../SKILL.md` §8.3）。

本節回答的是：軸 B 是 GitLab 時，`.foundry/org.yml` 宣告的編制在 GitLab 上以什麼形式存在。

### 四個落點（其中一個受版本分岔影響）

| 落點 | 承載編制的哪一部分 | 怎麼做 | 它的上限 |
| --- | --- | --- | --- |
| 角色定義 | 每個角色的判準與產出要求 | `skills/roles/<id>/SKILL.md`，跟著 repo 走（規則層 100% 可攜） | 純文件，GitLab 不讀它 |
| `CODEOWNERS` | 審查責任歸屬 | **Code Owners 屬 Premium 以上**（附錄 B 第 ③ 級推定）。有授權才有這個落點 | 吃的是**帳號**不是角色；一人分飾多角時每一列指向同一個帳號，等於沒分開 |
| `role:*` label | 這張單「該由哪個角色做」 | `init_structure` 已建同一組（**非 scoped**，單冒號；scoped 的 `status::*` 是另一回事，別混） | label 不會通知任何人 |
| roster 對照表 | **誰扮演哪個角色** | 見下 | 手維護，無機械檢查 |

⚠️ **Free 版只剩三個落點。** 沒有 Code Owners 就沒有「審查責任綁在路徑上」這件事，
審查歸屬只能靠 roster ＋ MR 上的人工指派。這與本檔開頭「版本分岔」那一節是同一個判斷點：
**先探測授權等級再決定寫哪一套**，不要臨場猜。

### roster：唯一需要新增的東西

`org.yml` 沒有「這個角色**現在由誰扮演**」——在有 agent 註冊表的平台上那一欄就是 agent 本身，
到了 GitLab 沒有承載處，就得補一張表。四欄固定：**角色（`org.yml` 的 `title`）｜扮演者
（GitLab 帳號或人名）｜自何時起｜備註**（備註寫一人多角時哪幾條規則因此不成立，例如 `M4`）。

- **放哪**：本節不預設檔名。GitLab 的 wiki 允許目錄層級，放 wiki 或 `docs/` 都行；
  導入時在 `foundry-adopt` 的報告裡定死一個路徑並寫進工單。規格不指定是刻意的——
  指定了又沒有人驗，只會多一個沒人維護的約定。
- **`model_tier` 不轉寫過來**：模型層綁的是 agent 的設定，人沒有這個欄位。
- ⚠️ **這張表會過期而且沒有任何地方會報錯**：`--selfcheck` 的 `org-sync` 只比對
  `org.yml` ↔ protocol 第 9／8 節，看不到本表。維護觸發點只有交接的那一刻。

### 硬約束（導入報告必須明列）

指派一個 GitLab issue **不會喚醒任何人**（`../SKILL.md` §7 對照表
「指派會不會喚醒 agent」那一列）。
四個落點加起來仍然只約束得了人：`../../foundry-ai-platform/SKILL.md` 的 `AP-2`
講的那件事，在組織層原封不動再發生一次。**不得靜默略過**。

## 附錄 A：專案 id 與 issue 的兩個編號

```sh
curl -s -H "$GL_AUTH" "$GL_API" | jq '{id, path_with_namespace, web_url}'   # 專案數字 id
```

GitLab 的 issue 有兩個編號：`iid`（專案內編號，就是網頁上的 `#12`）與 `id`（實例全域唯一）。
**API 路徑一律用 `iid`**（`/projects/:id/issues/:iid`）；`id` 只在少數跨專案端點出現。
`issue_ref` 定義為 `#<iid>`（`../SKILL.md` §2）。兩者混用時 API 多半回 404 而不是報錯——
拿到 404 先確認自己用的是不是 `iid`。

## 附錄 B：本文指令的查證狀態

**本 repo 沒有 GitLab 實例，本文沒有任何一條在本 repo 執行過。** 三級證據：

| 級 | 範圍 | 依據 |
| --- | --- | --- |
| ① 來源專案實測 | wiki 的三個坑（巢狀頁 PUT 要帶 `title`、`_sidebar` 取代預設列表、改名不留重導向）；`{base}/api/v4/projects/{URL-encoded path}` ＋ `PRIVATE-TOKEN` 的 API 形狀；`rules:` catch-all 在 MR 事件也命中；tag 觸發的 `if: $CI_COMMIT_TAG` | `AI_Server_SuperOD`（自架 GitLab）2026-09-03～09-04 的 `scripts/wiki_check.py`、`.gitlab-ci.yml`、`docs/development/git_flow.md`、`CLAUDE.md`。**只讀，未改對方 repo** |
| ② 官方 API 規格 | 全部動詞的 endpoint、參數名、`state_event`、`add_labels`／`remove_labels`、board／list、wiki、Pages 的 `public/` 慣例 | GitLab REST API v4 文件。**形狀正確不等於跑過** |
| ③ 版本分岔推定 | scoped label 互斥、`blocks` link_type、epic／Roadmap 的 Premium 歸屬 | 依 GitLab 方案功能表。⇒ 所以本文要求**先用「版本分岔」那一節探測一次並寫進工單**，不要臨場猜 |

**第一次在真的 GitLab 專案上跑本文時要做的事**：逐動詞記錄實際回傳，把對不上的地方改回本文，
並把錨點比對（見 `publish_docs` 的警告）補齊。在那之前，`devtools_platform: gitlab` 屬**未實跑驗證**的組態。
