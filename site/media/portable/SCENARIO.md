# Shared scenario for the portable examples (all figures are sample data)

**Company:** Lumen Desk, a fictional help-desk software company (B2B SaaS).
**Proposal:** Raise the Pro plan from **$49 to $59 per seat per month**, effective **January 1, 2027**, for new customers; existing customers move at their next renewal after that date, with a **one-time 10% loyalty discount for their first year** at the new price ($53.10/seat).
**Why:** Pro gained AI ticket triage, SLA reporting, and 24/7 chat support in 2026; Pro is the most-used plan and is priced below comparable tools ($55–$79). Gross margin on Pro fell from 81% to 74% after adding AI triage (model costs).

## Baseline numbers (current, monthly)
- Pro customers: 1,240 accounts, 18,600 seats (avg 15 seats/account)
- Current Pro MRR: 18,600 × $49 = **$911,400**
- Monthly logo churn on Pro: **1.6%**
- Expected extra churn from the increase (finance model): **+0.4 pts** in the first 6 months (to 2.0%), then back to 1.6%
- Net effect at $59 with expected churn (year 1): about **+$657K** extra recurring revenue in 2027 (Finance's model, exactly as computed in what-if-pricing.html: all 18,600 seats reprice Jan 1 at $53.10 with the loyalty discount, churn +0.4 pts for six months)

## Options under decision
- **A. $59 for everyone** (with the loyalty discount above) — recommended by Finance and Product
- **B. $55 for everyone**, no discount — smaller increase, less churn risk
- **C. Hold at $49**, revisit in Q3 2027

Decision owner: **Dana Whitfield, VP Revenue** (fictional). Decision needed by **Friday, November 6, 2026**. Replies go to **pricing@lumendesk.example**.

## Audiences
- Executives: want the revenue impact and the risk in one screen.
- Sales: want talk tracks and objection handling.
- Support: want what customers will ask and what to say.
- Finance: want the model and assumptions.
- Customers (personalized notices): want what changes for *them*, when, and what it costs.

## Sample customers (for personalized notices)
| Account | Seats | Renewal date | Current monthly | New monthly (first year, with 10% loyalty) | After first year |
|---|---|---|---|---|---|
| Harbor & Pine Dental Group | 12 | 2027-02-14 | $588.00 | $637.20 | $708.00 |
| Corvid Logistics | 48 | 2027-04-01 | $2,352.00 | $2,548.80 | $2,832.00 |
| Fernhill Public Library | 6 | 2027-09-30 | $294.00 | $318.60 | $354.00 |

## Design rules for every example
- One self-contained `.html` file: inline CSS and JS, **no external fonts, scripts, images, or network requests**. Works by double-click and offline. System font stacks only (choose deliberately, not just `system-ui` everywhere).
- No login, no tracking, no localStorage requirement (may use it as optional convenience inside try/catch).
- Light and dark themes via `prefers-color-scheme`; readable on phone width (~400px).
- Visible "Sample scenario: Lumen Desk is fictional" note somewhere unobtrusive.
- Forward-looking tone: sell the value; never mock competitors or older ways of working.
- Shared identity: Lumen Desk brand — ink `#1b2a33`, paper `#f6f7f5`, accent teal-green `#2f7d6d`, warm highlight `#d9a441`; dark theme adapts these. Avoid the generic AI looks (cream + serif + terracotta, purple gradients, emoji icons, everything centered).

## Price list for the quote builder (sample, effective January 1, 2027)
- Plans, per seat per month: **Starter $19**, **Pro $59**, **Enterprise $89** (Enterprise adds SSO/SAML, audit log, 99.9% uptime SLA, dedicated success manager).
- Add-ons: **Advanced analytics** $8/seat/month (Pro and Enterprise only); **Extra AI triage volume** $150/month per additional 10,000 tickets (Pro includes 10,000 tickets/month, Enterprise 50,000; not available on Starter); **Premium onboarding** $2,500 one-time.
- Volume discount on seat price: **50–99 seats 5%**, **100+ seats 10%**.
- Billing: monthly, or **annual (pay 10 months for 12)**. Annual applies to recurring charges only, not one-time fees.
- Quotes are valid for 30 days. Sales contact: **sales@lumendesk.example**.
- Order of calculation: seat price × seats → minus volume discount → plus add-ons → annual billing discount on recurring → plus one-time fees.
