// Appearance smoke check against a running UI; no backend or model calls.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const http = require("node:http");
const {
  chromium,
} = require("../ui/agent-chat-ui/node_modules/@playwright/test");

const output = path.resolve(__dirname, "../runtime/appearance-verification");
fs.mkdirSync(output, { recursive: true });
const threadId = "b3495e21-5fb1-4997-8ee3-35c2b90e2315";
let messages = [];
const thread = () => ({
  thread_id: threadId,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  metadata: {},
  status: "idle",
  values: { messages },
});
const server = http.createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  if (req.method === "OPTIONS") return res.end();
  const url = req.url.split("?")[0];
  let body = "";
  for await (const chunk of req) body += chunk;
  if (url.endsWith("/runs/stream")) {
    messages.push(...JSON.parse(body).input.messages);
    res.writeHead(200, { "Content-Type": "text/event-stream" });
    const event = (name, value) =>
      res.write(`event: ${name}\ndata: ${JSON.stringify(value)}\n\n`);
    event("metadata", {
      run_id: "58fef55c-5b0f-4c7d-87ae-e7008ac2f862",
      thread_id: threadId,
    });
    event("values", { messages });
    await new Promise((resolve) => setTimeout(resolve, 1000));
    messages.push({
      id: "ai-tools",
      type: "ai",
      content: "Looking up the policy…",
      tool_calls: [
        {
          id: "call-1",
          name: "lookup_information",
          args: { question: "VPN policy" },
        },
      ],
    });
    event("values", { messages });
    await new Promise((resolve) => setTimeout(resolve, 1000));
    messages.push({
      id: "tool-1",
      type: "tool",
      name: "lookup_information",
      tool_call_id: "call-1",
      content: JSON.stringify({
        evidence: [{ source: "VPN policy", requirement: "Manager approval" }],
        status: "ok",
      }),
    });
    messages.push({
      id: "ai-final",
      type: "ai",
      content:
        "VPN requires **manager approval** [D1]. See [policy](https://example.com/policy).\n\n| Requirement | Status |\n| --- | --- |\n| Approval | Required |\n\n> Contact IT Operations.\n\nUse `request_id`:\n\n```python\nprint('VPN policy')\n```",
    });
    event("values", { messages });
    return res.end();
  }
  res.setHeader("Content-Type", "application/json");
  if (url === "/threads/search")
    return res.end(JSON.stringify(messages.length ? [thread()] : []));
  if (url.endsWith("/history")) return res.end("[]");
  if (url.endsWith("/state"))
    return res.end(
      JSON.stringify({
        values: { messages },
        next: [],
        tasks: [],
        checkpoint: null,
      }),
    );
  if (url.startsWith("/threads")) return res.end(JSON.stringify(thread()));
  res.end("{}");
});

(async () => {
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const apiUrl = `http://127.0.0.1:${server.address().port}`;
  const base = process.env.WEB_UI_URL || "http://127.0.0.1:3000";
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.WEB_BROWSER_PATH
      ? { executablePath: process.env.WEB_BROWSER_PATH }
      : {}),
  });
  const checks = [];
  const errors = [];
  let activePage;
  try {
    for (const mobile of [false, true]) {
      messages = [];
      const context = await browser.newContext({
        viewport: mobile
          ? { width: 375, height: 812 }
          : { width: 1440, height: 1000 },
        colorScheme: "dark",
      });
      // Public environment settings may pin the backend URL over query parameters.
      await context.route(
        (url) =>
          url.pathname === "/info" || url.pathname.startsWith("/threads"),
        (route) => {
          const url = new URL(route.request().url());
          return route.continue({
            url: `${apiUrl}${url.pathname}${url.search}`,
          });
        },
      );
      const page = await context.newPage();
      activePage = page;
      page.on("pageerror", (e) => errors.push(e.message));
      page.on("console", (msg) => {
        if (msg.type() === "error") errors.push(msg.text());
      });
      await page.addInitScript(() => {
        window.__firstAppearance = new Promise((resolve) => {
          const sample = () => {
            if (!document.body || !document.body.textContent.trim())
              return requestAnimationFrame(sample);
            resolve({
              theme: document.documentElement.className,
              background: getComputedStyle(document.body).backgroundColor,
            });
          };
          requestAnimationFrame(sample);
        });
      });
      await page.goto(
        `${base}/?apiUrl=${encodeURIComponent(apiUrl)}&assistantId=assistant`,
      );
      const control = page.getByRole("button", { name: /^Appearance:/ });
      const choose = async (theme) => {
        await control.click();
        await page
          .getByRole("menuitemradio", { name: theme, exact: true })
          .click();
      };
      await control.waitFor();
      const newThread = page.getByRole("button", {
        name: "New thread",
        exact: true,
      });
      assert.equal(await newThread.isVisible(), true);
      assert.equal(
        await control.getAttribute("aria-label"),
        "Appearance: System",
      );
      assert.match(
        (await page.evaluate(() => window.__firstAppearance)).theme,
        /dark/,
      );
      const expectTheme = async (theme) => {
        await page.waitForFunction(
          (t) => document.documentElement.classList.contains(t),
          theme,
        );
        assert.equal(
          await page.evaluate(
            () => getComputedStyle(document.documentElement).colorScheme,
          ),
          theme,
        );
      };
      await control.focus();
      await page.keyboard.press("ArrowDown");
      assert.equal(
        await page
          .getByRole("menuitemradio", { name: "System", exact: true })
          .getAttribute("aria-checked"),
        "true",
      );
      await page.keyboard.press("Home");
      assert.equal(
        await page
          .getByRole("menuitemradio", { name: "Light", exact: true })
          .evaluate((el) => el === document.activeElement),
        true,
      );
      await page.keyboard.press("End");
      await page.keyboard.press("Escape");
      assert.equal(
        await control.evaluate((el) => el === document.activeElement),
        true,
      );
      await control.click();
      await page.screenshot({
        path: path.join(
          output,
          `${mobile ? "mobile" : "desktop"}-appearance-menu.png`,
        ),
      });
      const menuBox = await page
        .getByRole("menu", { name: "Appearance", exact: true })
        .boundingBox();
      assert.ok(
        menuBox.x >= 0 &&
          menuBox.x + menuBox.width <= page.viewportSize().width,
      );
      await page.getByRole("textbox", { name: "Message", exact: true }).click();
      assert.equal(await control.getAttribute("aria-expanded"), "false");
      await expectTheme("dark");
      await page.emulateMedia({ colorScheme: "light" });
      await expectTheme("light");
      for (const theme of ["dark", "light", "system"]) {
        await choose(theme[0].toUpperCase() + theme.slice(1));
        assert.equal(
          await page.evaluate(() =>
            localStorage.getItem("agent-chat-appearance"),
          ),
          theme,
        );
        await page.reload();
        assert.equal(
          await control.getAttribute("aria-label"),
          `Appearance: ${theme[0].toUpperCase() + theme.slice(1)}`,
        );
        await expectTheme(theme === "system" ? "light" : theme);
      }
      await choose("Dark");
      await page
        .getByRole("textbox", { name: "Message", exact: true })
        .fill("What does the VPN policy require?");
      await page.getByRole("button", { name: "Send", exact: true }).click();
      await page.getByText("Looking up the policy…", { exact: true }).waitFor();
      await page.getByRole("link", { name: "policy", exact: true }).waitFor();
      await page
        .getByRole("button", { name: "Cancel", exact: true })
        .waitFor({ state: "hidden" });
      assert.ok((await page.locator("body").innerText()).includes("[D1]"));
      assert.ok(
        (await page.locator("body").innerText()).includes("lookup_information"),
      );
      await page.getByRole("textbox", { name: "Message", exact: true }).focus();
      await page.waitForFunction(() => {
        const input = document.querySelector('textarea[aria-label="Message"]');
        return (
          document.activeElement === input &&
          getComputedStyle(input.closest("form").parentElement).boxShadow !==
            "none"
        );
      });
      await page.waitForTimeout(400);
      await page.screenshot({
        path: path.join(output, `${mobile ? "mobile" : "desktop"}-dark.png`),
      });
      await page
        .getByRole("button", { name: "Toggle thread history" })
        .filter({ visible: true })
        .last()
        .click();
      await page
        .getByText("Thread History", { exact: true })
        .filter({ visible: true })
        .waitFor();
      await page
        .getByRole("button", {
          name: "What does the VPN policy require?",
          exact: true,
        })
        .filter({ visible: true })
        .waitFor();
      await page.waitForTimeout(700);
      await page.screenshot({
        path: path.join(
          output,
          `${mobile ? "mobile" : "desktop"}-dark-history.png`,
        ),
      });
      if (mobile)
        await page.getByRole("button", { name: "Close", exact: true }).click();
      else
        await page
          .getByRole("button", { name: "Toggle thread history" })
          .filter({ visible: true })
          .first()
          .click();
      await page.waitForTimeout(700);
      await choose("Light");
      await page.waitForTimeout(400);
      await page.screenshot({
        path: path.join(output, `${mobile ? "mobile" : "desktop"}-light.png`),
      });
      assert.equal(await newThread.isVisible(), true);
      const newThreadBox = await newThread.boundingBox();
      assert.ok(
        newThreadBox.x >= 0 &&
          newThreadBox.x + newThreadBox.width <= page.viewportSize().width,
      );
      await newThread.click();
      await page
        .getByRole("link", { name: "policy", exact: true })
        .waitFor({ state: "hidden" });
      assert.equal(await newThread.isVisible(), true);
      const box = await control.boundingBox();
      assert.ok(box.x >= 0 && box.x + box.width <= page.viewportSize().width);
      checks.push(
        `${mobile ? "mobile" : "desktop"}: fresh System, OS changes, all choices, reload, first paint, streamed conversation, history, focus, menu keyboard navigation/dismissal, control/menu bounds, new thread visible and resets chat`,
      );
      await context.close();
    }
    if (process.env.WEB_SETUP_URL) {
      const page = await browser.newPage({
        viewport: { width: 375, height: 812 },
        colorScheme: "dark",
      });
      page.on("pageerror", (e) => errors.push(e.message));
      await page.goto(process.env.WEB_SETUP_URL);
      await page.getByLabel("Deployment URL").waitFor();
      await page.getByRole("button", { name: /^Appearance:/ }).click();
      await page
        .getByRole("menuitemradio", { name: "Light", exact: true })
        .click();
      await page.screenshot({
        path: path.join(output, "mobile-setup-light.png"),
        fullPage: true,
      });
      await page.getByRole("button", { name: /^Appearance:/ }).click();
      await page
        .getByRole("menuitemradio", { name: "Dark", exact: true })
        .click();
      await page.screenshot({
        path: path.join(output, "mobile-setup-dark.png"),
        fullPage: true,
      });
      checks.push("connection form: mobile Light and Dark control");
    }
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(output, "report.json"),
      JSON.stringify({ passed: true, checks, errors }, null, 2),
    );
    console.log(checks.join("\n"));
  } catch (error) {
    if (activePage && !activePage.isClosed()) {
      await activePage.screenshot({ path: path.join(output, "failure.png") });
      fs.writeFileSync(
        path.join(output, "failure.txt"),
        await activePage.locator("body").innerText(),
      );
    }
    fs.writeFileSync(
      path.join(output, "report.json"),
      JSON.stringify(
        { passed: false, checks, errors, error: error.message },
        null,
        2,
      ),
    );
    console.error(error);
    process.exitCode = 1;
  } finally {
    await browser.close();
    server.close();
  }
})();
