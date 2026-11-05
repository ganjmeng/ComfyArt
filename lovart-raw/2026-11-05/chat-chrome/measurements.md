# Lovart (lovart.ai) chat composer chrome — 2026-11-05
Signed-in session reused. English UI only (no language toggle looked for; Chinese not captured). Viewport 1920x1072 (CSS px). Project: canvas?projectId=2v0ruhzfw2kg ("Logo Style Preference Question", created by a harmless test prompt from /home).
Images are crops of full screenshots; crops exclude the avatar/name. Shots: idle.png, idle-with-reply.png, working-stop.png, working-timeline.png, reference-at-menu.png (asset names masked), ask-card.png.

## Composer (docked bottom of right-side chat panel), x=609..1311
- Textbox placeholder: `Start with an idea, "@" for context, "/" for skills` — [609,953,702,33]
- Left row: "+" button [609,1023,32,32]; mode dropdown "Agent" [643,1023,100,32]
- Right cluster: unlabeled icon button (cube-like) [1239,1023,32,32]; primary button [1279,1023,32,32]
- Primary button idle = dark circle with waveform (voice/mic) icon; with text it turns to up-arrow (send; seen in @ shot).
- Upgrade banner "Upgrade to unlock Image 2.5 unlimited gens." sits above composer (not part of the chrome).

## 1) Working indicator
No "工作中"/"Working" text chip exists (page text search for "Working" = 0 hits). While running, the timeline showed a dim "Got…" streaming text with a small mascot icon above the composer (left, ~[330,495] in 1024-scale shot). Run was very short so only one in-progress frame was caught.

## 2) Stop
While running, the primary button at the same position [1279,1023,32,32] became a dark circle with white square (Stop). No separate 终止/Stop chip above the composer was seen. Idle/after-run it reverts to waveform.
**Hypothesis (Stop = right-side composer button becomes Stop): YES** — it replaces the mic/send button, same bbox, inside the composer, bottom-right. Caveat: only observed on a ~few-second text reply, not a long image generation.

## 3) Reference
Typing "@" in the textbox opens a popup above the composer (x≈660..915, y≈680..1020): sections "Assets" (project assets + "More") and "Model" (GPT Image 2.6 Flare Auto/Low/Medium, "More"); textbox placeholder becomes "Type a keyword to search references". A separate "Reference" tab button also exists in the top canvas tab bar (Reference / Assets / Pinterest / Lovart Clipper) — a canvas panel, not a composer chip. No 参考 chip next to composer seen with nothing attached.

## 4) Ask / question card (ask_user) — captured
Card replaces/sits directly above composer, [601,603,718,296]: header "Question" [639,621,55,20]; text "What logo style do you prefer?"; options "A Minimal", "B Playful", "C Retro" (each row ~[609,687,702,36]); option "D" free-text "Other (type your answer)..." [645,815,658,20]; buttons "Skip" [1151,855,60,32] and "Submit" [1217,855,90,32] (disabled until choice; has ⏎ hint). Clicking Skip posts user message "Skip this question".
While the card is shown the composer sits below it with the same layout.

## Not triggered
Chinese UI; long image-generation run; any "工作中" text. Note: user's computer was offline during this run, so browsing went over the box's own network.
