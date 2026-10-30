#!/usr/bin/env bash
# #462 mutation: drop the description parse line in parseMarkdown; the round-trip test must go red.
set -u
cd "$(dirname "$0")/../../.."
cp src/skills.ts /tmp/skills.ts.bak
sed -i 's/^  const description = m ? unquote(.*$/  const description = ""/' src/skills.ts
grep -q 'const description = ""' src/skills.ts || { echo "mutation not applied"; exit 2; }
python3 -m pytest -q tests/test_skill_desc_462.py -p no:cacheprovider; rc=$?
cp /tmp/skills.ts.bak src/skills.ts
[ $rc -ne 0 ] && echo "MUTANT KILLED" || { echo "MUTANT SURVIVED"; exit 1; }
