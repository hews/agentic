CLAUDE_DIR := $(HOME)/.claude

.PHONY: help sync

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

sync: ## Symlink config and plugins into ~/.claude/
	@echo "-> Syncing statusline..."
	@ln -sf $(CURDIR)/config/statusline-command.sh $(CLAUDE_DIR)/statusline-command.sh
	@echo "   $(CLAUDE_DIR)/statusline-command.sh -> config/statusline-command.sh"
	@echo "-> Done."
