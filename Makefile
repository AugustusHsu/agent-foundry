# agent-foundry — 單一指令入口（MYL-36 P5）
#
# 每個 target 帶 `##` 說明，`make help` 會自動列出，不需另外維護一份清單。

.DEFAULT_GOAL := help
.PHONY: help check selfcheck test hooks lint-doc serve providers browser

help: ## 列出所有可用指令
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

check: selfcheck test ## 跑完所有機械層閘門（＝pre-commit 會擋的內容）

selfcheck: ## repo 規範自檢：雙入口同步、手冊 nav、錨點、規則 ID、規則標記、大檔清單、相對連結、版本號形狀、表格連續性、組織宣告、手冊戳記、鏡像對帳
	@python3 tools/foundry-lint/foundry_lint.py --selfcheck

# 每個工具各自 discover：unittest 會把 start dir 加進 sys.path，
# 從共同上層 discover 會找不到受測模組。新增工具時在此追加一行。
#
# ⚠️ 追加一行的同時要改 `skills/foundry-init/SKILL.md` §2 第 3 點的複製清單：
# init 會把本檔整份複製到目標專案，這裡列到、清單沒列到的目錄，
# 會讓那個專案第一次跑 `make check` 就掛。目前沒有自檢管這個對應關係（MYL-78）。
test: ## 工具單元測試（foundry-lint ＋ model-routing ＋ browser-probe ＋ publish-docs）
	@python3 -m unittest discover tools/foundry-lint
	@python3 -m unittest discover tools/model-routing
	@python3 -m unittest discover tools/browser-probe
	@python3 -m unittest discover tools/publish-docs

hooks: ## 安裝 pre-commit hook（一台機器裝一次）
	@pre-commit install

providers: ## 盤點本機可用的模型供應商（foundry-model-routing 步驟 1）
	@python3 tools/model-routing/probe_providers.py

browser: ## 盤點本機瀏覽器能力 L0～L3（foundry-browser 步驟 1）
	@python3 tools/browser-probe/probe_browser.py

# 用法：make lint-doc TYPE=prd FILE=docs/features/<模組>/PRD.md
lint-doc: ## 檢查單一文件是否含模板必備章節（需 TYPE= 與 FILE=）
	@test -n "$(TYPE)" -a -n "$(FILE)" \
		|| { echo "用法：make lint-doc TYPE=prd FILE=docs/features/<模組>/PRD.md"; exit 2; }
	@python3 tools/foundry-lint/foundry_lint.py --type $(TYPE) $(FILE)

serve: ## 本機預覽手冊網站
	@mkdocs serve
