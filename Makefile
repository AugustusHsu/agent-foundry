# agent-foundry — 單一指令入口（MYL-36 P5）
#
# 每個 target 帶 `##` 說明，`make help` 會自動列出，不需另外維護一份清單。

.DEFAULT_GOAL := help
.PHONY: help check selfcheck test hooks lint-doc serve

help: ## 列出所有可用指令
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

check: selfcheck test ## 跑完所有機械層閘門（＝pre-commit 會擋的內容）

selfcheck: ## repo 規範自檢：雙入口同步、手冊 nav、錨點、規則 ID
	@python3 tools/foundry-lint/foundry_lint.py --selfcheck

test: ## foundry-lint 單元測試
	@python3 -m unittest discover tools/foundry-lint

hooks: ## 安裝 pre-commit hook（一台機器裝一次）
	@pre-commit install

# 用法：make lint-doc TYPE=prd FILE=docs/features/<模組>/PRD.md
lint-doc: ## 檢查單一文件是否含模板必備章節（需 TYPE= 與 FILE=）
	@test -n "$(TYPE)" -a -n "$(FILE)" \
		|| { echo "用法：make lint-doc TYPE=prd FILE=docs/features/<模組>/PRD.md"; exit 2; }
	@python3 tools/foundry-lint/foundry_lint.py --type $(TYPE) $(FILE)

serve: ## 本機預覽手冊網站
	@mkdocs serve
