import { defineConfig } from 'vitepress'

// #35: ComfyArt docs site. English at the root, Chinese under /zh/. Published to GitHub Pages
// at https://ganjmeng.github.io/ComfyArt/ by .github/workflows/docs-site.yml.
const groups = (zh: boolean) => {
  const p = zh ? '/zh/guides/' : '/guides/'
  const L = (en: string, cn: string) => (zh ? cn : en)
  return [
    {
      text: L('Get started', '开始'),
      items: [
        { text: L('Getting started', '快速开始'), link: `${p}getting-started` },
        { text: L('Home and projects', '首页与项目'), link: `${p}home` },
        { text: L('Models and costs', '模型与费用'), link: `${p}models` },
        { text: 'WaveSpeed Key', link: `${p}wavespeed-key` },
      ],
    },
    {
      text: L('Create', '创作'),
      items: [
        { text: L('The canvas', '画布'), link: `${p}canvas` },
        { text: L('Text, shapes and paths', '文字、形状与路径'), link: `${p}design` },
        { text: L('Generate', '生成'), link: `${p}generate` },
        { text: L('Image tools', '图像工具'), link: `${p}image-tools` },
        { text: L('Edit Elements and mockups', '编辑元素与样机'), link: `${p}elements-mockups` },
        { text: L('Video', '视频'), link: `${p}video` },
        { text: L('Audio and 3D', '音频与 3D'), link: `${p}audio-3d` },
      ],
    },
    {
      text: L('Assets and Agent', '资产与 Agent'),
      items: [
        { text: L('Assets', '资产'), link: `${p}assets` },
        { text: 'Agent', link: `${p}agent` },
        { text: L('MCP server', 'MCP 服务器'), link: `${p}mcp` },
        { text: L('Custom workflows', '自定义工作流'), link: `${p}custom-workflows` },
      ],
    },
  ]
}

export default defineConfig({
  title: 'ComfyArt',
  base: process.env.DOCS_BASE || '/ComfyArt/',
  cleanUrls: true,
  lastUpdated: false,
  srcExclude: ['README.md'],
  head: [['link', { rel: 'icon', href: `${process.env.DOCS_BASE || '/ComfyArt/'}favicon.svg` }]],
  themeConfig: {
    logo: { light: '/logo.svg', dark: '/logo-dark.svg' },
    siteTitle: false,
    socialLinks: [{ icon: 'github', link: 'https://github.com/ganjmeng/ComfyArt' }],
    search: {
      provider: 'local',
      options: {
        locales: {
          zh: { translations: { button: { buttonText: '搜索文档', buttonAriaLabel: '搜索文档' }, modal: { noResultsText: '没有找到结果', resetButtonTitle: '清除', footer: { selectText: '选择', navigateText: '切换', closeText: '关闭' } } } },
        },
      },
    },
  },
  locales: {
    root: {
      label: 'English',
      lang: 'en',
      description: 'AI design canvas for ComfyUI on WaveSpeed cloud models.',
      themeConfig: { nav: [{ text: 'Guides', link: '/guides/getting-started' }], sidebar: { '/guides/': groups(false) } },
    },
    zh: {
      label: '简体中文',
      lang: 'zh-CN',
      link: '/zh/',
      description: '跑在 WaveSpeed 云端模型上的 ComfyUI AI 设计画布。',
      themeConfig: {
        nav: [{ text: '指南', link: '/zh/guides/getting-started' }],
        sidebar: { '/zh/guides/': groups(true) },
        outline: { label: '本页目录' },
        docFooter: { prev: '上一页', next: '下一页' },
        langMenuLabel: '切换语言',
        returnToTopLabel: '回到顶部',
        sidebarMenuLabel: '菜单',
        darkModeSwitchLabel: '外观',
      },
    },
  },
})
