#940 first cut — Full App user-bubble chips (tip f3e6cdb9)

- `inline-chips-zh-light.png` / `inline-chips-en-dark.png`: 1280×800 Full App, device_scale_factor 2.
- Each shot has two user bubbles: (1) skill chip + wrapping long text; (2) skill chip + two reference chips (16×16 thumb from the existing `/api/view` URL + filename).
- Seeded `chat_store` messages in the real app. No model calls, no paid generate. Cost $0.
- Mock boundary: only the host websocket / empty catalog stubs from the shared e2e `app_url` fixture; chat rows are persisted messages, not injected DOM.
