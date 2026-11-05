# Lovart raw index

Sources: _har_quarantine/{lovart,lovart-official,lovart-missing}.masked.har. Two card types: `collection_card` (template modal, via feed/get + recall) and `skill_plaza_card` (example modal, via feed/recall SHOWCASE_* and plaza/for-you/list; no feed/get). Files named `*.plaza.json` are the plaza card for a skillKey that also has a collection card.

| skillKey | zh title | itemId | card type | source endpoint | collectionMemberCount | feed/get | media count | file |
|---|---|---|---|---|---|---|---|---|
| amazon-product-a-plus-content | Amazon A+ 内容页 | 2quhxjqd40e8 | collection_card (template) | feed/recall | 6 | no | media 0 | `amazon-product-a-plus-content.json` |
| amazon-product-listing-images | Amazon 规格说明图 | 2quhxj84cyyo | collection_card (template) | feed/recall | 6 | no | media 0 | `amazon-product-listing-images.json` |
| app-store-launch-kit | App 上架素材 | 2quhxl3m3xts | collection_card (template) | feed/recall | 0 | no | media 0 | `app-store-launch-kit.json` |
| banner-design-director | 横幅设计 | pe9nryLm8M | skill_plaza_card (example) | feed/plaza/for-you/list, feed/recall | - | no (none fires) | highlights 1, coverList 0 | `banner-design-director.json` |
| brand-identity-director | Logo 系统 | 2quhxjqfm680 | collection_card (template) | feed/get | 6 | yes | media 0 | `brand-identity-director.json` |
| brand-identity-director | 品牌识别 | pe2OsxQJfW | skill_plaza_card (example) | feed/plaza/for-you/homepage, feed/plaza/for-you/list, feed/recall | - | no (none fires) | highlights 11, coverList 0 | `brand-identity-director.plaza.json` |
| character-sheet-design | 真人角色设定与参考板 | 2quhxlmeufi8 | collection_card (template) | feed/get | 7 | yes | media 0 | `character-sheet-design.json` |
| character-sheet-design | 角色设定表设计 | pdZIplhfHO | skill_plaza_card (example) | feed/plaza/for-you/list, feed/recall | - | no (none fires) | highlights 6, coverList 0 | `character-sheet-design.plaza.json` |
| cover-design-director | 封面设计总监 | pj7436Pnjy | skill_plaza_card (example) | feed/plaza/for-you/homepage, feed/plaza/for-you/list, feed/recall | - | no (none fires) | highlights 1, coverList 0 | `cover-design-director.json` |
| interior-architectural-visualization-<masked>-<masked> | 室内与建筑可视化 | 2q24865beubk | skill_plaza_card (example) | feed/plaza/for-you/list, feed/recall | - | no (none fires) | highlights 4, coverList 1 | `interior-architectural-visualization.json` |
| interior-design-rough-to-render-<masked>-<masked> | 毛坯房直出室内效果 | 2pyna75bgv0g | skill_plaza_card (example) | feed/plaza/for-you/list, feed/recall | - | no (none fires) | highlights 2, coverList 3 | `interior-design-rough-to-render.json` |
| logo-material-explorer | 徽标材质探索器 | pweyUNiCPe | skill_plaza_card (example) | feed/recall | - | no (none fires) | highlights 3, coverList 0 | `logo-material-explorer.plaza.json` |
| manga-character-sheet | 动漫角色设定与参考板 | 2quhxl3m47b5 | collection_card (template) | feed/get | 7 | yes | media 0 | `manga-character-sheet.json` |
| manga-character-sheet | 漫画角色设定表 | pj8GMcJHag | skill_plaza_card (example) | feed/plaza/for-you/homepage, feed/plaza/for-you/list, feed/recall | - | no (none fires) | highlights 3, coverList 0 | `manga-character-sheet.plaza.json` |
| marketing-campaign-generator | 营销活动生成器 | pj0hKQ225i | skill_plaza_card (example) | feed/plaza/for-you/homepage, feed/plaza/for-you/list, feed/recall | - | no (none fires) | highlights 8, coverList 0 | `marketing-campaign-generator.json` |
| meta-ads-creative-director | Meta广告创意 | pkDx6GTC6c | skill_plaza_card (example) | feed/plaza/for-you/homepage, feed/plaza/for-you/list, feed/recall | - | no (none fires) | highlights 4, coverList 0 | `meta-ads-creative-director.json` |
| mobile-app-visual-design | App 核心页面 | 2quhxkaesxs0 | collection_card (template) | feed/get | 5 | yes | media 0 | `mobile-app-visual-design.json` |
| mobile-app-visual-design | 移动应用视觉设计 | pkzaYTV27u | skill_plaza_card (example) | feed/plaza/for-you/homepage, feed/plaza/for-you/list, feed/recall | - | no (none fires) | highlights 13, coverList 0 | `mobile-app-visual-design.plaza.json` |
| motion-poster-generator | 动态海报 | 2sf3x9tciiv4 | collection_card (template) | feed/get | 2 | yes | media 1 | `motion-poster-generator.json` |
| multi-angle-photo-from-references-<masked>-<masked> | 参考图片多角度摄影 | 2porqzqzmeww | skill_plaza_card (example) | feed/plaza/for-you/list, feed/recall | - | no (none fires) | highlights 6, coverList 0 | `multi-angle-photo-from-references.json` |
| packaging-design-director | 品牌包装设计系统 | 2quhxk9auark | collection_card (template) | feed/get | 5 | yes | media 0 | `packaging-design-director.json` |
| poster-differentiated-compiler | 海报设计 | pdVO0ozfGM | skill_plaza_card (example) | feed/plaza/for-you/list, feed/recall | - | no (none fires) | highlights 5, coverList 0 | `poster-differentiated-compiler.json` |
| product-tvc-advertisement-generator | 产品广告片 | 2sf3x9tcisch | collection_card (template) | feed/recall | 7 | no | media 1 | `product-tvc-advertisement-generator.json` |
| rednote-cover-maker | 小红书封面制作器 | pjj7diI7v2 | skill_plaza_card (example) | feed/plaza/for-you/list, feed/recall | - | no (none fires) | highlights 10, coverList 0 | `rednote-cover-maker.json` |
| scene-photo-to-rendering-<masked>-<masked> | 场景图美化效果图 | 2orgsqbkdvcw | skill_plaza_card (example) | feed/plaza/for-you/list, feed/recall | - | no (none fires) | highlights 2, coverList 0 | `scene-photo-to-rendering.json` |
| taobao | 淘宝商品详情页 | 2quhxj75e4n4 | collection_card (template) | feed/recall | 6 | no | media 0 | `taobao.json` |
| ugc-ad-video | UGC 广告视频导演 | 2sf3x9tciscg | collection_card (template) | feed/recall | 1 | no | media 1 | `ugc-ad-video.json` |
| universal-multi-angle-grid | 多角度图像生成器 | pj7ljezKxy | skill_plaza_card (example) | feed/plaza/for-you/homepage, feed/plaza/for-you/list, feed/recall | - | no (none fires) | highlights 11, coverList 6 | `universal-multi-angle-grid.json` |
| video-remake | 爆款视频复刻 | 2sf3x9ta0mio | collection_card (template) | feed/recall | 1 | no | media 5 | `video-remake.json` |
| web-product-visual-design | Web产品视觉设计 | pjo9VdVZok | skill_plaza_card (example) | feed/plaza/for-you/homepage, feed/plaza/for-you/list, feed/recall | - | no (none fires) | highlights 9, coverList 0 | `web-product-visual-design.json` |

## Final skill table (product ruling)

| old id | new id | raw file | card type | zh name | en name |
|---|---|---|---|---|---|
| thumbnail | cover-design-director | `cover-design-director.json` | example | 封面设计总监 | Cover Design Director |
| poster | poster-differentiated-compiler | `poster-differentiated-compiler.json` | example | 海报设计 | Poster Design |
| meta-ads | meta-ads-creative-director | `meta-ads-creative-director.json` | example | Meta广告创意 | Meta Ads Creative |
| marketing-campaign | marketing-campaign-generator | `marketing-campaign-generator.json` | example | 营销活动生成器 | Marketing Campaign Generator |
| banner | banner-design-director | `banner-design-director.json` | example | 横幅设计 | Banner Design |
| character | character-sheet-design | `character-sheet-design.json` | template | 真人角色设定与参考板 | Realistic Human Character Design & Reference Sheets |
| logo-material | logo-material-explorer | `logo-material-explorer.plaza.json` | example | 徽标材质探索器 | Logo Material Explorer |
| mobile-ui | mobile-app-visual-design | `mobile-app-visual-design.plaza.json` | example | 移动应用视觉设计 | Mobile APP Visual Design |
| web-product | web-product-visual-design | `web-product-visual-design.json` | example | Web产品视觉设计 | Web Product Visual Design |
| multi-angle | universal-multi-angle-grid | `universal-multi-angle-grid.json` | example | 多角度图像生成器 | Multi-Angle Image Generator |
| interior | interior-architectural-visualization | `interior-architectural-visualization.json` (source key `interior-architectural-visualization-<masked>-<masked>`) | example | 室内与建筑可视化 | Interior & Architectural Visualization |
| packaging | packaging-design-director | `packaging-design-director.json` | template | 品牌包装设计系统 | Brand Packaging Design System |
| motion | motion-poster-generator | `motion-poster-generator.json` | template | 动态海报 | Motion Poster |
| product | product-tvc-advertisement-generator | `product-tvc-advertisement-generator.json` | template | 产品广告片 | Product Commercial |
| brand | brand-identity-director | `brand-identity-director.json` | template | Logo 系统 | Logo System |
| social | rednote-cover-maker | `rednote-cover-maker.json` | example | 小红书封面制作器 | RedNote Cover Maker |

## Mapping: our id → Lovart skillKey

| our id | Lovart skillKey | zh title | status |
|---|---|---|---|
| thumbnail | cover-design-director | 封面设计总监 | confirmed (plaza extra.i18n_title.zh) |
| poster | poster-differentiated-compiler | 海报设计 | confirmed |
| meta-ads | meta-ads-creative-director | Meta广告创意 | confirmed |
| marketing-campaign | marketing-campaign-generator | 营销活动生成器 | confirmed |
| banner | banner-design-director | 横幅设计 | confirmed |
| character | character-sheet-design | 真人角色设定与参考板 (collection) / 角色设定表设计 (plaza) | confirmed: same skillKey on both cards |
| logo-material | logo-material-explorer | 徽标材质探索器 | confirmed: plaza extra.skillKey, template captured in feed/recall (lovart-logo-material.masked.har) |
| mobile-ui | mobile-app-visual-design | App 核心页面 (collection) / 移动应用视觉设计 (plaza) | confirmed: same skillKey |
| web-product | web-product-visual-design | Web产品视觉设计 | confirmed |
| multi-angle | universal-multi-angle-grid | 多角度图像生成器 | confirmed by title; 参考图片多角度摄影 is a separate UGC skill |
| interior | interior-architectural-visualization-1789421886-… | 室内与建筑可视化 | GUESS by title; it is a UGC skill (timestamped key), not industry |
| packaging | packaging-design-director | 品牌包装设计系统 / 包装设计 | confirmed |
| motion | motion-poster-generator | 动态海报 (collection) / 动态海报生成器 (plaza) | confirmed |
| product | product-tvc-advertisement-generator | 产品广告片 / 产品电视广告 | confirmed: same skillKey on both cards |
| brand | brand-identity-director | 品牌识别 (plaza) = Logo 系统 (collection) | confirmed: 品牌识别 shares skillKey with Logo 系统 |
| social | rednote-cover-maker | 小红书封面制作器 | confirmed |

## to-wash list

URLs stay in raw/ only and must never go into skills.ts.

| skillKey | member title | role | kind | WxH |
|---|---|---|---|---|
| amazon-product-a-plus-content | 食品 | RESULT | image (png) | 1280x528 |
| amazon-product-a-plus-content | 食品 | RESULT | image (png) | 1280x528 |
| amazon-product-a-plus-content | 食品 | RESULT | image (png) | 1280x528 |
| amazon-product-a-plus-content | 食品 | RESULT | image (png) | 1280x528 |
| amazon-product-a-plus-content | 食品 | RESULT | image (png) | 1472x608 |
| amazon-product-a-plus-content | 男装 | RESULT | image (png) | 1280x528 |
| amazon-product-a-plus-content | 男装 | RESULT | image (png) | 1280x528 |
| amazon-product-a-plus-content | 男装 | RESULT | image (png) | 1280x528 |
| amazon-product-a-plus-content | 男装 | RESULT | image (png) | 1280x528 |
| amazon-product-a-plus-content | 男装 | RESULT | image (png) | 1280x528 |
| amazon-product-a-plus-content | 女装 | RESULT | image (png) | 1040x640 |
| amazon-product-a-plus-content | 女装 | RESULT | image (png) | 1040x640 |
| amazon-product-a-plus-content | 女装 | RESULT | image (png) | 1040x640 |
| amazon-product-a-plus-content | 女装 | RESULT | image (png) | 1040x640 |
| amazon-product-a-plus-content | 女装 | RESULT | image (png) | 1040x640 |
| amazon-product-a-plus-content | 家居 | RESULT | image (png) | 1280x720 |
| amazon-product-a-plus-content | 家居 | RESULT | image (png) | 1280x720 |
| amazon-product-a-plus-content | 家居 | RESULT | image (png) | 1280x720 |
| amazon-product-a-plus-content | 家居 | RESULT | image (png) | 1280x720 |
| amazon-product-a-plus-content | 家居 | RESULT | image (png) | 1280x720 |
| amazon-product-a-plus-content | 数码 | RESULT | image (png) | 2048x1152 |
| amazon-product-a-plus-content | 数码 | RESULT | image (png) | 1280x720 |
| amazon-product-a-plus-content | 数码 | RESULT | image (png) | 1280x720 |
| amazon-product-a-plus-content | 数码 | RESULT | image (png) | 1280x720 |
| amazon-product-a-plus-content | 数码 | RESULT | image (png) | 2048x1152 |
| amazon-product-a-plus-content | 美妆 | RESULT | image (png) | 1280x528 |
| amazon-product-a-plus-content | 美妆 | RESULT | image (png) | 1280x528 |
| amazon-product-a-plus-content | 美妆 | RESULT | image (png) | 1280x528 |
| amazon-product-a-plus-content | 美妆 | RESULT | image (png) | 1280x528 |
| amazon-product-a-plus-content | 美妆 | RESULT | image (png) | 1280x528 |
| amazon-product-listing-images | 女装 | RESULT | image (png) | 360x360 |
| amazon-product-listing-images | 男装 | RESULT | image (png) | 360x360 |
| amazon-product-listing-images | 美妆 | RESULT | image (png) | 1280x1280 |
| amazon-product-listing-images | 数码 | RESULT | image (png) | 1280x1280 |
| amazon-product-listing-images | 食品 | RESULT | image (png) | 1280x1280 |
| amazon-product-listing-images | 家居 | RESULT | image (png) | 1280x1280 |
| banner-design-director | (cover) | cover | video | 960x720 |
| banner-design-director | (highlights #0) | highlight | video | 960x720 |
| brand-identity-director | 餐饮服务 | RESULT | image (png) | 360x360 |
| brand-identity-director | 餐饮服务 | RESULT | image (png) | 360x360 |
| brand-identity-director | 餐饮服务 | RESULT | image (png) | 360x360 |
| brand-identity-director | 餐饮服务 | RESULT | image (png) | 1280x720 |
| brand-identity-director | 服装配饰 | RESULT | image (png) | 1280x1280 |
| brand-identity-director | 服装配饰 | RESULT | image (png) | 1280x1280 |
| brand-identity-director | 服装配饰 | RESULT | image (png) | 1280x1280 |
| brand-identity-director | 服装配饰 | RESULT | image (png) | 1280x720 |
| brand-identity-director | 美妆个护 | RESULT | image (png) | 679x725 |
| brand-identity-director | 美妆个护 | RESULT | image (png) | 565x738 |
| brand-identity-director | 美妆个护 | RESULT | image (png) | 641x719 |
| brand-identity-director | 美妆个护 | RESULT | image (jpeg) | 1280x720 |
| brand-identity-director | 食品饮料 | RESULT | image (png) | 1280x1280 |
| brand-identity-director | 食品饮料 | RESULT | image (png) | 360x360 |
| brand-identity-director | 食品饮料 | RESULT | image (png) | 360x360 |
| brand-identity-director | 食品饮料 | RESULT | image (png) | 360x202 |
| brand-identity-director | 宠物用品 | RESULT | image (png) | 360x360 |
| brand-identity-director | 宠物用品 | RESULT | image (png) | 1254x1254 |
| brand-identity-director | 宠物用品 | RESULT | image (png) | 1254x1254 |
| brand-identity-director | 宠物用品 | RESULT | image (png) | 1280x1280 |
| brand-identity-director | 家居生活 | RESULT | image (png) | 360x240 |
| brand-identity-director | 家居生活 | RESULT | image (png) | 360x240 |
| brand-identity-director | 家居生活 | RESULT | image (png) | 360x240 |
| brand-identity-director | 家居生活 | RESULT | image (png) | 360x202 |
| brand-identity-director | (cover) | cover | video | 640x480 |
| brand-identity-director | (highlights #0) | highlight | video | 1440x1080 |
| brand-identity-director | (highlights #1) | highlight | image | 2048x1536 |
| brand-identity-director | (highlights #2) | highlight | image | 2048x1152 |
| brand-identity-director | (highlights #3) | highlight | image | 2048x1152 |
| brand-identity-director | (highlights #4) | highlight | image | 2048x1152 |
| brand-identity-director | (highlights #5) | highlight | image | 2048x1152 |
| brand-identity-director | (highlights #6) | highlight | image | 2048x1152 |
| brand-identity-director | (highlights #7) | highlight | image | 2048x1152 |
| brand-identity-director | (highlights #8) | highlight | image | 2048x1536 |
| brand-identity-director | (highlights #9) | highlight | image | 2048x1152 |
| brand-identity-director | (highlights #10) | highlight | image | 2048x1152 |
| character-sheet-design | 角色转身板 | RESULT | image (png) | 2048x2048 |
| character-sheet-design | 表情动作板 | RESULT | image (png) | 3840x2160 |
| character-sheet-design | 建模细节参考板 | RESULT | image (png) | 2048x1152 |
| character-sheet-design | 服装/形态变体板 | RESULT | image (png) | 2048x2048 |
| character-sheet-design | 道具互动板 | RESULT | image (png) | 1024x1024 |
| character-sheet-design | 基础角色板 | RESULT | image (png) | 3840x2160 |
| character-sheet-design | 完整技术角色板 | RESULT | image (png) | 2048x1152 |
| character-sheet-design | (cover) | cover | video | 960x718 |
| character-sheet-design | (highlights #0) | highlight | image | 2048x1152 |
| character-sheet-design | (highlights #1) | highlight | image | 1536x1024 |
| character-sheet-design | (highlights #2) | highlight | image | 1536x2048 |
| character-sheet-design | (highlights #3) | highlight | image | 2048x1152 |
| character-sheet-design | (highlights #4) | highlight | image | 2048x1152 |
| character-sheet-design | (highlights #5) | highlight | image | 2048x1152 |
| cover-design-director | (cover) | cover | video | 960x720 |
| cover-design-director | (highlights #0) | highlight | video | 960x720 |
| interior-architectural-visualization-<masked>-<masked> | (cover) | cover | image | 2048x2048 |
| interior-architectural-visualization-<masked>-<masked> | (coverList) | coverList | image | 2048x2048 |
| interior-architectural-visualization-<masked>-<masked> | (highlights #0) | highlight | image | 1600x2000 |
| interior-architectural-visualization-<masked>-<masked> | (highlights #1) | highlight | image | 1600x2000 |
| interior-architectural-visualization-<masked>-<masked> | (highlights #2) | highlight | image | 1600x2000 |
| interior-architectural-visualization-<masked>-<masked> | (highlights #3) | highlight | image | 2048x2048 |
| interior-design-rough-to-render-<masked>-<masked> | (cover) | cover | image | 1841x2279 |
| interior-design-rough-to-render-<masked>-<masked> | (coverList) | coverList | image | 1841x2279 |
| interior-design-rough-to-render-<masked>-<masked> | (coverList) | coverList | image | 1600x2000 |
| interior-design-rough-to-render-<masked>-<masked> | (coverList) | coverList | image | 1600x2000 |
| interior-design-rough-to-render-<masked>-<masked> | (highlights #0) | highlight | image | 928x1152 |
| interior-design-rough-to-render-<masked>-<masked> | (highlights #1) | highlight | image | 1600x2000 |
| manga-character-sheet | 角色转身板 | RESULT | image (png) | 1024x1024 |
| manga-character-sheet | 建模细节参考板 | RESULT | image (png) | 2048x2048 |
| manga-character-sheet | 道具互动板 | RESULT | image (png) | 1024x1024 |
| manga-character-sheet | 表情动作板 | RESULT | image (png) | 1024x1024 |
| manga-character-sheet | 基础角色板 | RESULT | image (png) | 1024x1024 |
| manga-character-sheet | 服装/形态变体板 | RESULT | image (png) | 1024x1024 |
| manga-character-sheet | 完整技术角色板 | RESULT | image (png) | 2048x1152 |
| logo-material-explorer | (cover) | cover | video | 960x720 |
| logo-material-explorer | (highlights #0) | highlight | video | 960x720 |
| logo-material-explorer | (highlights #1) | highlight | image | 1254x1254 |
| logo-material-explorer | (highlights #2) | highlight | image | 1254x1254 |
| manga-character-sheet | (cover) | cover | video | 640x480 |
| manga-character-sheet | (highlights #0) | highlight | video | 1112x834 |
| manga-character-sheet | (highlights #1) | highlight | image | 1536x1024 |
| manga-character-sheet | (highlights #2) | highlight | image | 2048x1152 |
| marketing-campaign-generator | (cover) | cover | video | 1440x1080 |
| marketing-campaign-generator | (highlights #0) | highlight | video | 1440x1080 |
| marketing-campaign-generator | (highlights #1) | highlight | image | 4605x900 |
| marketing-campaign-generator | (highlights #2) | highlight | image | 4106x480 |
| marketing-campaign-generator | (highlights #3) | highlight | image | 3070x480 |
| marketing-campaign-generator | (highlights #4) | highlight | image | 3070x600 |
| marketing-campaign-generator | (highlights #5) | highlight | image | 3070x600 |
| marketing-campaign-generator | (highlights #6) | highlight | image | 3588x480 |
| marketing-campaign-generator | (highlights #7) | highlight | image | 3588x854 |
| meta-ads-creative-director | (cover) | cover | video | 640x480 |
| meta-ads-creative-director | (highlights #0) | highlight | image | 2048x1152 |
| meta-ads-creative-director | (highlights #1) | highlight | image | 2048x1152 |
| meta-ads-creative-director | (highlights #2) | highlight | image | 2048x1152 |
| meta-ads-creative-director | (highlights #3) | highlight | image | 2048x1152 |
| mobile-app-visual-design | 电商零售 | RESULT | image (png) | 960x2048 |
| mobile-app-visual-design | 电商零售 | RESULT | image (png) | 960x2048 |
| mobile-app-visual-design | 电商零售 | RESULT | image (png) | 960x2048 |
| mobile-app-visual-design | 电商零售 | RESULT | image (png) | 960x2048 |
| mobile-app-visual-design | 健康运动 | RESULT | image (png) | 1152x2048 |
| mobile-app-visual-design | 健康运动 | RESULT | image (png) | 1152x2048 |
| mobile-app-visual-design | 健康运动 | RESULT | image (png) | 1152x2048 |
| mobile-app-visual-design | 健康运动 | RESULT | image (png) | 1152x2048 |
| mobile-app-visual-design | 效率工具 | RESULT | image (png) | 1152x2048 |
| mobile-app-visual-design | 效率工具 | RESULT | image (png) | 1152x2048 |
| mobile-app-visual-design | 效率工具 | RESULT | image (png) | 1152x2048 |
| mobile-app-visual-design | 效率工具 | RESULT | image (png) | 1152x2048 |
| mobile-app-visual-design | 金融支付 | RESULT | image (png) | 693x1413 |
| mobile-app-visual-design | 金融支付 | RESULT | image (png) | 685x1404 |
| mobile-app-visual-design | 金融支付 | RESULT | image (png) | 685x1477 |
| mobile-app-visual-design | 金融支付 | RESULT | image (png) | 685x1432 |
| mobile-app-visual-design | 内容娱乐 | RESULT | image (jpg) | 960x2048 |
| mobile-app-visual-design | 内容娱乐 | RESULT | image (jpg) | 960x2048 |
| mobile-app-visual-design | 内容娱乐 | RESULT | image (jpg) | 960x2048 |
| mobile-app-visual-design | 内容娱乐 | RESULT | image (jpg) | 960x2048 |
| mobile-app-visual-design | (cover) | cover | video | 640x480 |
| mobile-app-visual-design | (highlights #0) | highlight | image | 2048x1152 |
| mobile-app-visual-design | (highlights #1) | highlight | image | 2048x1152 |
| mobile-app-visual-design | (highlights #2) | highlight | image | 2048x688 |
| mobile-app-visual-design | (highlights #3) | highlight | image | 2048x1024 |
| mobile-app-visual-design | (highlights #4) | highlight | image | 2048x1024 |
| mobile-app-visual-design | (highlights #5) | highlight | image | 2048x1024 |
| mobile-app-visual-design | (highlights #6) | highlight | image | 2048x1152 |
| mobile-app-visual-design | (highlights #7) | highlight | image | 2048x1024 |
| mobile-app-visual-design | (highlights #8) | highlight | image | 2048x1152 |
| mobile-app-visual-design | (highlights #9) | highlight | image | 2048x1152 |
| mobile-app-visual-design | (highlights #10) | highlight | image | 2048x1024 |
| mobile-app-visual-design | (highlights #11) | highlight | image | 2016x1344 |
| mobile-app-visual-design | (highlights #12) | highlight | image | 2048x1152 |
| motion-poster-generator | (collection) | RESULT | video (mp4) | 1324x992 |
| motion-poster-generator | 海报动效 | RESULT | video (mp4) | 1324x992 |
| motion-poster-generator | 首尾帧动画 | RESULT | video (mp4) | 1080x1920 |
| multi-angle-photo-from-references-<masked>-<masked> | (cover) | cover | video | 1920x1080 |
| multi-angle-photo-from-references-<masked>-<masked> | (highlights #0) | highlight | image | 1088x1920 |
| multi-angle-photo-from-references-<masked>-<masked> | (highlights #1) | highlight | image | 1088x1920 |
| multi-angle-photo-from-references-<masked>-<masked> | (highlights #2) | highlight | image | 1088x1920 |
| multi-angle-photo-from-references-<masked>-<masked> | (highlights #3) | highlight | image | 1088x1920 |
| multi-angle-photo-from-references-<masked>-<masked> | (highlights #4) | highlight | image | 1088x1920 |
| multi-angle-photo-from-references-<masked>-<masked> | (highlights #5) | highlight | image | 1088x1920 |
| packaging-design-director | 主款包装设计 | RESULT | image (png) | 270x360 |
| packaging-design-director | 包装视觉方向 | RESULT | image (png) | 360x202 |
| packaging-design-director | 包装视觉方向 | RESULT | image (png) | 1280x720 |
| packaging-design-director | 包装视觉方向 | RESULT | image (png) | 1280x720 |
| packaging-design-director | 多 SKU 包装系列 | RESULT | image (png) | 270x360 |
| packaging-design-director | 多 SKU 包装系列 | RESULT | image (png) | 960x1280 |
| packaging-design-director | 多 SKU 包装系列 | RESULT | image (png) | 960x1280 |
| packaging-design-director | 多 SKU 包装系列 | RESULT | image (png) | 1280x720 |
| packaging-design-director | 包装面板与结构示意 | RESULT | image (png) | 1280x720 |
| packaging-design-director | 包装货架展示 | RESULT | image (png) | 360x202 |
| poster-differentiated-compiler | (cover) | cover | video | 640x480 |
| poster-differentiated-compiler | (highlights #0) | highlight | image | 1344x2016 |
| poster-differentiated-compiler | (highlights #1) | highlight | image | 960x1280 |
| poster-differentiated-compiler | (highlights #2) | highlight | image | 853x1280 |
| poster-differentiated-compiler | (highlights #3) | highlight | image | 240x360 |
| poster-differentiated-compiler | (highlights #4) | highlight | image | 1152x2048 |
| product-tvc-advertisement-generator | (collection) | RESULT | video (mp4) | 640x480 |
| product-tvc-advertisement-generator | 美妆 | RESULT | video (mp4) | 1920x1080 |
| product-tvc-advertisement-generator | 服装 | RESULT | video (mp4) | 1280x720 |
| product-tvc-advertisement-generator | 食品饮料 | RESULT | video (mp4) | 1280x720 |
| product-tvc-advertisement-generator | 数码 | RESULT | video (mp4) | 1280x720 |
| product-tvc-advertisement-generator | 家居 | RESULT | video (mp4) | 1280x720 |
| product-tvc-advertisement-generator | 户外 | RESULT | video (mp4) | 1280x720 |
| product-tvc-advertisement-generator | 软件 | RESULT | video (mp4) | 1920x1080 |
| rednote-cover-maker | (cover) | cover | video | 640x480 |
| rednote-cover-maker | (highlights #0) | highlight | image | 1536x2048 |
| rednote-cover-maker | (highlights #1) | highlight | image | 1086x1448 |
| rednote-cover-maker | (highlights #2) | highlight | image | 1086x1448 |
| rednote-cover-maker | (highlights #3) | highlight | image | 1536x2048 |
| rednote-cover-maker | (highlights #4) | highlight | image | 1536x2048 |
| rednote-cover-maker | (highlights #5) | highlight | image | 1536x2048 |
| rednote-cover-maker | (highlights #6) | highlight | image | 1536x2048 |
| rednote-cover-maker | (highlights #7) | highlight | image | 1536x2048 |
| rednote-cover-maker | (highlights #8) | highlight | image | 1536x2048 |
| rednote-cover-maker | (highlights #9) | highlight | image | 1536x2048 |
| scene-photo-to-rendering-<masked>-<masked> | (cover) | cover | image | 1536x2048 |
| scene-photo-to-rendering-<masked>-<masked> | (highlights #0) | highlight | image | 1792x2400 |
| scene-photo-to-rendering-<masked>-<masked> | (highlights #1) | highlight | image | 1792x2400 |
| taobao | 家居 | RESULT | image (png) | 750x8000 |
| taobao | 女装 | RESULT | image (png) | 750x8125 |
| taobao | 男装 | RESULT | image (png) | 750x9000 |
| taobao | 食品 | RESULT | image (png) | 1536x20480 |
| taobao | 数码 | RESULT | image (png) | 750x6000 |
| taobao | 美妆 | RESULT | image (png) | 1536x20479 |
| ugc-ad-video | (collection) | RESULT | video (mp4) | 640x480 |
| ugc-ad-video | 产品种草 | RESULT | video (mp4) | 720x1280 |
| universal-multi-angle-grid | (cover) | cover | image | 640x480 |
| universal-multi-angle-grid | (coverList) | coverList | image | 640x480 |
| universal-multi-angle-grid | (coverList) | coverList | image | 1536x1152 |
| universal-multi-angle-grid | (coverList) | coverList | image | 1062x796 |
| universal-multi-angle-grid | (coverList) | coverList | image | 1816x1362 |
| universal-multi-angle-grid | (coverList) | coverList | image | 1536x1152 |
| universal-multi-angle-grid | (coverList) | coverList | image | 1536x1152 |
| universal-multi-angle-grid | (highlights #0) | highlight | image | 1536x2048 |
| universal-multi-angle-grid | (highlights #1) | highlight | image | 1536x2048 |
| universal-multi-angle-grid | (highlights #2) | highlight | image | 1536x2048 |
| universal-multi-angle-grid | (highlights #3) | highlight | image | 1536x2048 |
| universal-multi-angle-grid | (highlights #4) | highlight | image | 1536x2048 |
| universal-multi-angle-grid | (highlights #5) | highlight | image | 1536x2048 |
| universal-multi-angle-grid | (highlights #6) | highlight | image | 1536x2048 |
| universal-multi-angle-grid | (highlights #7) | highlight | image | 1536x2048 |
| universal-multi-angle-grid | (highlights #8) | highlight | image | 1536x2048 |
| universal-multi-angle-grid | (highlights #9) | highlight | image | 1536x2048 |
| universal-multi-angle-grid | (highlights #10) | highlight | image | 1536x2048 |
| video-remake | (collection) | RESULT | video (mp4) | 1440x1920 |
| video-remake | (collection) | RESULT | video (mp4) | 1280x720 |
| video-remake | (collection) | RESULT | video (mp4) | 1440x2560 |
| video-remake | (collection) | RESULT | video (mp4) | 1440x810 |
| video-remake | (collection) | RESULT | video (mp4) | 1440x810 |
| video-remake | 自定义复刻 | RESULT | video (mp4) | 1440x1920 |
| web-product-visual-design | (cover) | cover | video | 640x480 |
| web-product-visual-design | (highlights #0) | highlight | image | 2048x1280 |
| web-product-visual-design | (highlights #1) | highlight | image | 1152x2048 |
| web-product-visual-design | (highlights #2) | highlight | image | 2048x1152 |
| web-product-visual-design | (highlights #3) | highlight | image | 1536x1024 |
| web-product-visual-design | (highlights #4) | highlight | image | 2048x1152 |
| web-product-visual-design | (highlights #5) | highlight | image | 2048x1152 |
| web-product-visual-design | (highlights #6) | highlight | image | 2048x1152 |
| web-product-visual-design | (highlights #7) | highlight | image | 2048x1152 |
| web-product-visual-design | (highlights #8) | highlight | image | 2048x1152 |

## Confirmed mapping for the 33 (lovart.ai only, 2026-11-05)

Ruling: lovart.ai only, no .art. Source: rebuilt `feed-list.json` (671 recall cards, zh+en merged, deduped by skillKey). Official = `namespace: industry`; UGC = `user-generated`. Confirmed: 30/33.

| our id | new id (Lovart skillKey) | type | zh / en name | raw file |
|---|---|---|---|---|
| flash-cut-video | `screenshot-flashcut-video-<masked>-<masked>` | UGC | Screenshot → Flash-Cut Video / Screenshot → Flash-Cut Video | `screenshot-flashcut-video.plaza.json` |
| style-transfer | `adaptive-style-transfer-director` | official | Adaptive Style Transfer Director /  | `adaptive-style-transfer-director.plaza.json` |
| person-swap | `fashion-portrait-multi-reference-<masked>-<masked>` | UGC | 电商3图换人 /  | `fashion-portrait-multi-reference.plaza.json` |
| commerce-strategist | `commerce-visual-strategist` | official | Commerce Visual Strategist /  | `commerce-visual-strategist.plaza.json` |
| lifestyle-scene | `marketing-style-lifestyle-scene` | official | E-commerce Lifestyle Scene Designer /  | `marketing-style-lifestyle-scene.plaza.json` |
| logo-abstract | `photo-to-geometric-minimal-logo-<masked>-<masked>` | UGC | 照片转几何极简LOGO /  | `photo-to-geometric-minimal-logo.plaza.json` |
| photo-split-poster | `half-collage-poster-<masked>-<masked>` | UGC | half-collage-poster / half-collage-poster | `half-collage-poster.plaza.json` |
| ppt-visual | `modular-web-ppt-skill-<masked>-<masked>` | UGC | Senior‑Sense PPT Visual Director / Senior‑Sense PPT Visual Director | `modular-web-ppt-skill.plaza.json` |
| promo-ecommerce | `ecommerce-promotion-brand-design` | official | Ecommerce Promotional Branding /  | `ecommerce-promotion-brand-design.plaza.json` |
| crt-interface | `crt-interface-pixel-illustration-<masked>-<masked>` | UGC | CRT复古界面像素插画 / CRT复古界面像素插画 | `crt-interface-pixel-illustration.plaza.json` |
| crayon-sketch | `retro-childrens-book-crayon-<masked>-<masked>` | UGC | 复古极简线条插画风 /  | `retro-childrens-book-crayon.plaza.json` |
| taobao-product | `taobao` | official | Taobao Product Visuals /  | `taobao.plaza.json` |
| before-after | `before-after-visual` | official | Before & After Visual /  | `before-after-visual.plaza.json` |
| anim-2d | `video-to-2d-cartoon-<masked>-<masked>` | UGC | 2D Animation Converter / 2D Animation Converter | `video-to-2d-cartoon.plaza.json` |
| creator-identity | `creator-visual-identity-system` | official | Creator Visual Identity System /  | `creator-visual-identity-system.plaza.json` |
| product-website | `premium-tech-saas-landing-page-<masked>-<masked>` | UGC | Product Website Designer / Product Website Designer | `premium-tech-saas-landing-page.plaza.json` |
| studio-model | `marketing-style-studio-apparel` | official | E-commerce Premium Studio On-Body Shot Designer /  | `marketing-style-studio-apparel.plaza.json` |
| youtube-channel-banner | `youtube-channel-banner-design` | official | YouTube Channel Banner / YouTube Channel Banner | `youtube-channel-banner-design.plaza.json` |
| ai-model | `e-commerce-fashion-model-portrait-generator-<masked>-<masked>` | UGC | AI模特定制生成 /  | `e-commerce-fashion-model-portrait-generator.plaza.json` |
| product-to-packaging | `product-to-packaging-system-<masked>-<masked>` | UGC | Product to Packaging System /  | `product-to-packaging-system.plaza.json` |
| game-art | `game-visual-design-<masked>-<masked>` | UGC | 游戏美术与运营视觉设计 / 游戏美术与运营视觉设计 | `game-visual-design.plaza.json` |
| portrait-studio | `photography-portrait-generator-<masked>-<masked>` | UGC | 摄影级人像生图工具 /  | `photography-portrait-generator.plaza.json` |
| premium-website | `deliver-client-brand-<masked>-<masked>` | UGC | Premium Website Art Director / Premium Website Art Director | `deliver-client-brand.plaza.json` |
| animated-poster | `animated-poster-maker-<masked>-<masked>` | UGC | Animated Poster Maker / Animated Poster Maker | `animated-poster-maker.plaza.json` |
| pose-fission | `character-angle-prompts-<masked>-<masked>` | UGC | 电商同场景角色姿势裂变 /  | `character-angle-prompts.plaza.json` |
| live-promo-decor | `livestream-promo-decor` | official | Livestream Promo Decoration /  | `livestream-promo-decor.plaza.json` |
| linkedin-banner | `linkedin-banner-design` | official | LinkedIn Banner / LinkedIn Banner | `linkedin-banner-design.plaza.json` |
| logo-animation | `logo-5s-motion-video-<masked>-<masked>` | UGC | LOGO animation video /  | `logo-5s-motion-video.plaza.json` |
| restaurant-website | `restaurant-skill-<masked>-<masked>` | UGC | Restaurant Website Creator / Restaurant Website Creator | `restaurant-skill.plaza.json` |
| clothing-swap | `fashion-unified-outfit-change-v2-<masked>-<masked>` | UGC | AI服装换装skill /  | `fashion-unified-outfit-change-v2.plaza.json` |

Notes:
- photo-split-poster → half-collage-poster (top half photo, bottom half abstract geometry sampled from photo colors); split-photo-naive-illustration-poster was the runner-up.
- crayon-sketch → retro-childrens-book-crayon (children-book crayon); freelancer-brand-deliver-kit "Hand-Drawn Crayon" is a brand kit, so it was rejected.
- animated-poster must not collide with motion-poster-generator.
- UGC skillKey suffix hashes equal publisher ids, so they must not be used as public ids in the product.
- #592 flag: brand / motion / product rows were each compared against several cards.

### No .ai match → source comfyart (3)

| our id | verdict | top-3 .ai candidates (rejected) | proposed id |
|---|---|---|---|
| yingzao | no .ai match → source comfyart | city-architectural-field-archive-1789128021 (architecture field poster, no Chinese display type); city-promo-poster-guofeng-1789634824 (guofeng watercolor, not photo); building-photo-to-guochao-line-illustration-1789530563 (line illustration) | `local-editorial-poster-designer` |
| fabric-collage | no .ai match → source comfyart | felt-pet-portrait-1793741060 (felt, pets only); handmade-clay-flat-applique-1791446571 (clay); torn-paper-collage-poster-1791769732 (paper, not cloth) | `fabric-collage-illustrator` |
| naive-illustration | no .ai match → source comfyart | food-doodle-poster-1788599217 (photo product + doodle mini figures); naive-daily-doodle-1792454335 (naive B/W doodle, no giant-vs-tiny); heytea-miniature-food-poster-1788747124 (photo food) | `giant-object-naive-illustrator` |

QA hints checked: naive-editorial-character (character sheet, not scale joke), half-collage-poster (used for photo-split-poster), collage-poetry-poster (torn-paper photo collage; not fabric).

### to-wash additions (2026-11-05)

| skillKey | our id | role | kind | WxH |
|---|---|---|---|---|
| screenshot-flashcut-video-<masked>-<masked> | flash-cut-video | cover | image | 2528x1424 |
| screenshot-flashcut-video-<masked>-<masked> | flash-cut-video | highlight | video | 1920x1080 |
| adaptive-style-transfer-director | style-transfer | cover | video | 960x720 |
| adaptive-style-transfer-director | style-transfer | highlight | image | 1254x1254 |
| adaptive-style-transfer-director | style-transfer | highlight | image | 1254x1254 |
| adaptive-style-transfer-director | style-transfer | highlight | image | 1254x1254 |
| adaptive-style-transfer-director | style-transfer | highlight | image | 1254x1254 |
| fashion-portrait-multi-reference-<masked>-<masked> | person-swap | cover | image | 2560x1896 |
| fashion-portrait-multi-reference-<masked>-<masked> | person-swap | highlight | image | 1536x2048 |
| commerce-visual-strategist | commerce-strategist | cover | video | 1440x1080 |
| commerce-visual-strategist | commerce-strategist | highlight | video | 640x480 |
| marketing-style-lifestyle-scene | lifestyle-scene | cover | video | 960x720 |
| marketing-style-lifestyle-scene | lifestyle-scene | highlight | image | 1536x2048 |
| marketing-style-lifestyle-scene | lifestyle-scene | highlight | image | 800x800 |
| photo-to-geometric-minimal-logo-<masked>-<masked> | logo-abstract | cover | image | 2048x2048 |
| photo-to-geometric-minimal-logo-<masked>-<masked> | logo-abstract | highlight | image | 2048x2048 |
| photo-to-geometric-minimal-logo-<masked>-<masked> | logo-abstract | highlight | image | 2048x2048 |
| photo-to-geometric-minimal-logo-<masked>-<masked> | logo-abstract | highlight | image | 2048x2048 |
| photo-to-geometric-minimal-logo-<masked>-<masked> | logo-abstract | highlight | image | 1254x1254 |
| photo-to-geometric-minimal-logo-<masked>-<masked> | logo-abstract | highlight | image | 1254x1254 |
| photo-to-geometric-minimal-logo-<masked>-<masked> | logo-abstract | highlight | image | 2048x2048 |
| photo-to-geometric-minimal-logo-<masked>-<masked> | logo-abstract | highlight | image | 2048x2048 |
| photo-to-geometric-minimal-logo-<masked>-<masked> | logo-abstract | highlight | image | 2048x2048 |
| photo-to-geometric-minimal-logo-<masked>-<masked> | logo-abstract | highlight | image | 2048x2048 |
| photo-to-geometric-minimal-logo-<masked>-<masked> | logo-abstract | highlight | image | 2048x2048 |
| photo-to-geometric-minimal-logo-<masked>-<masked> | logo-abstract | highlight | image | 2048x2048 |
| half-collage-poster-<masked>-<masked> | photo-split-poster | cover | image | 2016x1344 |
| half-collage-poster-<masked>-<masked> | photo-split-poster | highlight | image | 1200x1600 |
| modular-web-ppt-skill-<masked>-<masked> | ppt-visual | cover | image | 2048x1536 |
| modular-web-ppt-skill-<masked>-<masked> | ppt-visual | highlight | image | 1920x10470 |
| ecommerce-promotion-brand-design | promo-ecommerce | cover | video | 960x720 |
| ecommerce-promotion-brand-design | promo-ecommerce | highlight | image | 2560x2214 |
| ecommerce-promotion-brand-design | promo-ecommerce | highlight | image | 2560x1464 |
| ecommerce-promotion-brand-design | promo-ecommerce | highlight | image | 1519x2560 |
| ecommerce-promotion-brand-design | promo-ecommerce | highlight | image | 1690x2560 |
| crt-interface-pixel-illustration-<masked>-<masked> | crt-interface | cover | image | 738x814 |
| crt-interface-pixel-illustration-<masked>-<masked> | crt-interface | highlight | image | 1536x2048 |
| retro-childrens-book-crayon-<masked>-<masked> | crayon-sketch | cover | video | 858x858 |
| retro-childrens-book-crayon-<masked>-<masked> | crayon-sketch | highlight | image | 1600x1600 |
| retro-childrens-book-crayon-<masked>-<masked> | crayon-sketch | highlight | video | 858x858 |
| taobao | taobao-product | cover | video | 1442x1080 |
| taobao | taobao-product | highlight | image | 2005x497 |
| taobao | taobao-product | highlight | image | 236x2560 |
| taobao | taobao-product | highlight | image | 2005x497 |
| taobao | taobao-product | highlight | image | 240x2560 |
| taobao | taobao-product | highlight | image | 2560x487 |
| taobao | taobao-product | highlight | image | 320x2560 |
| taobao | taobao-product | highlight | image | 2560x487 |
| taobao | taobao-product | highlight | image | 240x2560 |
| before-after-visual | before-after | cover | video | 640x480 |
| before-after-visual | before-after | highlight | image | 1600x2000 |
| before-after-visual | before-after | highlight | image | 1600x2000 |
| before-after-visual | before-after | highlight | image | 1600x2000 |
| before-after-visual | before-after | highlight | image | 1600x2000 |
| before-after-visual | before-after | highlight | image | 1600x2000 |
| before-after-visual | before-after | highlight | image | 1600x2000 |
| before-after-visual | before-after | highlight | image | 1122x1402 |
| before-after-visual | before-after | highlight | image | 1600x2000 |
| video-to-2d-cartoon-<masked>-<masked> | anim-2d | cover | image | 1672x941 |
| video-to-2d-cartoon-<masked>-<masked> | anim-2d | highlight | video | 1080x1920 |
| video-to-2d-cartoon-<masked>-<masked> | anim-2d | highlight | image | 541x979 |
| video-to-2d-cartoon-<masked>-<masked> | anim-2d | highlight | image | 542x979 |
| creator-visual-identity-system | creator-identity | cover | video | 640x480 |
| creator-visual-identity-system | creator-identity | highlight | video | 1440x1078 |
| premium-tech-saas-landing-page-<masked>-<masked> | product-website | cover | image | 1536x1024 |
| premium-tech-saas-landing-page-<masked>-<masked> | product-website | highlight | video | 3360x1530 |
| premium-tech-saas-landing-page-<masked>-<masked> | product-website | highlight | video | 3360x1530 |
| premium-tech-saas-landing-page-<masked>-<masked> | product-website | highlight | video | 3360x1530 |
| marketing-style-studio-apparel | studio-model | cover | video | 960x720 |
| marketing-style-studio-apparel | studio-model | highlight | image | 1536x2048 |
| marketing-style-studio-apparel | studio-model | highlight | image | 750x1000 |
| youtube-channel-banner-design | youtube-channel-banner | cover | video | 640x480 |
| youtube-channel-banner-design | youtube-channel-banner | highlight | image | 2048x1152 |
| youtube-channel-banner-design | youtube-channel-banner | highlight | image | 2048x1152 |
| youtube-channel-banner-design | youtube-channel-banner | highlight | image | 2048x1152 |
| youtube-channel-banner-design | youtube-channel-banner | highlight | image | 3840x1916 |
| youtube-channel-banner-design | youtube-channel-banner | highlight | image | 3840x1916 |
| youtube-channel-banner-design | youtube-channel-banner | highlight | image | 3840x1916 |
| youtube-channel-banner-design | youtube-channel-banner | highlight | image | 3840x1916 |
| youtube-channel-banner-design | youtube-channel-banner | highlight | image | 3840x1916 |
| youtube-channel-banner-design | youtube-channel-banner | highlight | image | 3840x1916 |
| e-commerce-fashion-model-portrait-generator-<masked>-<masked> | ai-model | cover | image | 3584x4800 |
| e-commerce-fashion-model-portrait-generator-<masked>-<masked> | ai-model | highlight | image | 1856x2304 |
| e-commerce-fashion-model-portrait-generator-<masked>-<masked> | ai-model | highlight | image | 1856x2304 |
| e-commerce-fashion-model-portrait-generator-<masked>-<masked> | ai-model | highlight | image | 3676x4564 |
| e-commerce-fashion-model-portrait-generator-<masked>-<masked> | ai-model | highlight | image | 1856x2304 |
| e-commerce-fashion-model-portrait-generator-<masked>-<masked> | ai-model | highlight | image | 1600x2000 |
| e-commerce-fashion-model-portrait-generator-<masked>-<masked> | ai-model | highlight | image | 1600x2000 |
| product-to-packaging-system-<masked>-<masked> | product-to-packaging | cover | image | 2048x1152 |
| product-to-packaging-system-<masked>-<masked> | product-to-packaging | highlight | image | 2048x1152 |
| product-to-packaging-system-<masked>-<masked> | product-to-packaging | highlight | image | 2048x1152 |
| product-to-packaging-system-<masked>-<masked> | product-to-packaging | highlight | image | 2048x1152 |
| product-to-packaging-system-<masked>-<masked> | product-to-packaging | highlight | image | 2048x1152 |
| product-to-packaging-system-<masked>-<masked> | product-to-packaging | highlight | image | 2048x1152 |
| product-to-packaging-system-<masked>-<masked> | product-to-packaging | highlight | image | 2048x1152 |
| product-to-packaging-system-<masked>-<masked> | product-to-packaging | highlight | image | 2048x1152 |
| product-to-packaging-system-<masked>-<masked> | product-to-packaging | highlight | image | 1536x2048 |
| product-to-packaging-system-<masked>-<masked> | product-to-packaging | highlight | image | 2048x1152 |
| product-to-packaging-system-<masked>-<masked> | product-to-packaging | highlight | image | 2048x1152 |
| product-to-packaging-system-<masked>-<masked> | product-to-packaging | highlight | image | 2048x1152 |
| product-to-packaging-system-<masked>-<masked> | product-to-packaging | highlight | image | 2048x1152 |
| product-to-packaging-system-<masked>-<masked> | product-to-packaging | highlight | image | 2016x1344 |
| product-to-packaging-system-<masked>-<masked> | product-to-packaging | highlight | image | 2016x1344 |
| game-visual-design-<masked>-<masked> | game-art | cover | image | 1254x1254 |
| game-visual-design-<masked>-<masked> | game-art | highlight | image | 1088x1920 |
| game-visual-design-<masked>-<masked> | game-art | highlight | image | 2048x2048 |
| game-visual-design-<masked>-<masked> | game-art | highlight | image | 1152x2048 |
| game-visual-design-<masked>-<masked> | game-art | highlight | image | 1088x1920 |
| game-visual-design-<masked>-<masked> | game-art | highlight | image | 2560x1440 |
| game-visual-design-<masked>-<masked> | game-art | highlight | image | 2560x1440 |
| game-visual-design-<masked>-<masked> | game-art | highlight | image | 1088x1920 |
| game-visual-design-<masked>-<masked> | game-art | highlight | image | 1088x1920 |
| game-visual-design-<masked>-<masked> | game-art | highlight | image | 1088x1920 |
| game-visual-design-<masked>-<masked> | game-art | highlight | image | 1088x1920 |
| game-visual-design-<masked>-<masked> | game-art | highlight | image | 1088x1920 |
| game-visual-design-<masked>-<masked> | game-art | highlight | image | 1088x1920 |
| game-visual-design-<masked>-<masked> | game-art | highlight | image | 1088x1920 |
| game-visual-design-<masked>-<masked> | game-art | highlight | image | 1088x1920 |
| game-visual-design-<masked>-<masked> | game-art | highlight | image | 1088x1920 |
| game-visual-design-<masked>-<masked> | game-art | highlight | image | 1088x1920 |
| game-visual-design-<masked>-<masked> | game-art | highlight | image | 1088x1920 |
| game-visual-design-<masked>-<masked> | game-art | highlight | image | 1088x1920 |
| game-visual-design-<masked>-<masked> | game-art | highlight | image | 1088x1920 |
| game-visual-design-<masked>-<masked> | game-art | highlight | image | 1088x1920 |
| photography-portrait-generator-<masked>-<masked> | portrait-studio | cover | image | 800x600 |
| photography-portrait-generator-<masked>-<masked> | portrait-studio | highlight | image | 1242x1656 |
| photography-portrait-generator-<masked>-<masked> | portrait-studio | highlight | image | 1242x1656 |
| photography-portrait-generator-<masked>-<masked> | portrait-studio | highlight | image | 1242x1656 |
| photography-portrait-generator-<masked>-<masked> | portrait-studio | highlight | image | 1242x1656 |
| photography-portrait-generator-<masked>-<masked> | portrait-studio | highlight | image | 1242x1656 |
| photography-portrait-generator-<masked>-<masked> | portrait-studio | highlight | image | 1242x1656 |
| deliver-client-brand-<masked>-<masked> | premium-website | cover | image | 2560x1440 |
| deliver-client-brand-<masked>-<masked> | premium-website | highlight | image | 2560x1440 |
| deliver-client-brand-<masked>-<masked> | premium-website | highlight | image | 2048x1152 |
| deliver-client-brand-<masked>-<masked> | premium-website | highlight | image | 2048x2048 |
| deliver-client-brand-<masked>-<masked> | premium-website | highlight | image | 2048x1536 |
| deliver-client-brand-<masked>-<masked> | premium-website | highlight | image | 2048x1536 |
| deliver-client-brand-<masked>-<masked> | premium-website | highlight | image | 2048x1536 |
| deliver-client-brand-<masked>-<masked> | premium-website | highlight | image | 1536x2048 |
| animated-poster-maker-<masked>-<masked> | animated-poster | cover | video | 834x1112 |
| animated-poster-maker-<masked>-<masked> | animated-poster | highlight | video | 834x1112 |
| animated-poster-maker-<masked>-<masked> | animated-poster | highlight | video | 834x1112 |
| animated-poster-maker-<masked>-<masked> | animated-poster | highlight | video | 834x1112 |
| animated-poster-maker-<masked>-<masked> | animated-poster | highlight | video | 834x1112 |
| character-angle-prompts-<masked>-<masked> | pose-fission | cover | image | 1600x1200 |
| character-angle-prompts-<masked>-<masked> | pose-fission | highlight | image | 3584x4800 |
| character-angle-prompts-<masked>-<masked> | pose-fission | highlight | image | 3584x4800 |
| character-angle-prompts-<masked>-<masked> | pose-fission | highlight | image | 3584x4800 |
| character-angle-prompts-<masked>-<masked> | pose-fission | highlight | image | 3584x4800 |
| livestream-promo-decor | live-promo-decor | cover | video | 960x720 |
| livestream-promo-decor | live-promo-decor | highlight | image | 1280x574 |
| livestream-promo-decor | live-promo-decor | highlight | image | 1280x574 |
| livestream-promo-decor | live-promo-decor | highlight | image | 1280x574 |
| livestream-promo-decor | live-promo-decor | highlight | image | 1280x574 |
| livestream-promo-decor | live-promo-decor | highlight | image | 1280x574 |
| livestream-promo-decor | live-promo-decor | highlight | image | 1280x574 |
| livestream-promo-decor | live-promo-decor | highlight | image | 2228x750 |
| livestream-promo-decor | live-promo-decor | highlight | image | 2228x750 |
| livestream-promo-decor | live-promo-decor | highlight | image | 1280x430 |
| livestream-promo-decor | live-promo-decor | highlight | image | 1280x430 |
| livestream-promo-decor | live-promo-decor | highlight | image | 1280x430 |
| livestream-promo-decor | live-promo-decor | highlight | image | 1280x430 |
| linkedin-banner-design | linkedin-banner | cover | video | 1440x1080 |
| linkedin-banner-design | linkedin-banner | highlight | video | 960x720 |
| logo-5s-motion-video-<masked>-<masked> | logo-animation | cover | video | 1280x720 |
| logo-5s-motion-video-<masked>-<masked> | logo-animation | highlight | video | 1280x720 |
| logo-5s-motion-video-<masked>-<masked> | logo-animation | highlight | video | 1280x720 |
| logo-5s-motion-video-<masked>-<masked> | logo-animation | highlight | video | 1280x720 |
| logo-5s-motion-video-<masked>-<masked> | logo-animation | highlight | video | 1280x720 |
| restaurant-skill-<masked>-<masked> | restaurant-website | cover | video | 960x720 |
| restaurant-skill-<masked>-<masked> | restaurant-website | highlight | image | 1280x708 |
| restaurant-skill-<masked>-<masked> | restaurant-website | highlight | image | 1280x706 |
| restaurant-skill-<masked>-<masked> | restaurant-website | highlight | image | 1280x627 |
| restaurant-skill-<masked>-<masked> | restaurant-website | highlight | image | 1280x635 |
| restaurant-skill-<masked>-<masked> | restaurant-website | highlight | image | 1280x694 |
| restaurant-skill-<masked>-<masked> | restaurant-website | highlight | image | 1280x707 |
| restaurant-skill-<masked>-<masked> | restaurant-website | highlight | image | 1280x701 |
| fashion-unified-outfit-change-v2-<masked>-<masked> | clothing-swap | cover | image | 1792x2400 |
| fashion-unified-outfit-change-v2-<masked>-<masked> | clothing-swap | highlight | image | 1792x2400 |
| fashion-unified-outfit-change-v2-<masked>-<masked> | clothing-swap | highlight | image | 1084x1451 |
