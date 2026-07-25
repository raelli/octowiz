#!/usr/bin/env bash
# Octowiz status line: <dir>  <model>  [OCTOWIZ <phase>:<state>]
#
# Wire it up in ~/.claude/settings.json:
#   "statusLine": { "type": "command",
#                   "command": "bash \"$CLAUDE_PLUGIN_ROOT/hooks/octowiz-statusline.sh\"" }
# (Claude Code's statusLine replaces the default bar, which is why this script
# also prints the directory and model rather than the badge alone.)
#
# The badge's source of truth is <dir>/.octowiz/state.json — the durable
# engineering state written by `octowiz state`. Deliberately NOT the machine-local
# runtime under ~/.cache/octowiz/*/runtime.json: those session leases are only
# released by a clean Stop hook, so they keep reporting "active" long after the
# session is gone. A badge that lies is worse than no badge.
#
# Nothing is printed when there is no engineering state to report, or once the
# work item is done. Projects on octowiz lines without the state model (anything
# predating src/state) simply stay dark.
#
# Pure bash on purpose: a status line re-renders constantly, so no python/jq per
# frame.

payload="$(cat)"

# Pull the first "key": "value" match out of the status line JSON on stdin.
jstr() { printf '%s' "$payload" | grep -o "\"$1\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" | head -n1 | sed 's/.*"\([^"]*\)"$/\1/'; }

dir="$(jstr current_dir)"
[ -z "$dir" ] && dir="$(jstr cwd)"
[ -z "$dir" ] && dir="$PWD"

model="$(jstr display_name)"
[ -z "$model" ] && model="$(jstr model)"

# ---- dir: home-relative, and only the last two segments when deep ------------
short="$dir"
case "$short" in
    "$HOME") short="~" ;;
    "$HOME"/*) short="~/${short#"$HOME"/}" ;;
esac
# ~/a/b/c/d -> …/c/d  (a bare ~ or a one-level path stays whole)
segs="$(printf '%s' "$short" | tr -cd '/' | wc -c | tr -d ' ')"
if [ "$segs" -gt 2 ]; then
    parent="${short%/*}"
    short="…/${parent##*/}/${short##*/}"
fi

out="$(printf '\033[38;5;110m%s\033[0m' "$short")"
[ -n "$model" ] && out="$out$(printf '  \033[38;5;245m%s\033[0m' "$model")"

# ---- badge: nearest .octowiz/state.json, walking up from the cwd -------------
# The walk is convenience — `octowiz state` itself resolves .octowiz in the
# literal cwd and never walks up. Two boundaries keep the badge honest:
#   * never inherit across a repository root: stop at a directory containing
#     .git, so a repo without its own state never wears an ancestor's badge
#   * $HOME's state counts only when sitting exactly in $HOME, otherwise every
#     non-repo directory on the machine would wear the badge
badge=""
if [ -d "$dir" ]; then
    d="$dir"
    while [ -n "$d" ] && [ "$d" != "/" ]; do
        if [ -f "$d/.octowiz/state.json" ]; then
            { [ "$d" != "$HOME" ] || [ "$dir" = "$HOME" ]; } && break
        fi
        [ -e "$d/.git" ] && { d=""; break; }   # repository root: do not inherit upward
        d="$(dirname "$d")"
    done
    state="$d/.octowiz/state.json"
    if [ -f "$state" ]; then
        field() { grep -o "\"$1\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" "$state" | head -n1 | sed 's/.*"\([^"]*\)"$/\1/'; }
        phase="$(field phase)"     # A | B | C | D
        work="$(field state)"      # explore … blocked, ready-to-ship, shipped
        status="$(field status)"   # active | blocked | done
        if [ -n "$phase$work" ] && [ "$status" != "done" ]; then
            label="OCTOWIZ"
            [ -n "$phase" ] && label="$label $phase"
            [ -n "$work" ] && label="$label:$work"
            # blocked is the one status worth an extra glance
            [ "$status" = "blocked" ] && [ "$work" != "blocked" ] && label="$label!"
            badge="$(printf '  \033[38;5;141m[%s]\033[0m' "$label")"
        fi
    fi
fi

printf '%s%s' "$out" "$badge"
