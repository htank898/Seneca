# Guide parameters

## Guide types
| Type | Shape | Length |
|---|---|---|
| **Orientation tour** | One screen, every region explained, ends in free explore | 10–18 steps |
| **Task walkthrough** | Do one job end to end, mostly `action: "click"` steps, with states for each screen | 5–12 steps |
| **Practice sandbox** | A task with no hand-holding: the learner clicks, and hints appear only after a wrong click | 3–8 checkpoints |
| **Troubleshooting path** | Branching: "Do you see X?" with Yes/No buttons that jump to different steps (use `guide.go(n)` from custom buttons) | Varies |
| **What's new** | 3–5 steps spotlighting changed UI only | 3–5 steps |

## Step writing rules
- **One action or idea per step.** If you write "and then", split the step.
- **Title = the thing's name as labeled in the UI** ("Notifications", "Start a post"), so learners can find it again on their own.
- **Body:** what it is, then why you'd use it, in 1–3 sentences (max about 45 words). Bold the names of other controls you mention.
- **Click steps:** the `do` line starts with a verb and the exact label: "Click **Me** to open the menu."
- **Be honest about what works.** The replica isn't the real app. If a step points at something that does nothing in the replica (a text box, a search bar, a button with no state behind it), say so: "This is where you'd type your post", "In the real app, clicking this opens…". Use a plain imperative ("Click **Me**") only on `action: "click"` steps, where the replica actually responds.
- Describe **behavior**, not pixels ("the red number is unseen updates", not "the red circle at top right").
- Open with a welcome step (no target) that sets expectations ("about two minutes"), and close with a step that hands off to free explore or the real app.
- **Dates and numbers** in the replica should be plausible and placeholder.

## Fidelity levels
| Level | What it means | When |
|---|---|---|
| **Schematic** | Boxes and labels in the right places, in the guide's own style | Internal process docs, very complex apps, or fast drafts |
| **Faithful** (default) | Rebuilt markup matching layout, spacing, type sizes, colors, and labels. Own icons, no logos, placeholder content | Public guides for third-party apps |
| **Pixel** | Indistinguishable from the real app | Only for the user's **own** product or internal tools they own. Never publish pixel copies of someone else's product, since they can read as phishing kits and raise trademark issues. |

All levels: no working login forms, no real credentials, and a visible "practice replica" note in the guide bar.

## Stage sizes
| Target | `data-width × data-height` |
|---|---|
| Desktop web app | 1440 × 900 (default) or 1280 × 800 |
| Wide admin console | 1600 × 1000 |
| Mobile app | 390 × 844 (and set the coach card to dock at the bottom) |
| Tablet | 1024 × 768 |
The stage scales to fit any window. Below 760px wide, the coach card docks to the bottom.

## Spotlight and card placement
- The spotlight pads the target by 6px. A **pulse** ring appears on click steps.
- The card goes beside the target: right, then below, then left, then above. Override this with `place` when the card would cover something the step mentions.
- For big targets (a whole modal or panel), put the card on the side with the most room and spotlight a smaller child element if possible.
- Keep the card off the target's next-step neighbor so learners can see what's coming.

## States
- Each overlay or screen is a state class: `#stage.s-me .medrop { display: block }`.
- A click step on a trigger (such as "Me") should be followed by a step whose `states` include the opened state, which simulates the click.
- For multi-screen tasks, put each screen in its own container and show it by state, so the whole task stays in one file.

## Accessibility
- The coach card is `role="dialog"` with `aria-live="polite"`. Buttons are real `<button>`s with visible focus.
- Keyboard: → / Enter to advance (Enter also performs click steps), ← to go back, Esc for explore mode.
- `prefers-reduced-motion` turns off the slide, pulse, and nudge animations.
- Contrast: the coach card is ink on white. Don't theme it into low contrast.

## Capture notes
- `capture-ui-map.mjs` records role, accessible name, box, colors, radius, and font for visible controls and landmarks (up to 3 viewports deep). Use the map for positions and labels, and the PNG to check proportions.
- Capture each state you need (menu open, modal open) as a separate run.
- Respect the app's terms. Capture only what the user can already see in their own session, for the purpose of teaching.

## Sharing
- One self-contained HTML file. Host it anywhere static, or attach it.
- `render-steps.mjs --gif` makes a silent walkthrough GIF for READMEs, Slack, or LinkedIn.
