export const downloads: { blob: Blob; name: string }[] = []
export function download(blob: Blob, name: string) { downloads.push({ blob, name }) }
