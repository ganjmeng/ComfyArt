import { cssFamily, fontFamilyFromFilename } from '../../src/fontName.ts'

const families: [string, string][] = [
  ['Arial', '"Arial"'],
  ['2Banner', '"2Banner"'],
  ['Roboto 3', '"Roboto 3"'],
  ['Comic Sans MS, cursive', '"Comic Sans MS", cursive'],
  ['sans-serif', 'sans-serif'],
  ['"Already"', '"Already"'],
  ['Han, SC', '"Han", "SC"'],
  ['', ''],
  ['  , serif , ', 'serif'],
]

const files: [string, string][] = [
  ['2Banner.otf', '2Banner'],
  ['Han,SC.ttf', 'Han SC'],
  ['Weird"Name.woff2', 'Weird Name'],
  ["Face'One.woff", 'Face One'],
  ['NoExt', 'NoExt'],
]

const family = Object.fromEntries(families.map(([input, want]) => {
  const got = cssFamily(input)
  if (got !== want) throw new Error(`cssFamily(${JSON.stringify(input)}) = ${JSON.stringify(got)}, want ${JSON.stringify(want)}`)
  return [input, got]
}))
const filename = Object.fromEntries(files.map(([input, want]) => {
  const got = fontFamilyFromFilename(input)
  if (got !== want) throw new Error(`fontFamilyFromFilename(${JSON.stringify(input)}) = ${JSON.stringify(got)}, want ${JSON.stringify(want)}`)
  return [input, got]
}))

console.log(JSON.stringify({ family, filename }))
