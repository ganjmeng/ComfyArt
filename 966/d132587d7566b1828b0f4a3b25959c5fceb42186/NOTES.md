# #966 — youtube-channel-banner card 2 zh/en (Full App, mock, $0)

Tip under test: `d132587d7566b1828b0f4a3b25959c5fceb42186` (`fix/966-en-card2-copy`).

## What these are

Full App screenshots of the real app + real chat + real MCP ask card, with a scripted
in-process agent (no LLM) and the local mock WaveSpeed server (no submit, no quote, no key).

- `card2-zh.png` — zh UI, card 2 is the existing reference copy (byte-for-byte unchanged).
- `card2-en.png` — en UI, card 2 fixed copy is English: prompts, placeholder, the two
  yt_text_mode option labels and the `(Recommended)` marker. The three yt_direction options
  are the agent's live copy (English in this run, per the skill's en guidance); the server
  does not translate live labels/descriptions.

Same flow both times: default skills page → YouTube Channel Banner → skill dialog Additional
Details → Start → Send → answer card 1 (A/A/A) → card 2 appears. Captured before answering
card 2 so the card copy is the evidence.

## Command

```
PLAYWRIGHT_BROWSERS_PATH=/private/tmp/pw-chromium \
ASK966_SHOTS=/private/tmp/shots966 \
/private/tmp/ca-env/bin/python -m pytest tests/test_966_en_card2_e2e.py -q
```

The test asserts the rendered card-2 prompt, every option label and every placeholder in both
languages, answers A / A through the real HTTP answer path (the agent receives option ids), and
asserts `mock_ws["submits"] == [] and mock_ws["quotes"] == []`.

No API key is shown or used.
