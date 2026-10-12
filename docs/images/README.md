# README screenshots

These PNGs capture the actual browser UI with fixed synthetic API responses.
The conversation is based on `data/documents/vpn.md` and VPN ownership
in `data/seed.json`. Responses, citation markers, and history entries are
fixtures, not recorded model output. No provider calls or database writes occur.

## Recreate

Use Node.js 22+ and run from the repository root. Install the pinned UI dependencies,
then build the current UI into an isolated directory.

### Windows (PowerShell)

```powershell
$env:WEB_CHECK_DIST_DIR = ".next-readme"
$env:NEXT_PUBLIC_API_URL = "http://localhost:2024"
$env:NEXT_PUBLIC_ASSISTANT_ID = "assistant"
Push-Location ui/agent-chat-ui
npm.cmd exec --yes --package=pnpm@10.5.1 -- pnpm install --frozen-lockfile
node node_modules/next/dist/bin/next build
Pop-Location
node scripts/capture_readme.cjs
```

### Linux / macOS (Bash or Zsh)

```bash
export WEB_CHECK_DIST_DIR=".next-readme"
export NEXT_PUBLIC_API_URL="http://localhost:2024"
export NEXT_PUBLIC_ASSISTANT_ID="assistant"
(
  cd ui/agent-chat-ui
  npm exec --yes --package=pnpm@10.5.1 -- pnpm install --frozen-lockfile
  node node_modules/next/dist/bin/next build
  node node_modules/@playwright/test/cli.js install chromium
)
node scripts/capture_readme.cjs
```

The subshell keeps your terminal in the repository root. On Linux, Playwright
may also require system libraries; use its `install --with-deps chromium` command
if needed.

### Capture behavior (all platforms)

The build fetches the app's Google font. The capture script starts a temporary
UI server on an available local port, intercepts backend requests with fixtures,
and closes its server and browser when finished. It uses Chrome on Windows when
installed; set `WEB_BROWSER_PATH` for another Chromium executable, or install
Playwright Chromium in the UI package. Set `WEB_UI_URL` to capture an already
running, current UI instead of starting one.

The Next.js build may add its temporary type paths to `tsconfig.json`; exclude
those build-generated changes from documentation commits. The isolated build
directory is ignored by Git.

| File | View |
| --- | --- |
| `desktop-light.png` | Conversation and history, 1440 × 960 |
| `desktop-dark.png` | Same conversation in dark appearance, 1440 × 960 |
| `chat-actions.png` | Dark appearance with the chat menu open, 1440 × 960 |
| `mobile.png` | Mobile conversation, 390 × 844 |

The root README uses a `<picture>` element to select the light/dark hero image
and relative image paths so captures work in GitHub and local Markdown previews.
