# ComfyArt docs site

VitePress site with English at the root and Chinese under `zh/`. It is published to GitHub Pages at <https://ganjmeng.github.io/ComfyArt/> by `.github/workflows/docs-site.yml` on every push to `main` that touches `docs-site/**`.

```bash
cd docs-site
npm install
npm run dev      # http://localhost:5173/ComfyArt/
npm run build    # output in .vitepress/dist
npm run models   # regenerate the model tables in guides/models.md from api/*.json
```

- Pages live in `guides/*.md` and `zh/guides/*.md`. Every page exists in both languages, and `tests/test_docs_site.py` checks this.
- Images go in `public/images/`. New screenshots go in `public/images/ours/`, taken from our own app against the mock backend.
- Never paste a real WaveSpeed key. Use a placeholder such as `ws_xxxxxxxxxxxxxxxx`.
