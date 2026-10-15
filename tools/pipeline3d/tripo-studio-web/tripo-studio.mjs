import { chromium } from 'playwright-core'
import fs from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'

const root = path.dirname(new URL(import.meta.url).pathname)
const profile = path.join(root, '.profile')
const artifacts = path.join(root, 'artifacts')
const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const studio = 'https://studio.tripo3d.ai/'
await fs.mkdir(artifacts, { recursive: true })

function stamp() { return new Date().toISOString().replaceAll(':', '-').replaceAll('.', '-') }
async function launch() {
  return chromium.launchPersistentContext(profile, {
    executablePath: chrome,
    headless: process.env.HEADLESS === '1',
    viewport: { width: 1440, height: 1000 },
    acceptDownloads: true,
    downloadsPath: artifacts,
    args: ['--disable-blink-features=AutomationControlled'],
  })
}
async function interactiveSnapshot(page, label) {
  const id = `${label}-${stamp()}`
  const shot = path.join(artifacts, `${id}.png`)
  await page.screenshot({ path: shot, fullPage: true })
  const data = await page.locator('button, a, input, [role="button"], [role="tab"], [role="menuitem"], [contenteditable="true"]').evaluateAll((els) =>
    els.map((e, i) => ({
      i,
      tag: e.tagName,
      type: e.getAttribute('type'),
      role: e.getAttribute('role'),
      text: (e.innerText || e.getAttribute('aria-label') || e.getAttribute('placeholder') || '').trim().replace(/\s+/g, ' ').slice(0, 180),
      visible: !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length),
      disabled: !!e.disabled,
    })).filter((x) => x.visible && x.text)
  )
  await fs.writeFile(path.join(artifacts, `${id}.json`), JSON.stringify({ url: page.url(), elements: data }, null, 2))
  console.log(JSON.stringify({ url: page.url(), screenshot: shot, elements: data }, null, 2))
}
async function waitReady(page) {
  await page.goto(studio, { waitUntil: 'domcontentloaded', timeout: 120000 })
  await page.waitForTimeout(7000)
}

const command = process.argv[2] || 'inspect'
const context = await launch()
const pages = context.pages()
const page = pages[0] || await context.newPage()
page.on('response', async (r) => {
  const u = r.url()
  if (/task|generation|upload|model|asset/i.test(u) && /tripo3d/i.test(u)) {
    await fs.appendFile(path.join(artifacts, 'network.log'), `${new Date().toISOString()} ${r.status()} ${r.request().method()} ${u}\n`)
  }
})
try {
  await waitReady(page)
  if (command === 'login') {
    console.log('Chrome opened with a persistent automation profile. Log into Tripo Studio in this window. The session is saved automatically.')
    await interactiveSnapshot(page, 'login-start')
    const timeout = Number(process.env.LOGIN_WAIT_MS || 15 * 60_000)
    const start = Date.now()
    while (Date.now() - start < timeout) {
      await page.waitForTimeout(3000)
      const body = await page.locator('body').innerText().catch(() => '')
      const authVisible = /Регистрация\/Вход|Вход через аккаунт Google|Продолжить с электронной почтой|Использовать пароль|Sign\s*(up|in)|Log\s*in|Continue with Google|Continue with email/i.test(body)
      const accountVisible = /(Мои проекты|Мои модели|Мой профиль|Аккаунт|My projects|My models|My profile|Account)/i.test(body)
      if (!authVisible && accountVisible) {
        console.log('Authenticated Studio session detected; saving profile.')
        break
      }
    }
    await interactiveSnapshot(page, 'login-finish')
  } else if (command === 'inspect') {
    await interactiveSnapshot(page, 'inspect')
  } else if (command === 'workspace') {
    const workspaceLink = page.getByRole('link', { name: /3D рабочая область|3D Workspace/i }).first()
    if (await workspaceLink.count()) await workspaceLink.click()
    else await page.getByRole('button', { name: /3D рабочая область|3D Workspace/i }).first().click()
    await page.waitForTimeout(8000)
    await interactiveSnapshot(page, 'workspace')
  } else if (command === 'calibrate') {
    await page.goto('https://studio.tripo3d.ai/ru/workspace/generate', { waitUntil: 'domcontentloaded', timeout: 120000 })
    await page.waitForTimeout(7000)
    await page.getByRole('button', { name: 'Умная сетка', exact: true }).click()
    await page.waitForTimeout(4000)
    await interactiveSnapshot(page, 'smart-mesh')
  } else if (command === 'probe-inputs') {
    await page.goto('https://studio.tripo3d.ai/ru/workspace/generate', { waitUntil: 'domcontentloaded', timeout: 120000 })
    await page.waitForTimeout(7000)
    await page.getByRole('button', { name: 'Умная сетка', exact: true }).click()
    await page.waitForTimeout(2500)
    const probe = await page.locator('input, button, [role="button"]').evaluateAll((els) => els.map((e, i) => {
      const r = e.getBoundingClientRect()
      return {
        i, tag: e.tagName, type: e.getAttribute('type'), accept: e.getAttribute('accept'), multiple: e.hasAttribute('multiple'),
        title: e.getAttribute('title'), aria: e.getAttribute('aria-label'), text: (e.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 120),
        x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
        html: e.outerHTML.slice(0, 500), visible: !!(r.width && r.height)
      }
    }).filter(x => x.type === 'file' || (x.visible && x.x < 320 && x.y < 450)))
    console.log(JSON.stringify(probe, null, 2))
  } else if (command === 'probe-multiview') {
    await page.goto('https://studio.tripo3d.ai/ru/workspace/generate', { waitUntil: 'domcontentloaded', timeout: 120000 })
    await page.waitForTimeout(7000)
    await page.getByRole('button', { name: 'Умная сетка', exact: true }).click()
    await page.locator('button:has(.i-tripo\\:multi-view)').click()
    await page.waitForTimeout(2500)
    const probe = await page.locator('input[type="file"], button, [role="button"]').evaluateAll((els) => els.map((e, i) => {
      const r = e.getBoundingClientRect()
      return { i, tag: e.tagName, type: e.getAttribute('type'), accept: e.getAttribute('accept'), text: (e.innerText || e.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 160), x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), parent: e.parentElement?.outerHTML.slice(0, 800), visible: !!(r.width && r.height) }
    }).filter(x => x.type === 'file' || (x.visible && x.x < 320 && x.y < 650)))
    console.log(JSON.stringify(probe, null, 2))
    await interactiveSnapshot(page, 'multiview')
  } else if (command === 'stage') {
    const runDir = process.env.RUN_DIR || '/Users/user0/godot-hybrid-casual/tools/pipeline3d/runs/2026-09-02-tripo-bucket-v1'
    const files = {
      front: process.env.FRONT || path.join(runDir, 'ref2_front.png'),
      side: process.env.SIDE || path.join(runDir, 'ref2_side.png'),
      back: process.env.BACK || path.join(runDir, 'ref2_back.png'),
    }
    await page.goto('https://studio.tripo3d.ai/ru/workspace/generate', { waitUntil: 'domcontentloaded', timeout: 120000 })
    await page.waitForTimeout(7000)
    await page.getByRole('button', { name: 'Умная сетка', exact: true }).click()
    await page.locator('button:has(.i-tripo\\:multi-view)').click()
    const slot = (icon) => page.locator(`div:has(> .i-tripo\\:${icon})`).locator('input[type="file"]')
    await slot('front-view').setInputFiles(files.front)
    await page.waitForTimeout(2500)
    await slot('left-view').setInputFiles(files.side)
    await page.waitForTimeout(2500)
    await slot('back-view').setInputFiles(files.back)
    await page.waitForTimeout(5000)
    await interactiveSnapshot(page, 'staged')
  } else if (command === 'generate') {
    const runDir = process.env.RUN_DIR || '/Users/user0/godot-hybrid-casual/tools/pipeline3d/runs/2026-09-02-tripo-bucket-v1'
    const files = {
      front: process.env.FRONT || path.join(runDir, 'ref2_front.png'),
      side: process.env.SIDE || path.join(runDir, 'ref2_side.png'),
      back: process.env.BACK || path.join(runDir, 'ref2_back.png'),
    }
    const responses = []
    page.on('response', async (r) => {
      if (!/tripo3d/i.test(r.url()) || !/task|generation|model|asset|workspace/i.test(r.url())) return
      const type = r.headers()['content-type'] || ''
      if (type.includes('json')) {
        const data = await r.json().catch(() => null)
        if (data) responses.push({ url: r.url(), status: r.status(), data })
      }
    })
    await page.goto('https://studio.tripo3d.ai/ru/workspace/generate', { waitUntil: 'domcontentloaded', timeout: 120000 })
    await page.waitForTimeout(7000)
    await page.getByRole('button', { name: 'Умная сетка', exact: true }).click()
    await page.locator('button:has(.i-tripo\\:multi-view)').click()
    const slot = (icon) => page.locator(`div:has(> .i-tripo\\:${icon})`).locator('input[type="file"]')
    await slot('front-view').setInputFiles(files.front)
    await page.waitForTimeout(2500)
    await slot('left-view').setInputFiles(files.side)
    await page.waitForTimeout(2500)
    await slot('back-view').setInputFiles(files.back)
    await page.waitForTimeout(5000)
    const create = page.getByRole('button', { name: /^Создать|^Create/i }).last()
    const label = (await create.innerText()).trim()
    if (!/\b0\b/.test(label) && process.env.ALLOW_PAID !== '1') throw new Error(`Refusing non-free generation; button label is: ${label}. Set ALLOW_PAID=1 to override.`)
    console.log(`Starting Studio generation: ${label}`)
    await create.click()
    const timeout = Number(process.env.GENERATION_WAIT_MS || 8 * 60_000)
    await page.getByRole('button', { name: /^Экспорт$|^Export$/i }).waitFor({ state: 'visible', timeout })
    await page.getByText(/Грани|Faces/i).waitFor({ state: 'visible', timeout })
    const resultFile = path.join(artifacts, `generation-responses-${stamp()}.json`)
    await fs.writeFile(resultFile, JSON.stringify(responses, null, 2))
    await interactiveSnapshot(page, 'generated')
    console.log(JSON.stringify({ responseLog: resultFile, url: page.url() }, null, 2))
  } else if (command === 'latest') {
    await page.goto('https://studio.tripo3d.ai/ru/workspace/generate', { waitUntil: 'domcontentloaded', timeout: 120000 })
    await page.waitForTimeout(8000)
    const assetLinks = page.locator('a[href*="/workspace/"]')
    const links = await assetLinks.evaluateAll((els) => els.map(e => ({ href: e.href, text: (e.innerText || '').trim() })).filter(x => x.href))
    console.log(JSON.stringify(links.slice(0, 20), null, 2))
    await interactiveSnapshot(page, 'latest')
  } else if (command === 'inspect-result') {
    await page.goto('https://studio.tripo3d.ai/ru/workspace/generate', { waitUntil: 'domcontentloaded', timeout: 120000 })
    await page.waitForTimeout(8000)
    const candidates = page.locator('a[href*="/workspace/generate/"]')
    if (!await candidates.count()) throw new Error('No generated assets found')
    await candidates.first().click()
    await page.waitForTimeout(10000)
    await interactiveSnapshot(page, 'result')
    const controls = await page.locator('button, a, [role="button"], [role="menuitem"]').evaluateAll((els) => els.map((e, i) => ({ i, text: (e.innerText || e.getAttribute('aria-label') || e.getAttribute('title') || '').trim().replace(/\s+/g, ' ').slice(0, 200), html: e.outerHTML.slice(0, 600) })).filter(x => /download|export|скач|экспорт|glb|fbx|obj/i.test(x.text + x.html)))
    console.log(JSON.stringify({ url: page.url(), controls }, null, 2))
  } else if (command === 'download') {
    await page.goto('https://studio.tripo3d.ai/ru/workspace/generate', { waitUntil: 'domcontentloaded', timeout: 120000 })
    await page.waitForTimeout(8000)
    const candidates = page.locator('a[href*="/workspace/generate/"]')
    if (!await candidates.count()) throw new Error('No generated assets found')
    await candidates.first().click()
    await page.waitForTimeout(10000)
    await page.getByRole('button', { name: /Экспорт|Export/i }).click()
    await page.waitForTimeout(2500)
    await interactiveSnapshot(page, 'export-dialog')
    const format = page.locator('button[role="combobox"]:has-text("FBX")').last()
    await format.click()
    await page.waitForTimeout(1000)
    const options = await page.locator('[role="option"], [role="menuitem"], [data-reka-collection-item]').allTextContents()
    console.log(JSON.stringify({ formatOptions: options }, null, 2))
    if (process.env.DO_DOWNLOAD === '1') {
      const glb = page.getByText(/^GLB$/).last()
      await glb.click()
      const exportButtons = page.getByRole('button', { name: /^Экспорт$|^Export$/i })
      const downloadPromise = page.waitForEvent('download', { timeout: 120000 })
      await exportButtons.last().click()
      const download = await downloadPromise
      const output = process.env.OUTPUT || '/Users/user0/godot-hybrid-casual/tools/pipeline3d/runs/2026-09-02-tripo-bucket-v1/tripo_studio_p2.glb'
      await download.saveAs(output)
      console.log(JSON.stringify({ output, suggestedFilename: download.suggestedFilename() }, null, 2))
    }
  } else {
    throw new Error(`Unknown command: ${command}`)
  }
} finally {
  await context.close()
}
