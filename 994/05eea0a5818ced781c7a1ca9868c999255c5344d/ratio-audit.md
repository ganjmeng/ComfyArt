# #994 all33 typed IMAGE-call audit

App ratios: 1:1, 1:2, 2:1, 1:3, 3:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 9:21, 21:9, 1:4, 4:1, 1:8, 8:1. Runtime support = intersection with actual selected model schema, never an assumption from normalization.

|Skill|Default canvas|Image count|Ref contract|Representative no-ref / one-ref model|
|---|---|---|---|---|
|anim-2d|2048×1152 16:9|1 (bounds None..None)|primary visual|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|animated-poster|1536×2048 3:4|1 (bounds None..None)|source artwork|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|banner-design-director|2048×1152 16:9|1 (bounds None..None)|uploaded refs; pass every one|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|commerce-strategist|1024×1024 1:1|1 (bounds None..None)|optional ref assets|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|crayon-sketch|1024×1024 1:1|1 (bounds None..None)|subject image (image 1)|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|creator-identity|1024×1024 1:1|3 (bounds None..None)|creator refs|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|crt-interface|2048×1536 4:3|1 (bounds None..None)|uploaded refs|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|fabric-collage|1024×1024 1:1|1 (bounds None..None)|uploaded refs|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|flash-cut-video|2048×1152 16:9|1 (bounds None..None)|landscape 16:9 screenshot|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|interior-architectural-visualization|2048×1152 16:9|1 (bounds None..None)|uploaded refs; eye-level wide shot, detail vignette is 4:3|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|lifestyle-scene|1024×1024 1:1|1 (bounds None..None)|product image (when provided)|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|live-promo-decor|1152×2048 9:16|3 (bounds None..None)|product/stream refs|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|logo-abstract|1024×1024 1:1|1 (bounds None..None)|reference photo (image 1)|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|logo-animation|2048×1152 16:9|1 (bounds None..None)|logo image (image 1)|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|marketing-campaign-generator|2048×1152 16:9|3 (bounds None..None)|brand/product refs, same on every call|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|meta-ads-creative-director|1024×1024 1:1|3 (bounds None..None)|product/person refs, same on every call|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|mobile-app-visual-design|880×2048 9:21|2 (bounds None..None)|uploaded refs; phone-framed screens|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|motion-poster-generator|1536×2048 3:4|1 (bounds None..None)|source_image (the static artwork)|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|naive-illustration|1024×1024 1:1|1 (bounds None..None)|uploaded refs|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|person-swap|1536×2048 3:4|3 (bounds None..None)|scene/pose first, then face and outfit|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|photo-split-poster|1638×2048 4:5|1 (bounds None..None)|photo (image 1); keep the photo/geometry split|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|poster-differentiated-compiler|1536×2048 3:4|1 (bounds 1..2)|uploaded refs; instruction says default 3:4|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|ppt-visual|2048×1152 16:9|3 (bounds None..None)|uploaded refs; pass every one|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|premium-website|2048×1152 16:9|2 (bounds None..None)|uploaded refs; pass every one|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|product-tvc-advertisement-generator|2048×1152 16:9|1 (bounds None..None)|product image (always pass it)|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|product-website|2048×1152 16:9|3 (bounds None..None)|uploaded refs; pass every one|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|promo-ecommerce|1024×1024 1:1|1 (bounds None..None)|product image|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|rednote-cover-maker|1024×1024 1:1|3 (bounds None..None)|product/person refs, same on every call|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|restaurant-website|2048×1152 16:9|3 (bounds None..None)|uploaded refs; pass every one|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|style-transfer|1024×1024 1:1|1 (bounds None..None)|content image first, style image second|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|taobao-product|1024×1024 1:1|4 (bounds None..None)|product image (main image is 1:1)|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|web-product-visual-design|2048×1152 16:9|1 (bounds None..None)|uploaded refs; pass every one|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|
|yingzao|1536×2048 3:4|1 (bounds None..None)|photo (image 1); no invented architecture|openai/gpt-image-2.6-flare/text-to-image / openai/gpt-image-2.6-flare/edit|

## Actual schema snapshot capabilities
- `bytedance/seedream-v5.0-pro`: enum=['1:1', '1:2', '2:1', '1:3', '3:1', '2:3', '3:2', '3:4', '4:3', '4:5', '5:4', '9:16', '16:9', '9:21', '21:9']; size=None; snapshot present=True
- `bytedance/seedream-v5.0-pro/edit`: enum=['1:1', '1:2', '2:1', '1:3', '3:1', '2:3', '3:2', '3:4', '4:3', '4:5', '5:4', '9:16', '16:9', '9:21', '21:9']; size=None; snapshot present=True
- `google/nano-banana-2.1/edit`: enum=['1:1', '3:2', '2:3', '3:4', '4:3', '4:5', '5:4', '9:16', '16:9', '21:9', '1:4', '4:1', '1:8', '8:1']; size=None; snapshot present=True
- `google/nano-banana-2.1/text-to-image`: enum=['1:1', '3:2', '2:3', '3:4', '4:3', '4:5', '5:4', '9:16', '16:9', '21:9', '1:4', '4:1', '1:8', '8:1']; size=None; snapshot present=True
- `midjourney/text-to-image`: enum=['1:1', '9:16', '16:9', '4:3', '3:4', '2:3', '3:2', '9:21', '21:9']; size=None; snapshot present=True
- `openai/gpt-image-2.6-flare/edit`: enum=['1:1', '1:2', '2:1', '1:3', '3:1', '2:3', '3:2', '3:4', '4:3', '4:5', '5:4', '9:16', '16:9', '9:21', '21:9']; size=None; snapshot present=True
- `openai/gpt-image-2.6-flare/text-to-image`: enum=['1:1', '1:2', '2:1', '1:3', '3:1', '2:3', '3:2', '3:4', '4:3', '4:5', '5:4', '9:16', '16:9', '9:21', '21:9']; size=None; snapshot present=True
- `recraft-ai/recraft-v3`: enum=['1:1', '16:9', '9:16', '4:3', '3:4']; size=None; snapshot present=True

Every row previously could lose user intent in run_hint/chat/relay/flat or call/ref defaults, then frontend/provider nearest-ratio mapping. New explicit intent wins chat+relay, carries through real frontend and is checked against the FINAL provider schema and final payload before submit; incompatible models refuse with alternatives, not a model switch. No explicit user ratio retains default plans/counts/refs. Multi-call image counts stay unchanged; six video skills here cover image/still calls ONLY. No992/993/990 scope. auto_models.json and pins unchanged. Photo-split4:5 is an already-default control on this base; photo9:16 additionally proves override.

Representative generic prompts only. Auto is prompt/ref dependent; explicit model pins remain unchanged. Final runtime schema validation is authoritative. Provider runtime was mocked; live paid runtime NOT tested.
