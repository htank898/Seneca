#!/usr/bin/env node
// Turn a transcript into an editor's worksheet: every moment worth considering for an overlay,
// with exact times. It finds candidates; the editing decisions (what to show, what to leave
// alone) are made from reference/editing-playbook.md.
//
//   node cues.mjs talk.transcript.json [--json]
//
// Flags, in priority order:
//   direction  the speaker talking to the editor: "put the logo here", "throw up a slide", "come back"
//   intro      self-introduction: "I'm Jordan", "my name is", "this is Jordan from Acme"
//   money      prices and amounts: "$12,000", "twelve thousand dollars", "per month"
//   number     stats: percentages, multipliers, counts with units, years
//   list       enumerations: "three things", "first / second / finally", "number one"
//   quote      the offer itself: "your quote", "proposal", "pricing", "package", "total"
//   cta        asks: "book a call", "reply", "reach out", "sign", "link", "schedule"
//   signoff    "thank you", "thanks", "talk soon", "cheers"
//   pause      silences over 0.8 s (natural places to start or end a full-screen moment)
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const args = process.argv.slice(2);
const file = args.find((a) => !a.startsWith("--"));
if (!file) { console.error("usage: cues.mjs <talk.transcript.json> [--json]"); process.exit(1); }
const tr = JSON.parse(readFileSync(resolve(file), "utf8"));
const W = tr.words.map((w, i) => ({ ...w, i, n: w.word.toLowerCase().replace(/[^a-z0-9$%'.,]/g, "").replace(/[.,]$/, "") }));
const text = (a, b) => W.slice(a, b + 1).map((w) => w.word).join("").trim();

const NUMWORD = "(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|half|double|triple)";
const RULES = [
  ["direction", /\b(logo|slide|graphic|overlay|animation|animate|title card|lower third|caption|b-?roll|cut to|come back|put (it|this|that|the \w+) (here|up|on screen)|throw (up|in|on)|pop up|show (the|a|my|our) \w+ here|on screen|zoom|pause here|freeze)\b/],
  ["intro", /\b(my name is|i'm [a-z]+|i am [a-z]+|this is [a-z]+ (from|with|at)|here from)\b/],
  ["money", /(\$\s?\d[\d,.]*\s?(k|m|million|thousand)?|\b\d[\d,.]*\s?(dollars|bucks|usd|euros|pounds)\b|\bper (month|year|seat|user|hour)\b|\b(a|per) (month|year)\b)/],
  ["number", new RegExp(`(\\b\\d[\\d,.]*\\s?(%|percent|x|times|hours|days|weeks|months|years|customers|users|people|reps)\\b|\\b${NUMWORD} (percent|times|hours|days|weeks|months|years|thousand|million)\\b|\\b(19|20)\\d\\d\\b)`)],
  ["list", new RegExp(`\\b(${NUMWORD} (things|reasons|steps|ways|options|parts|pieces|points)|first(ly)?|second(ly)?|third(ly)?|finally|number (one|two|three)|step (one|two|three))\\b`)],
  ["quote", /\b(your quote|the quote|a quote|quote for|proposal|pricing|price|package|estimate|investment|total|discount|contract|invoice)\b/],
  ["cta", /\b(book (a|some) (call|time|meeting|demo)|schedule|reply|reach out|get in touch|let me know|sign (up|here|the)|click|link (below|in)|grab (a|some) time|send me|email me|text me|call me|dm me)\b/],
  ["signoff", /\b(thank you|thanks|talk soon|cheers|have a (great|good)|take care|bye|sign off)\b/],
];

// sliding windows of 1..6 words so phrases are reported with their own start/end times
const hits = [];
const seen = new Set();
for (const [kind, re] of RULES) {
  for (let i = 0; i < W.length; i++) {
    for (let len = 6; len >= 1; len--) {
      if (i + len > W.length) continue;
      const phrase = W.slice(i, i + len).map((w) => w.n).join(" ");
      const m = re.exec(phrase);
      if (!m || m.index !== 0) continue;
      // tighten to the words the match actually covers
      let a = i, acc = "";
      let b = i;
      for (; b < i + len; b++) { acc += (acc ? " " : "") + W[b].n; if (acc.length >= m[0].trim().length) break; }
      const key = `${kind}:${a}`;
      if (seen.has(key)) break;
      seen.add(key);
      hits.push({ kind, start: W[a].start, end: W[b].end, say: text(a, b).replace(/[.,!?]$/, ""),
                  context: text(Math.max(0, a - 6), Math.min(W.length - 1, b + 6)) });
      break;
    }
  }
}
for (let i = 1; i < W.length; i++) {
  const gap = W[i].start - W[i - 1].end;
  if (gap > 0.8) hits.push({ kind: "pause", start: W[i - 1].end, end: W[i].start, say: `${gap.toFixed(1)}s silence`,
                             context: `…${text(Math.max(0, i - 4), i - 1)} ‖ ${text(i, Math.min(W.length - 1, i + 3))}…` });
}
hits.sort((x, y) => x.start - y.start);

if (args.includes("--json")) {
  console.log(JSON.stringify({ duration: tr.duration, segments: tr.segments.map(({ start, end, text }) => ({ start, end, text })), cues: hits }, null, 2));
} else {
  console.log(`# Transcript (${tr.duration.toFixed(1)}s)\n`);
  for (const s of tr.segments) console.log(`${s.start.toFixed(2).padStart(6)}–${s.end.toFixed(2).padEnd(6)} ${s.text}`);
  console.log(`\n# Candidate moments (${hits.length})\n`);
  console.log("| time | kind | phrase (use as \"say\") | context |\n|---|---|---|---|");
  for (const h of hits) console.log(`| ${h.start.toFixed(2)}–${h.end.toFixed(2)} | ${h.kind} | ${h.say} | ${h.context.replace(/\|/g, "/")} |`);
}
