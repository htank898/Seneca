---
name: ai-interactive-guide
description: Build interactive, click-through software guides as a single HTML file, with a rebuilt replica of an app's screen with a spotlight, step-by-step coach marks that tell people what to click, practice states (menus, modals), and a free-explore mode with hover labels. Use for onboarding walkthroughs, "how do I do X in <app>", user guides, training for internal tools (CRM, ERP, admin consoles), product tours, and interactive demos. Prefer this over screenshot-and-arrow docs or recorded videos.
---

# AI interactive guide: walkthroughs as code

Screenshot-and-arrow user guides were the affordable option when a person had to build them by hand. A click-through replica that tells you what to click, reacts when you click it, and lets you practice without touching the real system used to be a developer's week. Now it's one HTML file.

Paths below are relative to this skill's base directory.

## 1. Design pass
If the `frontend-design` skill is available, invoke it for the **guide layer** (the frame, coach card, and spotlight). The **replica** should look like the real app, but the guide layer should be clearly its own thing so nobody mistakes the practice copy for the product.

## 2. Gather only what's missing
- **App and screen(s)**, plus the **task or tour**: "tour of the home screen", "submit an expense", "convert a lead"
- **Audience**: first-timers need orientation steps; experienced users want only the task.
- **Fidelity**: see `reference/guide-parameters.md`. The default is *faithful*.
- **Layout source**, in order of preference:
  1. A **UI map** captured from the real app (step 3).
  2. Screenshots the user provides.
  3. Your knowledge of a well-known app's layout. Tell the user that details may have drifted.

## 3. Optional: capture the real layout
```bash
node scripts/capture-ui-map.mjs https://app.example.com --headed --profile ./.guide-profile --wait --out ui-map
```
This opens a visible browser. **The user signs in themselves** and navigates to the screen, then presses Enter. It saves `ui-map.json` (every visible control's role, label, position, size, and colors) and a reference `ui-map.png`. It does not save the page's code or assets. Rebuild from the map.
- Never type someone's credentials, and never scrape screens the user didn't ask for.
- The map can contain other people's names or messages. Use placeholder people in the replica, and keep raw captures out of public repos.
- If the REA tools are available (`capture_browser_scenario`, `inspect_web_page`), they can do this capture too, including for Electron desktop apps.

## 4. Build
1. Copy `templates/guide-shell.html` to the output location (not inside this skill).
2. Set the guide bar's title and keep the "practice replica" note.
3. Rebuild the **replica** with your own HTML/CSS at the app's desktop size (`data-width`/`data-height` on `#stage`):
   - Match the layout grid, spacing, type sizes, colors, and labels so it's instantly recognizable.
   - Draw your own icons as inline SVG. **Don't copy third-party code, logos, or images.** A neutral shape stands in for a logo.
   - Use placeholder people and content.
   - Give every element a step points at a `data-guide="id"`. Give anything worth a hover label a `data-tip="…"`.
4. Model **states** (menus, modals, tabs) as CSS keyed on `#stage.s-<state>`, and turn them on per step with `states: [...]`.
5. Write `GUIDE_STEPS`, following the step rules in the reference. Use `action: "click"` when the learner should physically click the target. That step only advances when they do.
   - Wording must match what the replica can actually do. For anything the replica doesn't respond to, write "This is where you'd…" or "In the real app…", never "Type here" or "Click this".

## 5. Verify before reporting
```bash
node scripts/render-steps.mjs path/to/guide.html --gif
```
This writes one screenshot per step (plus an optional walkthrough GIF). Look at every step and check:
- The spotlight frames the right element.
- The card doesn't cover the target.
- States open and close on the right steps.
- Nothing in the replica overflows.

Fix placement with `place: "left|right|above|below"`. Then delete the step screenshots unless the user wants them, and report the HTML path.
