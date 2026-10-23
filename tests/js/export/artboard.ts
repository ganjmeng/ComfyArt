// Plain (non-styled) frames go straight to editor.toImage, same as the real exportImage.
export const exportImage = (editor: { toImage: (ids: unknown, o: unknown) => unknown }, ids: unknown, opts: unknown) => editor.toImage(ids, opts)
