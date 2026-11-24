#!/usr/bin/env bash
export LC_ALL=C.UTF-8 2>/dev/null
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
routes="$here/skill-routes.tsv"
[ -r "$routes" ] || exit 0
input="$(cat)"
prompt="$(printf '%s' "$input" | sed -n 's/.*"prompt"[[:space:]]*:[[:space:]]*"\(\([^"\\]\|\\.\)*\)".*/\1/p' | head -n 1)"
session="$(printf '%s' "$input" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"
[ "${#prompt}" -ge 4 ] || exit 0
case "$prompt" in
    *"<task-notification>"*|*"[SYSTEM NOTIFICATION"*|*"<system-reminder>"*|*"<local-command"*|*"<command-name>"*|*"<agent-message"*|*"<cross-session-message"*|*"[Subagent hand-back]"*) exit 0 ;;
esac
text=" ${prompt,,} "
text="${text//\\n/ }"
shopt -s nocasematch
picked=()
reasons=()
while IFS=$'\t' read -r skill why thai english; do
    [ -n "$skill" ] || continue
    hit=0
    if [ -n "$thai" ] && [[ $text =~ ($thai) ]]; then
        hit=1
    fi
    if [ $hit -eq 0 ] && [ -n "$english" ] && [[ $text =~ (^|[^a-z0-9_])($english)([^a-z0-9_]|$) ]]; then
        hit=1
    fi
    [ $hit -eq 1 ] || continue
    seen=0
    for p in "${picked[@]}"; do
        [ "$p" = "$skill" ] && seen=1
    done
    [ $seen -eq 1 ] && continue
    picked+=("$skill")
    reasons+=("$why")
done < "$routes"
[ ${#picked[@]} -gt 0 ] || exit 0
has() {
    for p in "${picked[@]}"; do
        [ "$p" = "$1" ] && return 0
    done
    return 1
}
if has infrontofx && ! has dev-flow; then
    picked+=("dev-flow")
    reasons+=("verify before done")
fi
lockroot="${TMPDIR:-/tmp}/infrontofx-skill-router"
mkdir -p "$lockroot" 2>/dev/null
key="$(printf '%s|%s' "$session" "$prompt" | cksum | cut -d' ' -f1)"
if ! mkdir "$lockroot/$key" 2>/dev/null; then
    exit 0
fi
find "$lockroot" -mindepth 1 -maxdepth 1 -mmin +10 -exec rm -rf {} + 2>/dev/null
list=""
count=0
for i in "${!picked[@]}"; do
    [ $count -lt 3 ] || break
    [ -n "$list" ] && list="$list, "
    list="$list${picked[$i]} (${reasons[$i]})"
    count=$((count + 1))
done
printf '{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"skill-router: load %s before acting (names may carry the infrontofx-skill: prefix); open only the references they route to."}}' "$list"
