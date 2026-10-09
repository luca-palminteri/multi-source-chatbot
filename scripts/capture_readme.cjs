// Capture the actual UI with fixed synthetic API responses, without model calls.
const fs = require('node:fs');
const path = require('node:path');
const net = require('node:net');
const { spawn } = require('node:child_process');
const { chromium } = require('../ui/agent-chat-ui/node_modules/@playwright/test');

const root = path.resolve(__dirname, '..');
const ui = path.join(root, 'ui/agent-chat-ui');
const output = path.join(root, 'docs/images');
const id = 'b3495e21-5fb1-4997-8ee3-35c2b90e2315';
const title = 'VPN access for remote work';
const messages = [
  { id: 'demo-question', type: 'human', content: 'Which team handles VPN access, and what do I need before requesting it?' },
  { id: 'demo-lookup', type: 'ai', content: '', tool_calls: [{ id: 'demo-call', name: 'lookup_information', args: { question: 'VPN access requirements and service ownership' } }] },
  { id: 'demo-evidence', type: 'tool', name: 'lookup_information', tool_call_id: 'demo-call', content: JSON.stringify({ answer: 'IT Operations owns VPN access.', source_ids: ['D1', 'G1'] }) },
  { id: 'demo-answer', type: 'ai', content: '**IT Operations** handles VPN access. [G1]\n\nBefore requesting access, you need: [D1]\n\n| Requirement | What to prepare |\n| --- | --- |\n| Manager approval | Get approval from your manager |\n| Managed device | Use a company-managed device |\n| Multi-factor authentication | Have MFA enabled |\n\nInclude your **business reason** and **desired start date** when known. Submitting a request does not grant VPN access. [D1]\n\n**Sources:** [D1] VPN Access Policy · [G1] VPN service ownership' },
];
const snapshot = { values: { messages }, next: [], tasks: [], checkpoint: { checkpoint_id: '0b0c82ca-e9c9-4e98-aeb9-26d7804a0b18', checkpoint_ns: '', checkpoint_map: {} }, parent_checkpoint: null, metadata: {}, created_at: '2026-10-09T14:00:00Z' };
const threads = [title, 'Software installation policy', 'Equipment support request', 'Account access requirements'].map((name, index) => ({
  thread_id: index ? `b3495e21-5fb1-4997-8ee3-35c2b90e231${index}` : id,
  title: name, created_at: '2026-10-09T14:00:00Z', updated_at: '2026-10-09T14:00:00Z', metadata: {}, status: 'idle', values: index ? {} : { messages },
}));

async function availablePort() {
  const server = net.createServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  await new Promise(resolve => server.close(resolve));
  return port;
}

(async () => {
  fs.mkdirSync(output, { recursive: true });
  let service;
  let browser;
  const errors = [];
  try {
    let base = process.env.WEB_UI_URL;
    if (!base) {
      const port = await availablePort();
      base = `http://127.0.0.1:${port}`;
      service = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'start', '--hostname', '127.0.0.1', '--port', String(port)], { cwd: ui, windowsHide: true, stdio: 'ignore' });
      service.on('error', error => errors.push(error.message));
      let ready = false;
      for (let attempt = 0; attempt < 100; attempt++) {
        if (service.exitCode !== null || errors.length) throw new Error('UI startup failed; build the UI first.');
        try { if ((await fetch(base, { signal: AbortSignal.timeout(1000) })).ok) { ready = true; break; } } catch {}
        await new Promise(resolve => setTimeout(resolve, 300));
      }
      if (!ready) throw new Error('UI startup timed out.');
    }
    const chrome = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
    browser = await chromium.launch({ headless: true, ...(process.env.WEB_BROWSER_PATH ? { executablePath: process.env.WEB_BROWSER_PATH } : fs.existsSync(chrome) ? { executablePath: chrome } : {}) });
    for (const variant of ['desktop-light', 'desktop-dark', 'mobile']) {
      const mobile = variant === 'mobile';
      const context = await browser.newContext({ viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 960 }, deviceScaleFactor: 1, colorScheme: variant === 'desktop-dark' ? 'dark' : 'light' });
      await context.route(url => url.pathname === '/info' || url.pathname.startsWith('/threads') || url.pathname.startsWith('/chat/'), async route => {
        const url = new URL(route.request().url());
        let body;
        if (url.pathname === '/info') body = {};
        else if (url.pathname === '/chat/history') {
          const query = (url.searchParams.get('q') || '').toLowerCase();
          body = { threads: threads.filter(thread => thread.title.toLowerCase().includes(query)), cursor: null };
        } else if (url.pathname.endsWith('/settings')) body = { title, status: 'idle' };
        else if (url.pathname.endsWith('/history')) body = [snapshot];
        else if (url.pathname.endsWith('/state')) body = snapshot;
        else if (url.pathname.endsWith('/runs')) body = [];
        else if (url.pathname === `/threads/${id}`) body = threads[0];
        else {
          errors.push(`Unexpected screenshot API request: ${route.request().method()} ${url.pathname}`);
          return route.fulfill({ status: 501, contentType: 'application/json', body: '{}' });
        }
        await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
      });
      const page = await context.newPage();
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(`${base}/?${new URLSearchParams({ apiUrl: 'http://localhost:2024', assistantId: 'assistant', threadId: id, chatHistoryOpen: mobile ? 'false' : 'true', hideToolCalls: 'true' })}`);
      await page.getByText('IT Operations', { exact: true }).waitFor();
      await page.getByRole('button', { name: `Actions for ${title}` }).last().waitFor();
      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(600);
      await page.screenshot({ path: path.join(output, `${variant}.png`), animations: 'disabled' });
      if (variant === 'desktop-dark') {
        await page.getByRole('button', { name: `Actions for ${title}` }).last().click();
        await page.getByRole('menuitem', { name: 'Export Markdown' }).waitFor();
        await page.screenshot({ path: path.join(output, 'chat-actions.png'), animations: 'disabled' });
      }
      await context.close();
    }
    if (errors.length) throw new Error(errors.join('\n'));
    console.log('Saved four README screenshots to docs/images (synthetic fixtures; no model calls).');
  } finally {
    if (browser) await browser.close();
    if (service) {
      service.kill();
      await new Promise(resolve => { if (service.exitCode !== null) resolve(); else service.once('exit', resolve); });
    }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
