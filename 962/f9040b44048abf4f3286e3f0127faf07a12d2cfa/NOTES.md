# #962 — youtube-channel-banner card 1 zh/en (Full App, mock, $0)

Tip under test: `f9040b44048abf4f3286e3f0127faf07a12d2cfa` (`fix/962-en-card1-copy`).

## What these are

Full App screenshots of the real app + real chat + real MCP ask card, with a scripted
in-process agent (no LLM) and the local mock WaveSpeed server (no submit, no quote, no key).

- `card1-zh.png` — zh UI, card 1 is the existing reference copy (unchanged).
- `card1-en.png` — en UI, card 1 prompt + every option + placeholders are English; no CJK.

Same flow both times: default skills page → YouTube Channel Banner → skill dialog Additional
Details → Start → Send. Captured before answering so the card copy is the evidence.

## Command

```
PLAYWRIGHT_BROWSERS_PATH=/private/tmp/pw-chromium \
ASK962_SHOTS=/private/tmp/shots962 \
/private/tmp/ca-env/bin/python -m pytest tests/test_962_en_card1_e2e.py -q
```

The test asserts the rendered prompt, every option label and every placeholder in both
languages, answers B / C / A through the real HTTP answer path, and asserts
`mock_ws["submits"] == [] and mock_ws["quotes"] == []`.

No API key is shown or used.
