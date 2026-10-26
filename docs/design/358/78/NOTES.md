# #358 chat media-hero left = icon column · #78 shots

**Branch:** `tip/358-media-hero-align` · closes #358  
**Amends:** #356 MEDIA-HERO left-align (voids “past icon rail / label column”)

## Numeric AC (product LOCK)

| | hero−icon | hero−text |
|---|---|---|
| Lovart | **0±2** | −15…−26 |
| tip `812ea12` (wrong) | **+27…+28** | −3…−4 |
| this tip #78 | **0** | −28 |

**LOCK:** grey hero left edge = ProcessTimeline icon column left edge.  
**CANCEL:** align with status/label column past icon rail + spine.

## Fix
`.ca-media-hero { margin-left: 0 }` — removed `calc(var(--ca-process-col) + var(--ca-process-gutter))` (~28px).

## Honest source
Tip CSS harness + static DOM matching ProcessTimeline — NOT full Electron / NOT live LLM.  
Measured via `getBoundingClientRect` (icon box left vs hero left).

## After (this tip)
| Shot | Shows |
|------|-------|
| `after/chat-image-{light,dark}-live.png` | title → grey hero flush with **icon** column; no bordered status |
| `after/chat-video-{light,dark}-live.png` | same for video AR 1/1 |

AR rules / no status above hero / canvas Generating radius 0 unchanged from #356/#357.
