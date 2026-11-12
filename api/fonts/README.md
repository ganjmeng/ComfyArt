# Bundled banner font

`ComfyArtBannerSansSC-Bold.otf` and `ComfyArtBannerSansSC-Regular.otf` are used only by
`api/banner_compose.py` (youtube-channel-banner 精确排版 final).

- Source: Noto Sans CJK SC 2.004 (Bold and Regular), https://github.com/notofonts/noto-cjk
- License: SIL Open Font License 1.1, see `OFL.txt` (commercial use allowed).
- Modified version: subset to GB2312 (6,763 hanzi + symbols), ASCII, Latin-1/Latin Extended-A,
  general and CJK punctuation, and full-width forms (8,270 code points). Renamed to
  "ComfyArt Banner Sans SC" as the OFL requires for modified fonts (Adobe's Reserved Font Name
  is "Source"; "Noto" is a Google trademark).
- Characters outside the subset are refused by `banner_compose.missing_glyphs` instead of being
  drawn as empty boxes.
