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
# Parsing is bash-native (no python/jq/grep/sed per frame) because a status line
# re-renders constantly. Requires bash 3.2+, which is what macOS ships.
#
# Known limitation: values containing escaped quotes (JSON \") are truncated at
# the escape. Directory names and model names containing a double quote are the
# only realistic trigger, and the failure is cosmetic — a short label, never a
# wrong badge.

payload=""
IFS= read -r -d '' payload || true

nl=$'\n'

# First "key": "value" match in the status line JSON on stdin.
jstr() {
    local re="\"$1\"[[:space:]]*:[[:space:]]*\"([^\"]*)\""
    [[ $payload =~ $re ]] && printf '%s' "${BASH_REMATCH[1]}"
}

dir="$(jstr current_dir)"
[ -z "$dir" ] && dir="$(jstr cwd)"
[ -z "$dir" ] && dir="$PWD"

# Resolve relative input against $PWD. Without this the upward walk below never
# terminates ("." has no parent), which would hang every status line render.
case "$dir" in
    /*) ;;
    *) dir="$PWD/$dir" ;;
esac
# Trim trailing "/." and "/" so the $HOME comparison below is a real comparison:
# "$PWD/." would otherwise never equal "$HOME" and would leak the home badge.
while :; do
    case "$dir" in
        /) break ;;
        */.) dir="${dir%/.}" ;;
        */) dir="${dir%/}" ;;
        *) break ;;
    esac
    [ -z "$dir" ] && { dir=/; break; }
done

model="$(jstr display_name)"
[ -z "$model" ] && model="$(jstr model)"

# ---- dir: home-relative, and only the last two segments when deep ------------
short="$dir"
if [ -n "$HOME" ]; then
    case "$short" in
        "$HOME") short="~" ;;
        "$HOME"/*) short="~/${short#"$HOME"/}" ;;
    esac
fi
# ~/a/b/c/d -> …/c/d  (a bare ~ or a one-level path stays whole)
slashes="${short//[!\/]/}"
if [ "${#slashes}" -gt 2 ]; then
    parent="${short%/*}"
    short="…/${parent##*/}/${short##*/}"
fi

out="$(printf '\033[38;5;110m%s\033[0m' "$short")"
[ -n "$model" ] && out="$out$(printf '  \033[38;5;245m%s\033[0m' "$model")"

# ---- badge: nearest .octowiz/state.json, walking up from the cwd -------------
# The walk is convenience — `octowiz state` itself resolves .octowiz in the
# literal cwd and never walks up. Three boundaries keep the badge honest:
#   * never inherit across a repository root: stop at a directory containing
#     .git, so a repository without its own state never wears an ancestor's badge
#   * $HOME's state counts only when the working directory is exactly $HOME
#   * never walk above $HOME, so nothing inherits a badge from /Users or /
badge=""
if [ -d "$dir" ]; then
    d="$dir"
    while [ -n "$d" ]; do
        if [ -f "$d/.octowiz/state.json" ]; then
            if [ -n "$HOME" ] && [ "$d" = "$HOME" ] && [ "$dir" != "$HOME" ]; then
                d=""            # home state, but not sitting in home
            fi
            break
        fi
        # repository root, or the home boundary: stop without inheriting upward
        if [ -e "$d/.git" ] || { [ -n "$HOME" ] && [ "$d" = "$HOME" ]; }; then
            d=""
            break
        fi
        parent="${d%/*}"
        [ "$parent" = "$d" ] && d="" && break   # no further parent to try
        d="$parent"                             # "/a" -> "" ends the walk
    done

    if [ -n "$d" ] && [ -f "$d/.octowiz/state.json" ]; then
        statetxt="$(<"$d/.octowiz/state.json")"
        # Anchored to top-level keys (two-space indent). Unanchored matching would
        # pick up nested objects — acceptanceCriteria[].status would shadow the
        # work item's own status and silently suppress or mislabel the badge.
        field() {
            local re="(^|${nl})  \"$1\"[[:space:]]*:[[:space:]]*\"([^\"]*)\""
            [[ $statetxt =~ $re ]] && printf '%s' "${BASH_REMATCH[2]}"
        }
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
