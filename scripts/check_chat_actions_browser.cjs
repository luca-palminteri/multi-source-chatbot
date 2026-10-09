// Browser checks against check_web.py's disposable native server and deterministic model.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('../ui/agent-chat-ui/node_modules/@playwright/test');
const api = process.argv[2];
const output = path.resolve(__dirname, '../runtime/chat-actions-browser');
fs.mkdirSync(output, { recursive: true });
const checks = {};
async function request(url, body) {
  const response = await fetch(api + url, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {});
  assert(response.ok, `${url}: ${response.status}`);
  return response.json();
}
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.WEB_BROWSER_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
  const errors = [];
  try {
    for (const mobile of [false, true]) {
      const { thread_id: id } = await request('/threads', {});
      await request(`/threads/${id}/runs/wait`, { assistant_id: 'assistant', input: { messages: [{ type: 'human', content: 'Browser café\nUnicode \u804a\u5929 [D1]', id: crypto.randomUUID() }] } });
      const page = await browser.newPage({ viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 }, acceptDownloads: true });
      page.on('pageerror', e => errors.push(e.message));
      const url = new URL(process.env.WEB_UI_URL || 'http://127.0.0.1:3000');
      url.search = new URLSearchParams({ apiUrl: api, assistantId: 'assistant', threadId: id, chatHistoryOpen: 'false' }).toString();
      await page.goto(url.toString());
      // Accessible names collapse whitespace.
      const headerActions = page.getByRole('button', { name: /Actions for Browser café/ }).first();
      await headerActions.waitFor({ timeout: 60000 });
      await headerActions.focus(); await page.keyboard.press('ArrowDown');
      await page.getByRole('menuitem', { name: 'Rename', exact: true }).waitFor();
      await page.keyboard.press('ArrowDown');
      assert.equal(await page.evaluate(() => document.activeElement.textContent), 'Export Markdown');
      await page.keyboard.press('Escape');
      assert(await headerActions.evaluate(el => el === document.activeElement));
      checks[`${mobile ? 'mobile' : 'desktop'}_keyboard`] = true;
      await headerActions.click(); await page.getByRole('menuitem', { name: 'Rename', exact: true }).click();
      await page.screenshot({ path: path.join(output, mobile ? 'mobile-rename.png' : 'desktop-rename.png') });
      await page.getByLabel('Chat title').fill('   ');
      assert(await page.getByRole('button', { name: 'Save', exact: true }).isDisabled());
      const title = mobile ? 'Mobile café \u804a\u5929' : 'Desktop café \u804a\u5929';
      await page.getByLabel('Chat title').fill(title);
      if (!mobile) {
        await page.route(`**/chat/${id}/title`, route => route.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify({ detail: 'Rename test error' }) }));
        await page.getByRole('button', { name: 'Save', exact: true }).click();
        await page.getByRole('alert').filter({ hasText: 'Rename test error' }).waitFor();
        await page.unroute(`**/chat/${id}/title`);
        checks.rename_error_feedback = true;
      }
      await page.getByRole('button', { name: 'Save', exact: true }).click();
      await page.getByRole('dialog').waitFor({ state: 'hidden' });
      await page.getByRole('button', { name: `Actions for ${title}` }).last().waitFor();
      await page.reload();
      await page.getByRole('button', { name: `Actions for ${title}` }).last().waitFor();
      checks[`${mobile ? 'mobile' : 'desktop'}_rename_reload`] = true;
      for (const format of ['Markdown', 'JSON']) {
        await page.getByRole('button', { name: `Actions for ${title}` }).last().click();
        const downloading = page.waitForEvent('download');
        await page.getByRole('menuitem', { name: `Export ${format}` }).click();
        const download = await downloading;
        const file = path.join(output, download.suggestedFilename());
        await download.saveAs(file);
        const content = fs.readFileSync(file, 'utf8');
        assert(content.includes('Unicode \u804a\u5929'));
        assert(content.includes('[D1]'));
        if (format === 'JSON') assert.equal(JSON.parse(content).version, 1);
      }
      checks[`${mobile ? 'mobile' : 'desktop'}_downloads`] = true;
      await page.getByRole('button', { name: 'Toggle thread history' }).last().click();
      const history = page.getByLabel('Search chat history').locator('..');
      await page.getByLabel('Search chat history').fill(title);
      await history.getByRole('button', { name: title, exact: true }).waitFor();
      await page.getByLabel('Search chat history').fill('no matching text xyz');
      await page.getByText('No matching chats.', { exact: true }).waitFor();
      await page.getByLabel('Search chat history').fill('');
      await history.getByRole('button', { name: title, exact: true }).waitFor();
      checks[`${mobile ? 'mobile' : 'desktop'}_search`] = true;
      await history.getByRole('button', { name: `Actions for ${title}` }).click();
      await page.getByRole('menuitem', { name: 'Delete', exact: true }).click();
      await page.getByText('Deleting history does not undo service-request actions.', { exact: false }).waitFor();
      await page.getByRole('button', { name: 'Delete permanently' }).click();
      await page.getByRole('dialog').filter({ hasText: 'Delete' }).waitFor({ state: 'hidden' });
      await page.waitForFunction(() => !new URL(location.href).searchParams.has('threadId'));
      await history.getByRole('button', { name: title, exact: true }).waitFor({ state: 'hidden' });
      checks[`${mobile ? 'mobile' : 'desktop'}_delete_selection`] = true;
      await page.screenshot({ path: path.join(output, mobile ? 'mobile.png' : 'desktop.png'), fullPage: true });
      await page.close();
    }
    checks.no_browser_errors = errors.length === 0;
    assert(checks.no_browser_errors, errors.join('\n'));
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify({ passed: true, checks, errors }, null, 2));
    console.log(JSON.stringify(checks));
  } finally { await browser.close(); }
})().catch(error => { fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify({ passed: false, checks, error: String(error) }, null, 2)); console.error(error); process.exitCode = 1; });
