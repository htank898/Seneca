# Metaphor catalog, honesty rules, inputs

Each metric gets one physical picture that someone with no finance background can read in two seconds. **Built** marks views the engine draws today (`--views` name in brackets). **Sketch** marks metaphors to hand-build in ai-gif or ai-graphic when a story needs them. They use the same palette and the same honesty rules.

## The catalog

| Metric | Formula | Picture | What the viewer should get |
|---|---|---|---|
| **P/E (trailing)** | price ÷ last 12 months' EPS | **Built [payback].** $100 invested in each stock. Each year of earnings is a coin, and coins stack until they reach the dashed $100 line while a year clock runs. It's a race: cheap stocks finish first. | "At today's profits, this takes 35 years to earn back what I paid." |
| **P/E (forward)** | price ÷ next 12 months' estimated EPS | Same view, `--basis fwd`. The note under the chart says "estimated". | Same, using what analysts expect next year. |
| **Payback with growth** | years until the sum of EPS·(1+g)^y ≥ price | `--growth` adds "16 yrs at +9%/yr" under each column | Growth is why people pay a high P/E. This shows how much it shortens the wait. |
| **Earnings yield** | EPS ÷ price | **Built [yields].** "What $100 of stock earns in a year", as a bar beside a benchmark line (Treasury yield). | P/E flipped into an interest rate you can compare with a savings account. |
| **FCF yield** | free cash flow ÷ market cap | **Built [yields]**, hatched bar | The cash the business actually threw off per $100. |
| **Dividend yield** | annual dividend ÷ price | **Built [yields]**, solid ink bar, "paid to you" | The part that actually lands in your account. |
| **Market cap vs. profit** | price × shares; floors = market cap ÷ net income | **Built [building].** Each company is a building, height = market value on one shared scale, fixed width (so height alone carries the number). Each floor is one year of profit, and the ground floor is the "rent". | Size and price at once: a tall building with many thin floors is priced richly for its rent. |
| **Margins** | gross, operating, net ÷ revenue | **Built [margins].** A $100 strip of sales gets trimmed in three steps: cost of making it, running the business, then interest, tax and other. | "Of every $100 customers pay, NVDA keeps $52 and KO keeps $26." |
| **P/S** | market cap ÷ revenue | Text on the margins view: "price 8.6× sales". Sketch: a price tag the length of N years of sales receipts. | What you pay per dollar of yearly sales. Useful when there are no profits yet. |
| **PEG** | forward P/E ÷ expected growth % | **Built [field].** Peers on a field: up = forward P/E, right = growth, dashed rays from the origin at PEG 1, 2, 3. Bubble **area** ∝ market cap. | "Who costs more per point of growth?" Rays turn a ratio into a direction. |
| **EV/EBITDA** | (market cap + debt − cash) ÷ EBITDA | **Built [ev].** Buying the whole house, on one shared scale of years of EBITDA: the shares bar, plus hatched debt, minus a dashed cash cut-out, gives a bracket at "26 yrs". Longer bars cost more years of operating profit. | What it costs to buy the whole business, debts included, in years of operating cash profit. |
| **P/B** | market cap ÷ book value | **Built [card]** row. Sketch: a price tag beside a crate labeled "what's on the books". | Price vs. accounting net worth. It matters most for banks and asset-heavy firms. |
| **Revenue / EPS growth** | year-over-year % | Sketch: a staircase with one step per year, and step height = that year's revenue. | Direction and steadiness, not just the last number. |
| **Everything** | — | **Built [card].** A spec sheet with tickers as columns. n/m is muted, losses are brick red. | The reference slide, and the source of truth for the pictures. |

**Suggested sequences**
- *Is it expensive?* payback → field → card
- *Who's actually good?* margins → building → yields
- *Social loop* (about 28 s): payback → building → yields → field
- *Investor deck:* one still per slide, with card last

## Honesty rules (non-negotiable)

1. **Every number has a date and a source.** The footer shows `asOf` and `source`. The explorer lists sources per ticker, plus the benchmark's. Undated data can't ship. Illustrative data sets `"sample": true`, which stamps SAMPLE DATA on every frame and adds "Illustrative sample numbers, not market data" to the footer.
2. **Label trailing vs. forward everywhere.** Payback and yields print their basis under the chart. Forward numbers are estimates, so call them that.
3. **Negative earnings: say so.** P/E, PEG, and payback are *undefined*, not zero and not huge. The engine draws "LOSING MONEY / no payback", writes n/m with the reason, puts loss bars in hatched brick red left of zero, and leaves unplaceable tickers off the field with a note. Never quietly drop a ticker.
4. **Area = value, or don't use area.** Bubbles scale by √(value), so area is proportional. Buildings and bars are fixed width, so only length carries the number. Never scale an icon by both width and height to show one number.
5. **One true linear scale per comparison, in every frame.** Every figure that compares tickers puts them all on one shared linear scale (EV is drawn in years of EBITDA, so its bars compare directly). No log axes unless the figure says "log scale" and logarithms are the point. The camera may zoom, but the axis stays honest. A value too big for the frame is cut at the edge with a zig-zag break and its full value as text. It is never redrawn on a different scale.
6. **Nothing overlaps or clips.** No text on text, no text on an icon or bar, nothing cut off at the frame edge, in any frame of the motion or any still. When things crowd, one fades out smoothly before contact, or it sits in a fixed side lane. Every position is assigned once per scene, never recomputed per frame from its neighbors. `scripts/check-overlaps.mjs` must pass before anything ships.
7. **No investment advice.** Describe; don't prescribe. Allowed: "costs more per dollar of earnings", "pays back sooner at today's profits". Not allowed: "cheap", "a buy", "undervalued", "overpriced", "you should", price targets. The footer always says "An explanation, not investment advice."
8. **Metaphors state their assumptions.** Payback holds earnings flat unless `--growth` is on, and it says so. Floors use net income. EV uses total debt and cash as given.
9. **Units and currency are consistent.** Use one currency per scene (`"currency"`). Shares and dollar amounts use the same scale. When in doubt use strings ("15.2B"), because they can't be off by 1,000×.

## Inputs

JSON (`templates/input-template.json`) or CSV with one row per ticker (`templates/input-template.csv`). Only `symbol` and `price` are required. Each view uses what it needs and the calculator skips views with no data.

| Field | Meaning | Used by |
|---|---|---|
| `symbol`, `name`, `color` | ticker, display name, optional hex | all |
| `price` | share price | P/E, yields |
| `shares` or `market_cap` | shares outstanding, or market cap | everything sized |
| `eps_ttm`, `eps_fwd` | EPS for the trailing 12 months, and the forward 12-month estimate | payback, yields, field |
| `revenue`, `gross_profit`, `operating_income`, `net_income` | trailing 12 months | margins, building, P/S |
| `ebitda`, `debt`, `cash` | trailing 12-month EBITDA, total debt, cash and short-term investments | ev |
| `fcf` | trailing 12-month free cash flow (operating cash flow − capex) | yields |
| `book_value` | total shareholders' equity | P/B |
| `dividend` | annual dividend per share | yields |
| `growth` | expected annual EPS growth (`"12%"` or `0.12`) | PEG, field, `--growth` |
| `asOf`, `source` | per ticker, overriding the top-level values | footer, explorer |

Top level: `title`, `asOf`, `source`, `sample`, `currency` (default `$`), `benchmark` `{label, rate, source, asOf}`, `notes` [..], `theme` {color overrides}, `basis`, `views`, `size`.

If `net_income` is missing, it's derived as `eps_ttm × shares`, and `shares` as `market_cap ÷ price`. Both are listed under "Derived" in the explorer's sources.
