// Real-model browser verification against already running disposable demo services.
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("../ui/agent-chat-ui/node_modules/@playwright/test");
const root = path.resolve(__dirname, "..");
const output = path.join(root, "runtime", "web-verification");
fs.mkdirSync(output, { recursive: true });
fs.writeFileSync(path.join(output, process.argv.includes("--edge-cases") ? "browser-edge-cases.json" : "browser-report.json"),
  JSON.stringify({ passed: false, status: "running" }));

(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.WEB_BROWSER_PATH ? { executablePath: process.env.WEB_BROWSER_PATH } : {}) });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const turns = [];
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("request", request => {
    if (request.method() === "POST") console.log("Browser POST " + new URL(request.url()).pathname);
  });
  try {
    await page.addInitScript(() => {
      window.__webRuns = [];
      const original = window.fetch;
      window.fetch = async (...args) => {
        const response = await original(...args);
        if (new URL(response.url).pathname.endsWith("/runs/stream")) {
          response.clone().text().then(stream => window.__webRuns.push({ status: response.status, stream }));
        }
        return response;
      };
    });
    await page.goto(process.env.WEB_UI_URL || "http://127.0.0.1:3000");
    const prompts = [
      "What does the VPN access policy require?",
      "Which team handles VPN access, and what does the policy require?",
      "Create a VPN access request for me. Summary: Browser demo remote access. Description: Need VPN for remote work starting October 12.",
      "Show the request you just created, including its status and version.",
      "Set that request to in_progress.",
      "What is its current status and version?",
      "Assign that request to its owning team IT Operations (team-it).",
    ];
    async function submit(prompt) {
      const index = await page.evaluate(() => window.__webRuns.length);
      await page.getByPlaceholder("Type your message...").fill(prompt);
      const responsePromise = page.waitForResponse(r => r.request().method() === "POST" && new URL(r.url()).pathname.endsWith("/runs/stream"), { timeout: 150000 });
      await page.getByRole("button", { name: "Send", exact: true }).click();
      const response = await responsePromise;
      await page.waitForFunction(count => window.__webRuns.length > count, index, { timeout: 150000 });
      const { stream } = await page.evaluate(index => window.__webRuns[index], index);
      turns.push({ prompt, status: response.status(), stream });
      console.log(`Browser turn ${turns.length}: HTTP ${response.status()}`);
      if (!response.ok() || /event: error/.test(stream)) throw new Error("Run failed; inspect browser-report.json");
      await page.getByRole("button", { name: "Cancel", exact: true }).waitFor({ state: "hidden", timeout: 150000 });
      await page.waitForTimeout(1000);
    }
    if (process.argv.includes("--edge-cases")) {
      for (const prompt of ["Create a service request for me.", "Set request req-nonexistent to in_progress."]) await submit(prompt);
      const checks = {
        no_create_without_details: !turns[0].stream.includes('"name":"create_service_request"'),
        no_update_for_invalid_id: !turns[1].stream.includes('"name":"update_service_request_status"'),
        no_page_errors: errors.length === 0,
      };
      fs.writeFileSync(path.join(output, "browser-edge-cases.json"), JSON.stringify({ passed: Object.values(checks).every(Boolean), checks, turns, errors }, null, 2));
      console.log(JSON.stringify(checks, null, 2));
      if (!Object.values(checks).every(Boolean)) process.exitCode = 1;
      return;
    }
    for (const prompt of prompts) await submit(prompt);
    await page.screenshot({ path: path.join(output, "browser-chat.png"), fullPage: true });
    const before = await page.locator("body").innerText();
    const threadUrl = page.url();
    await page.reload();
    await page.getByText("Browser demo remote access", { exact: false }).first().waitFor({ timeout: 30000 });
    const after = await page.locator("body").innerText();
    const checks = { seven_turns: turns.length === 7, tool_activity: before.includes("lookup_information") && before.includes("create_service_request"),
      citations: before.includes("[D1]") && /\[G\d+\]/.test(before), refresh_history: after.includes("in_progress"),
      replay_controls_hidden: await page.getByRole("button", { name: "Refresh", exact: true }).count() === 0,
      readable_mcp_results: !before.includes("[object Object]"),
      no_page_errors: errors.length === 0 };
    await page.goto(process.env.WEB_UI_URL || "http://127.0.0.1:3000");
    checks.new_thread_empty = !(await page.locator("body").innerText()).includes("Set that request to in_progress.");
    await submit("Create a service request for me.");
    checks.missing_details_clarified = !turns[turns.length - 1].stream.includes('"name":"create_service_request"');
    await submit("Set request req-nonexistent to in_progress.");
    checks.invalid_id_no_success = !turns[turns.length - 1].stream.includes('"name":"update_service_request_status"');
    fs.writeFileSync(path.join(output, "browser-report.json"), JSON.stringify({ passed: Object.values(checks).every(Boolean), checks, threadUrl, turns, errors }, null, 2));
    console.log(JSON.stringify(checks, null, 2));
    if (!Object.values(checks).every(Boolean)) process.exitCode = 1;
  } catch (error) {
    fs.writeFileSync(path.join(output, process.argv.includes("--edge-cases") ? "browser-edge-cases.json" : "browser-report.json"), JSON.stringify({ passed: false, error: error.message, turns, errors }, null, 2));
    console.error(error.message);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
