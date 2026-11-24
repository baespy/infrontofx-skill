#!/usr/bin/env bash
export LC_ALL=C.UTF-8 2>/dev/null
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
routes="$here/skill-routes.tsv"
input="$(cat)"
mode="claude"
none=""
case "$input" in
    *'"lastUserInput"'*|*'"PreInvocation"'*)
        mode="antigravity"
        none="{}"
        ;;
esac
finish() {
    printf '%s' "$none"
    exit 0
}
if [ "$mode" = "antigravity" ]; then
    prompt="$(printf '%s' "$input" | sed -n 's/.*"lastUserInput"[[:space:]]*:[[:space:]]*"\(\([^"\\]\|\\.\)*\)".*/\1/p' | head -n 1)"
    session="$(printf '%s' "$input" | sed -n 's/.*"conversationId"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"
else
    prompt="$(printf '%s' "$input" | sed -n 's/.*"prompt"[[:space:]]*:[[:space:]]*"\(\([^"\\]\|\\.\)*\)".*/\1/p' | head -n 1)"
    session="$(printf '%s' "$input" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"
fi
[ -r "$routes" ] || finish
[ "${#prompt}" -ge 4 ] || finish
case "$prompt" in
    *"<task-notification>"*|*"[SYSTEM NOTIFICATION"*|*"<system-reminder>"*|*"<local-command"*|*"<command-name>"*|*"<agent-message"*|*"<cross-session-message"*|*"[Subagent hand-back]"*) finish ;;
esac
lockroot="${TMPDIR:-/tmp}/infrontofx-skill-router"
mkdir -p "$lockroot" 2>/dev/null
key="$(printf '%s|%s|%s' "$mode" "$session" "$prompt" | cksum | cut -d' ' -f1)"
mkdir "$lockroot/$key" 2>/dev/null || finish
find "$lockroot" -mindepth 1 -maxdepth 1 -mmin +30 -exec rm -rf {} + 2>/dev/null
text=" ${prompt,,} "
text="${text//\\n/ }"
shopt -s nocasematch
picked=()
reasons=()
add() {
    for p in "${picked[@]}"; do
        [ "$p" = "$1" ] && return 0
    done
    picked+=("$1")
    reasons+=("$2")
}
has() {
    for p in "${picked[@]}"; do
        [ "$p" = "$1" ] && return 0
    done
    return 1
}
words() {
    [[ $text =~ (^|[^a-z0-9_])($1)([^a-z0-9_]|$) ]]
}
while IFS=$'\t' read -r skill why thai english; do
    [ -n "$skill" ] || continue
    case "$skill" in
        \#*) continue ;;
    esac
    if { [ -n "$thai" ] && [[ $text =~ ($thai) ]]; } || { [ -n "$english" ] && words "$english"; }; then
        add "$skill" "$why"
    fi
done < "$routes"
if has sculpt-forge && ! has prop-forge && ! has map-forge && { [[ $text =~ (ส่งออก|เข้าเกม|ลงเกม|สตรีม) ]] || words 'export|stream|spawn|in game|ingame'; }; then
    add prop-forge "export after sculpting"
fi
if has infrontofx && ! has dev-flow; then
    add dev-flow "verify before done"
fi
[ ${#picked[@]} -gt 0 ] || finish
list=""
count=0
for core in infrontofx dev-flow; do
    for i in "${!picked[@]}"; do
        if [ "${picked[$i]}" = "$core" ]; then
            [ -n "$list" ] && list="$list, "
            list="$list${picked[$i]} (${reasons[$i]})"
            count=$((count + 1))
        fi
    done
done
for i in "${!picked[@]}"; do
    case "${picked[$i]}" in
        infrontofx|dev-flow) continue ;;
    esac
    [ $count -lt 5 ] || break
    [ -n "$list" ] && list="$list, "
    list="$list${picked[$i]} (${reasons[$i]})"
    count=$((count + 1))
done
message="skill-router: load $list before acting (names may carry the infrontofx-skill: prefix); open only the references they route to."
if [ "$mode" = "antigravity" ]; then
    printf '{"injectSteps":[{"systemMessage":{"systemMessage":"%s"}}]}' "$message"
else
    printf '{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"%s"}}' "$message"
fi
