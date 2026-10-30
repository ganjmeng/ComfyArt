#!/usr/bin/env bash
# #462 Edit in chat — mutations proven red UNDER PYTEST.
#   M1 另存成新技能: saving over an existing skill writes a new folder (src/skills.ts saveSkill)
#   M2 开场消息发两次: the opening message is sent twice (src/skillEdit.ts startSkillEdit)
#   M3 chip 不让位: the in-bubble chip no longer shrinks/truncates, so the text wraps (src/styles/shell.css)
#   M4 带 path 也算加载: a read WITH a path renders 技能加载完成 again (src/ui/ChatMessage.tsx)
# pytest breaks in hyphenated dirs, so this runs in a throwaway clone named ComfyArt (node_modules symlinked);
# each mutation is reverted with git checkout there. The source worktree is never modified.
set -u
SRC="$(cd "$(dirname "$0")/../../.." && pwd)"
# not the box desktop browser runtime (sand-playwright-runtime / chrome): only real test runners block
if pgrep -f "python3\? -m pytest|playwright/driver/node" >/dev/null; then echo "another pytest/Playwright runner is active; try later"; exit 2; fi
WORK="$(mktemp -d)/ComfyArt"
git clone -q --no-hardlinks "$SRC" "$WORK" && git -C "$WORK" checkout -q "$(git -C "$SRC" rev-parse HEAD)"
ln -s "$SRC/node_modules" "$WORK/node_modules"
echo node_modules >> "$WORK/.git/info/exclude"  # the symlink is not matched by node_modules/
cd "$WORK"
T="tests/test_skill_edit_chat_462.py tests/test_agent_loop_audit_410.py"
run() { python3 -m pytest $T -q -p no:cacheprovider >"/tmp/mut462-$1.log" 2>&1; echo $?; }
fails() { grep -E '^FAILED' "/tmp/mut462-$1.log" | sed 's/ - .*//; s/^FAILED /    /'; }
status=0
rc=$(run base); if [ "$rc" = 0 ]; then echo "BASELINE GREEN (unmutated passes)"; else echo "BASELINE RED rc=$rc — fix before trusting mutations"; fails base; status=1; fi

mutate() {  # name file sed-expr
  sed -i "$3" "$2"
  if git diff --quiet -- "$2"; then echo "$1: MUTATION NOT APPLIED"; status=1; return; fi
  rc=$(run "$1")
  git checkout -q -- "$2"
  if [ "$rc" != 0 ]; then echo "$1: RED (killed, pytest rc=$rc)"; fails "$1"; else echo "$1: GREEN (SURVIVED)"; status=1; fi
}
mutate M1-save-new-folder src/skills.ts 's|^export async function saveSkill(skill: Skill) {$|&\n  if ((await listFiles(skill.id)).includes("SKILL.md")) skill = { ...skill, id: `${skill.id}-copy` }|'
mutate M2-send-twice src/skillEdit.ts 's|^  await send(turn.text, skill, turn.context)$|&\n  await send(turn.text, skill, turn.context)|'
mutate M3-chip-no-shrink src/styles/shell.css 's|^\(.ca-chat__bubble--skill > .ca-chip--skill {\) flex: 0 999 auto; min-width: 48px; overflow: hidden; white-space: nowrap; }|\1 flex: none; }|'
mutate M4-path-read-as-load src/ui/ChatMessage.tsx "s/(action === 'read' \&\& !!input?.path)/action === 'read'/"
if [ -z "$(git status --porcelain)" ]; then echo "TREE CLEAN"; else echo "TREE DIRTY"; git status --short; status=1; fi
rm -rf "$(dirname "$WORK")"
exit $status
