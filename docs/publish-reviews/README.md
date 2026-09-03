# 發佈審查記錄

`docs/handbook/` 的每次公開發佈，在這裡留一份審查記錄（`<工單編號>.md`，骨架見
`templates/publish-review.md`）。`scripts/publish-handbook.sh` 的證據閘門會讀本目錄：
找不到 `verdict: APPROVED` 且 `handbook_commit` 對得上目前手冊內容的記錄，就拒絕發佈。

流程與判準見 `skills/foundry-protocol/SKILL.md` 第 7 節「手冊發佈審查」（MYL-24）。

本目錄不在公開鏡像同步範圍內（腳本只複製 `docs/handbook/`）。
