# ComfyArt Docs Site

The documentation for ComfyArt, built with [Mintlify](https://mintlify.com) for **comfyart.org**. English pages live at the root (`index.mdx`, `guides/`), Chinese pages under `zh/`. Navigation, theme and languages are in `docs.json`. Screenshots are in `images/`.

## Local preview

Mintlify (`mint`) does not run on Node 25+. The wrapper finds a Node 22 install from nvm-windows and uses it for that command only.

```powershell
.\scripts\mint.cmd install   # first time only
.\scripts\mint.cmd           # dev server -> http://localhost:3000
.\scripts\mint.cmd check     # broken-link check
```

If Node 22 is missing: `nvm install 22`.

## Deploy

1. In the Mintlify dashboard, connect the GitHub app to `ganjmeng/ComfyArt` and set the content directory to `docs-site`.
2. Add the custom domain `comfyart.org`, then in Cloudflare add a CNAME `@` → `cname.mintlify.builders` (proxied) plus the TXT records Mintlify shows, and set SSL/TLS to Full.

Every push to `main` then redeploys the site.
