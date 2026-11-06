# QA HOLD tip e160da32

Independent Full-App (`http://127.0.0.1:8285/comfyart/`, Firefox zh-light) against **committed dist** on tip e160da32:

- Dialog labels are raw748 order 美妆/服装/食品饮料/数码/家居/户外/软件 (7)
- Media still #541 still-life: product__white / lifestyle / detail / electronics / food / beauty; 软件 empty
- Tip src/skills.ts has washProduct784 RESULT videos but **dist/ was not rebuilt** in the tip commit (PR files: skills.ts + tests only)

Cover BR wash asset on review-assets d17ae7c9 is MAREN pink lip-tube (source/assets OK). Featured stays WASH_779 NODAL in source. Cannot PASS Full-App until dist rebuild lands on a new tip.
