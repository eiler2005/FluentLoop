/* Optional browser acceptance check. Requires Playwright and an installed Chrome. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('playwright');

(async () => {
  const artifacts = await fs.mkdtemp(path.join(os.tmpdir(), 'fluentloop-planner-'));
  const browser = await chromium.launch({channel: process.env.PLANNER_BROWSER || 'chrome'});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    const errors = [], network = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {if (/^https?:/.test(request.url())) network.push(request.url());});
    await page.goto(pathToFileURL(path.resolve(__dirname, '../docs/curriculum/workplace-planner.html')).href);
    assert.equal(await page.locator('.module').count(), 48);
    assert.match(await page.locator('#general-time').innerText(), /45 мин/);
    assert.match(await page.locator('#work-time').innerText(), /105 мин/);
    assert.equal(await page.locator('#track').inputValue(), 'client_facing');
    await page.locator('#track').selectOption('client_facing');
    await page.locator('#minutes').fill('200');
    await page.locator('#share').click();
    await page.locator('#share').fill('65');
    await page.locator('#search').click();
    assert.match(await page.locator('#general-time').innerText(), /130 мин/);
    await page.locator('#strand').selectOption('general');
    assert.equal(await page.locator('.module').count(), 16);
    await page.locator('#strand').selectOption('work');
    assert.equal(await page.locator('.module').count(), 32);
    await page.locator('#search').fill('потребност');
    assert.ok(await page.locator('.module').count() > 0);
    await page.locator('#search').fill('');
    await page.locator('#stage').selectOption('c1_intro');
    assert.match(await page.locator('#detail').innerText(), /C1 intro/);
    await page.getByRole('button', {name: 'Сделать фокусом', exact: true}).click();
    const focused = await page.evaluate(() => plan.focus);
    const note = '</textarea><img src=x onerror=alert(1)> Только текст 🧭';
    await page.locator('#detail textarea').fill(note);
    await page.locator('#search').click();
    assert.equal(await page.locator('#detail img').count(), 0);
    await page.getByRole('button', {name: 'Ниже ↓', exact: true}).click();
    await page.getByRole('button', {name: 'Поставить на паузу', exact: true}).click();
    assert.equal(await page.evaluate(() => plan.focus), null);
    assert.equal(await page.evaluate(id => plan.paused.includes(id), focused), true);
    await page.getByRole('button', {name: 'Вернуть в план', exact: true}).click();
    await page.getByRole('button', {name: 'Сделать фокусом', exact: true}).click();
    const before = await page.evaluate(() => JSON.stringify(plan));
    await page.reload();
    assert.equal(await page.evaluate(() => JSON.stringify(plan)), before);
    const downloadPromise = page.waitForEvent('download');
    await page.locator('#export').click();
    const download = await downloadPromise;
    const exported = path.join(artifacts, 'roundtrip.json');
    await download.saveAs(exported);
    const exportedPlan = JSON.parse(await fs.readFile(exported, 'utf8'));
    assert.equal(exportedPlan.notes[focused], note);
    await page.locator('#file').setInputFiles(exported);
    assert.equal(await page.evaluate(() => JSON.stringify(plan)), before);
    const invalid = path.join(artifacts, 'invalid.json');
    await fs.writeFile(invalid, JSON.stringify({...exportedPlan, mastery: true}));
    await page.locator('#file').setInputFiles(invalid);
    await page.waitForFunction(() => document.getElementById('status').classList.contains('error'));
    assert.equal(await page.evaluate(() => JSON.stringify(plan)), before);
    assert.match(await page.locator('#status').innerText(), /План не изменён/);
    const duplicate = JSON.stringify(exportedPlan).replace('"version":1', '"version":1,"version":1');
    await fs.writeFile(invalid, duplicate);
    await page.locator('#file').setInputFiles(invalid);
    await page.waitForFunction(() => document.getElementById('status').textContent.includes('повторное поле'));
    assert.equal(await page.evaluate(() => JSON.stringify(plan)), before);
    assert.equal(await page.evaluate(() => {
      const bad = {...plan, track: ['balanced']};
      try {validatePlan(bad); return false;} catch {return true;}
    }), true);
    assert.equal(await page.evaluate(() => {
      const bad = {...plan, notes: {[plan.order[0]]: '\ud800'}};
      try {validatePlan(bad); return false;} catch {return true;}
    }), true);
    await page.evaluate(() => {tell('Проверка сохранения и переноса пройдена.');scrollTo(0,0);});
    await page.screenshot({path: path.join(artifacts, 'desktop.png'), fullPage: false});
    await page.locator('#detail').screenshot({path: path.join(artifacts, 'desktop-detail.png')});
    await page.setViewportSize({width: 390, height: 844});
    await page.evaluate(() => scrollTo(0,0));
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({path: path.join(artifacts, 'mobile.png'), fullPage: false});
    await page.locator('#detail').screenshot({path: path.join(artifacts, 'mobile-detail.png')});
    assert.deepEqual(errors, []);
    assert.deepEqual(network, []);
    console.log(JSON.stringify({browser_checks: 'passed', modules: 48, offline: true, artifacts}));
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
