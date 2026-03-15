#!/usr/bin/env bash
# Claude Code status line: model, context window usage, session cost
# Color-coded by context usage: green <50%, yellow 50-79%, red 80%+

input=$(cat)

model=$(echo "$input" | jq -r '.model.display_name // empty')
model_id=$(echo "$input" | jq -r '.model.id // empty')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
used_tokens=$(echo "$input" | jq -r '.context_window.current_usage.input_tokens // empty')
total_tokens=$(echo "$input" | jq -r '.context_window.context_window_size // empty')
cost=$(echo "$input" | jq -r '.cost.total_cost_usd // empty')

RED='\033[0;31m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
DIM='\033[0;90m'
RESET='\033[0m'

format_tokens() {
  local n=$1
  if [ "$n" -ge 1000000 ]; then
    printf "%.1fM" "$(echo "scale=1; $n / 1000000" | bc)"
  elif [ "$n" -ge 1000 ]; then
    printf "%.1fK" "$(echo "scale=1; $n / 1000" | bc)"
  else
    printf "%d" "$n"
  fi
}

# Model
if [ -n "$model" ]; then
  printf "${DIM}%s${RESET}" "$model"
  # Append context size hint from model_id (e.g. "1m" from "claude-opus-4-6[1m]")
  case "$model_id" in
    *\[1m\]*|*1m*) printf "${DIM}(1M)${RESET}" ;;
  esac
else
  printf "${DIM}?${RESET}"
fi

printf " ${DIM}|${RESET} "

# Context window
if [ -n "$used_pct" ] && [ -n "$total_tokens" ]; then
  pct_int=$(printf "%.0f" "$used_pct")
  if [ "$pct_int" -ge 80 ]; then
    color="$RED"
  elif [ "$pct_int" -ge 50 ]; then
    color="$YELLOW"
  else
    color="$GREEN"
  fi

  total_fmt=$(format_tokens "$total_tokens")
  if [ -n "$used_tokens" ]; then
    used_fmt=$(format_tokens "$used_tokens")
    printf "${color}${used_fmt}/${total_fmt} (${pct_int}%%)${RESET}"
  else
    printf "${color}${pct_int}%% of ${total_fmt}${RESET}"
  fi
else
  printf "${DIM}ctx: ...${RESET}"
fi

# Session cost
if [ -n "$cost" ] && [ "$cost" != "0" ]; then
  printf " ${DIM}|${RESET} "
  printf "${DIM}\$%s${RESET}" "$cost"
fi
