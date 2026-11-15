# #992 review evidence (tip 59754e69ce56bde46ad19896fbdbdfb421a0c98a)

Base: `4ce96715bc10ee5ff1841b7d55baf9c17d197ea4` (PR #1000 / #994 merge).

These are **our-app before/after** shots, not fabricated Lovart comparisons. Existing 771 left-Lovart / right-ours dialogs show the Examples layout, not the option chips this card restores, so they are not used as a Lovart counterpart here.

- `shots-before/`: dialogs on main `4ce96715` (example area present, option chips absent).
- `shots/`: dialogs after the #992 restore (same example area; five skills show unselected option chips and one selected chip; logo has no chips).
- `sbs/`: labeled left=before, right=after.
- `gate-1/`: first official gate; UNIT 3 failed on pre-#992 pins / template-count label, E2E 234 passed.
- `gate-2/` and `gate.log`: second official gate after honest test updates; UNIT 4912 passed, E2E 234 passed, GATE_EXIT=0. Mock $0.

Live provider / paid runtime was not tested.
