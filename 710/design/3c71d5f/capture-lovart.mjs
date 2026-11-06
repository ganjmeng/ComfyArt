#!/usr/bin/env node
/**
 * capture-lovart.mjs — lovart.ai 金标一次跑完的 Playwright 抓取脚本（设计交付，网络恢复/在 Jingmeng 本机可用）。
 *
 * 用法（匿名；不碰用户登录态）：
 *   NODE_PATH=/Users/jingmeng.gan/Documents/open-lovart/node_modules \
 *   node capture-lovart.mjs --out /tmp/team/design/lovart-capture [--authed-profile /tmp/copy-of-Profile1] [--headed]
 *
 * 输出：
 *   <out>/shots/*.png        —— 命名 <state>-<lang>-<theme>.png，可直接按
 *                               <卡号>/design/<sha8>/<state>-zh-light.png 上传 review-assets
 *   <out>/computed.json      —— #710 需要的 computed style 实测值（getComputedStyle，含 devicePixelRatio）
 *   <out>/capture-result.json—— 每步 ok/error + 页面 URL/标题 + 网络错误，供 HOLD 记录
 *
 * 设计稿状态清单（#710）：
 *   dialog-default    技能页 → 打开 "E-commerce Same-scene Character Pose Variation" 弹框（默认态）
 *   dialog-filled     上传参考图 + 填 Additional Details
 *   running           开始创作后「Skill ready / Outputting…」状态
 *   followup-unselected / followup-selected / followup-submitted  追问卡三态
 *
 * 注意：
 *  - 匿名上下文不登录；lovart.ai 若对匿名用户弹登录墙，脚本会截图并记录 `authWall`。
 *  - 传 --authed-profile <已复制到 /tmp 的 Chrome profile> 时用 launchPersistentContext（绝不指向原 profile）。
 *  - 本脚本不点付费/生成类按钮（Start making 只在 running 步骤点；若账户无额度，会在结果里记录错误，
 *    不会重试、不会产生付费调用；如需严格 $0，请先确认账户额度或跳过 running 步骤）。
 *  - 不抓 cookie、不导出账号信息；截图前请求 cover 类图片等待加载完成。
 *
 * 依赖：playwright（已在 /Users/jingmeng.gan/Documents/open-lovart/node_modules），Chrome 用 channel:'chrome'。
 */
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';

const require = createRequire('/Users/jingmeng.gan/Documents/open-lovart/node_modules/noop.cjs');
const { chromium } = require('playwright');

// ---- args -----------------------------------------------------------------
const argv = process.argv.slice(2);
const arg = (name, dflt = null) => {
  const i = argv.indexOf('--' + name);
  return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : dflt;
};
const flag = (name) => argv.includes('--' + name);
const OUT = arg('out', '/tmp/team/design/lovart-capture');
const PROFILE = arg('authed-profile', null);
const HEADED = flag('headed');
const APP = 'https://www.lovart.ai/';
const SHOTS = path.join(OUT, 'shots');
fs.mkdirSync(SHOTS, { recursive: true });
const result = { app: APP, startedAt: new Date().toISOString(), authed: !!PROFILE, steps: [], computed: {}, errors: [] };

const shot = async (page, name) => {
  const p = path.join(SHOTS, `${name}.png`);
  await page.waitForTimeout(700);
  await page.screenshot({ path: p, fullPage: false });
  const { size } = fs.statSync(p);
  result.steps.push({ name, file: p, bytes: size });
  console.log('SHOT', p, size);
  return p;
};

async function waitImages(page) {
  await page.evaluate(async () => {
    const imgs = [...document.querySelectorAll('img')];
    await Promise.all(imgs.map((im) => (im.complete ? null : new Promise((r) => { im.onload = im.onerror = r; }))));
  }).catch(() => {});
  await page.waitForTimeout(500);
}

/** computed styles for the #710 spec table. selectors resolved by text/label so they survive class churn. */
async function grabComputed(page) {
  return page.evaluate(() => {
    const byText = (re, root = document) => [...root.querySelectorAll('button,div,span,h2,textarea,input')]
      .find((el) => re.test((el.innerText || el.placeholder || '').trim()) && el.offsetParent !== null);
    const cs = (el) => {
      if (!el) return null;
      const s = getComputedStyle(el); const r = el.getBoundingClientRect();
      return {
        rect: { x: r.x, y: r.y, w: r.width, h: r.height },
        font: `${s.fontWeight} ${s.fontSize}/${s.lineHeight} ${s.fontFamily}`,
        radius: s.borderRadius, bg: s.backgroundColor, color: s.color,
        padding: s.padding, margin: s.margin, border: s.border, gap: s.gap,
        opacity: s.opacity, boxShadow: s.boxShadow,
      };
    };
    const title = byText(/^E-commerce Same-scene Character Pose Variation$/i);
    const dialog = title && title.closest('[role=dialog], [class*=modal], [class*=dialog]');
    const startBtn = byText(/Start making/i, dialog || document);
    const details = (dialog || document).querySelector('textarea, input[placeholder*="Anything else" i]');
    const submit = byText(/^Submit$/i);
    const skip = byText(/^Skip$/i);
    const question = byText(/^Question$/i);
    return {
      dpr: window.devicePixelRatio, viewport: { w: innerWidth, h: innerHeight },
      dialog: cs(dialog), title: cs(title), startButton: cs(startBtn),
      additionalDetails: cs(details), submit: cs(submit), skip: cs(skip), questionCard: cs(question),
    };
  });
}

/** open the Skills page and the pose-fission dialog (Lovart international skill name). */
async function openDialog(page) {
  // Lovart 2.0 sidebar: Skills
  const skillsNav = page.getByText(/^Skills$/i).first();
  if (await skillsNav.count()) { await skillsNav.click().catch(() => {}); await page.waitForTimeout(2500); }
  // skill card: search then click
  const search = page.locator('input[placeholder*="model" i], input[placeholder*="search" i]').first();
  const skillName = /E-commerce Same-scene Character Pose Variation/i;
  if (await search.count()) {
    await search.fill('E-commerce').catch(() => {});
    await page.waitForTimeout(1500);
  }
  let card = page.getByText(skillName).first();
  if (!(await card.count())) {
    // fall back: any card mentioning "Pose Variation"
    card = page.getByText(/Pose Variation/i).first();
  }
  if (!(await card.count())) throw new Error('skill card not found (maybe login wall / A/B copy change) — see page screenshot');
  await card.scrollIntoViewIfNeeded().catch(() => {});
  await card.click();
  // dialog detection
  const dlgText = page.getByText(/Start Creating/i).first();
  await dlgText.waitFor({ timeout: 20000 }).catch(() => {});
  result.authWall = await page.evaluate(() => {
    const t = document.body.innerText;
    return /sign in|log in|登录|立即登录/i.test(t) && !/Start Creating/i.test(t);
  });
  await waitImages(page);
}

async function fillDialog(page) {
  const fileInput = page.locator('input[type=file]').first();
  if (!(await fileInput.count())) throw new Error('no file input in dialog');
  const fixture = path.join(OUT, 'fixture-ref.png');
  if (!fs.existsSync(fixture)) { // 900x1200 neutral mock ref
    fs.writeFileSync(fixture, Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAMAAAAFCAIAAAAf7r5hAAAAFElEQVR4nGP4z8DAwMDAxMDAwMDAAAANHQEDasKb6QAAAABJRU5ErkJggg==', 'base64'));
  }
  await fileInput.setInputFiles(fixture);
  await page.waitForTimeout(1500);
  const details = page.locator('textarea, input[placeholder*="Anything else" i]').first();
  if (await details.count()) {
    await details.fill('Same model, beige trench coat, same city street; 4 frames: front, back-look, half-body side, close-up.');
    await page.waitForTimeout(400);
  }
  await waitImages(page);
}

const steps = {
  'dialog-default': async (page) => openDialog(page),
  'dialog-filled': async (page) => { await openDialog(page); await fillDialog(page); },
  'running': async (page) => {
    await openDialog(page); await fillDialog(page);
    const btn = page.getByText(/^Start making$/i).first();
    await btn.click();
    await page.waitForTimeout(4000);
    // wait for a "Skill ready"/"Outputting…" status line to appear
    await page.getByText(/Skill ready|Outputting|输出中|技能就绪/i).first().waitFor({ timeout: 20000 }).catch(() => {});
    await waitImages(page);
  },
  'followup-unselected': async (page) => {
    // state is produced by the agent after running the skill; needs a real/session run.
    // If the current page already shows a Question card (e.g. resumed session), shoot it.
    const q = page.getByText(/^Question$/i).first();
    if (!(await q.count())) throw new Error('no Question card on page — open/resume a chat that has one');
  },
  'followup-selected': async (page) => {
    await steps['followup-unselected'](page);
    const a = page.getByText(/^A\s+Start generating$/i).first();
    await a.click(); await page.waitForTimeout(600);
  },
  'followup-submitted': async (page) => {
    await steps['followup-selected'](page);
    const submit = page.getByText(/^Submit$/i).first();
    await submit.click();
    await page.waitForTimeout(1500);
  },
};

// ---- main -----------------------------------------------------------------
let browser, context;
try {
  if (PROFILE) {
    context = await chromium.launchPersistentContext(PROFILE, {
      channel: 'chrome', headless: !HEADED, viewport: { width: 1920, height: 1072 },
      locale: 'en-US', args: ['--no-first-run', '--no-default-browser-check'],
    });
    browser = context.browser();
  } else {
    browser = await chromium.launch({ channel: 'chrome', headless: !HEADED });
    context = await browser.newContext({ viewport: { width: 1920, height: 1072 }, locale: 'en-US' });
  }
  const page = await context.newPage();
  page.setDefaultTimeout(45000);
  page.on('requestfailed', (r) => {
    if (/lovart\.ai/.test(r.url())) result.errors.push({ url: r.url().slice(0, 160), err: r.failure()?.errorText });
  });
  console.log('NAV', APP);
  await page.goto(APP, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await page.waitForTimeout(6000);
  await shot(page, '00-home');
  result.anonymousOk = !result.authWall;

  const wanted = arg('states', 'dialog-default,dialog-filled,computed');
  for (const name of wanted.split(',').map((s) => s.trim()).filter(Boolean)) {
    try {
      if (name === 'computed') {
        result.computed = await grabComputed(page);
        console.log('COMPUTED', JSON.stringify(result.computed));
        continue;
      }
      const fn = steps[name];
      if (!fn) throw new Error('unknown state: ' + name);
      await fn(page);
      await shot(page, name);
      result.steps[result.steps.length - 1].ok = true;
    } catch (e) {
      result.errors.push({ step: name, error: String(e).slice(0, 400) });
      console.log('STEP-FAIL', name, String(e).slice(0, 200));
      await shot(page, '99-fail-' + name).catch(() => {});
    }
  }
  result.ok = true;
} catch (e) {
  result.ok = false;
  result.error = String(e).slice(0, 600);
} finally {
  try { await context?.close(); } catch {}
  fs.writeFileSync(path.join(OUT, 'capture-result.json'), JSON.stringify(result, null, 2));
  fs.writeFileSync(path.join(OUT, 'computed.json'), JSON.stringify(result.computed, null, 2));
  console.log('RESULT', JSON.stringify({ ok: result.ok, steps: result.steps.map((s) => s.name), errors: result.errors.length }));
  process.exitCode = result.ok ? 0 : 1;
}
