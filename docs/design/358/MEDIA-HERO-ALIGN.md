# #358 MEDIA-HERO left-align amend

Replaces #356 rule “Left edge aligns with status-card / label column (past icon rail + spine).”

**New:** `ca-media-hero` left edge = ProcessTimeline **icon column** left edge (Lovart).  
Acceptance: `hero−icon = 0 ± 2px` on #78 live (light+dark × image+video).

Implementation: `margin-left: 0` on `.ca-media-hero` (was `calc(var(--ca-process-col) + var(--ca-process-gutter))`).
