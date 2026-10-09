# Step 9: Dark mode

## Status and scope

Implemented and locally verified. Extend the existing vendored Agent Chat UI with Light, Dark, and System
appearance options. Default to System and persist the choice in the browser.
This step is independent of steps 10 and 11 and requires no backend changes.

## Current implementation

`ui/agent-chat-ui` already includes `next-themes`, Tailwind's dark variant, and
dark color variables in `src/app/globals.css`. `src/app/layout.tsx` does not
mount a theme provider. Several chat/history components use literal white
backgrounds and gray text, so enabling the dark class alone is insufficient.

## Implementation

1. Add a client-side theme provider around the existing application providers.
   Use class-based themes, system preference support, and a persistent storage
   key. Apply the appropriate hydration handling at the root HTML element;
   render theme-dependent controls only when their browser state is available.
2. Add an accessible appearance control in the chat header with Light, Dark,
   and System choices. Keep it reachable on mobile and on the connection form.
3. Audit the setup form, chat header, composer, history sidebar/mobile drawer,
   messages, tool results, artifacts, dialogs, buttons, borders, and toast styles.
   Replace literal surface/text colors with semantic tokens, retaining specific
   status colors with sufficient contrast in both themes. Keep code blocks
   readable without changing their syntax-highlighting behavior unnecessarily.
4. Record the customization in `UPSTREAM.md` and document the control in
   `docs/web-chat.md`.

## Acceptance and verification

- Light, Dark, and System work on desktop and mobile; selecting System tracks
  subsequent OS appearance changes.
- Reload preserves the selection, and a fresh visit uses the system preference.
- Initial loading has no visible theme flash or hydration warnings.
- Inputs, citations, tool JSON, menus, dialogs, and focus indicators remain legible.
- Verify visually in the browser, including history open/closed and a streamed
  conversation. Run the production build and the relevant existing UI checks;
  no new backend tests are needed for this presentation change.

## Main files

- `ui/agent-chat-ui/src/app/layout.tsx` and `globals.css`
- New theme provider/control under `src/components/`
- `src/components/thread/`, including history and message renderers
- `src/providers/Stream.tsx` for the setup form
- `ui/agent-chat-ui/UPSTREAM.md` and `docs/web-chat.md`

## Verification results

- Production build, UI ESLint, and full UI Prettier check pass. ESLint retains
  18 existing warnings; the build retains the upstream Tailwind module-format
  warning and LangGraph passthrough authentication notice.
- `scripts/check_web_appearance.cjs` passes in Chrome on desktop (1440px) and
  mobile (375px), using a disposable deterministic HTTP stream without model
  calls. It checks all three choices, persistence, live OS changes, dark first
  paint, streamed messages/tool JSON/citations, focus, and history open/closed.
- The mobile connection form was checked in Light and Dark. Browser captures
  were visually reviewed, including markdown tables and retained code highlighting.
  No production browser console errors or hydration errors were observed.
- Evidence: ignored `runtime/appearance-verification/report.json` and screenshots.
  No backend changes or new backend tests.
