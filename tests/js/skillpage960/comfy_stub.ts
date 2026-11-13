// In-memory user files for the #960 skill-read paging harness (no browser, no backend).
export const files: Record<string, string> = {}
export const listUserFiles = async (dir: string, _deep?: boolean) =>
  Object.keys(files).filter((p) => p.startsWith(dir + '/')).map((p) => p.slice(dir.length + 1))
export const readUserText = async (p: string) => (p in files ? files[p] : null)
export const writeUserText = async (p: string, s: string) => { files[p] = s }
export const deleteUserFile = async (p: string) => { delete files[p] }
export const uploadImage = async (_b: unknown, name: string) => ({ filename: name, subfolder: '', type: 'input' })
export const viewUrl = (r: { filename: string }) => `/view?filename=${r.filename}`
