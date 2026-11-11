// Builds pricing-update.eml (multipart/alternative: text/plain + text/html)
// from pricing-update-email.txt and pricing-update-email.html, so the three stay in sync.
// No dependencies. Run: node build-eml.mjs
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";

const here = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(join(here, "pricing-update-email.html"), "utf8");
const text = readFileSync(join(here, "pricing-update-email.txt"), "utf8");

// Subject is read from the comment at the top of the HTML so there is one source of truth.
const subject = (html.match(/^\s*Subject:\s*(.+)$/m) || [])[1]?.trim();
if (!subject) throw new Error("No 'Subject:' line found in the HTML comment header");

const CRLF = "\r\n";

// RFC 2045 quoted-printable, operating on UTF-8 bytes. Hard line breaks become CRLF;
// soft breaks keep every encoded line at 76 characters or fewer.
export function qpEncode(str) {
  const lines = str.replace(/\r\n?/g, "\n").split("\n");
  return lines
    .map((line) => {
      const bytes = Buffer.from(line, "utf8");
      const tokens = [];
      for (let i = 0; i < bytes.length; i++) {
        const b = bytes[i];
        const last = i === bytes.length - 1;
        const printable = (b >= 33 && b <= 126 && b !== 61) || ((b === 32 || b === 9) && !last);
        // Encode a leading "." (SMTP dot-stuffing) and a leading "F" ("From " mangling) defensively.
        const leadingRisk = i === 0 && (b === 46 || b === 70);
        tokens.push(printable && !leadingRisk ? String.fromCharCode(b) : "=" + b.toString(16).toUpperCase().padStart(2, "0"));
      }
      const out = [];
      let cur = "";
      for (const t of tokens) {
        if (cur.length + t.length > 75) { out.push(cur + "="); cur = ""; }
        cur += t;
      }
      out.push(cur);
      return out.join(CRLF);
    })
    .join(CRLF);
}

// RFC 2047 encoded-word, only if the header value is not plain ASCII.
function headerValue(v) {
  if (/^[\x20-\x7e]*$/.test(v)) return v;
  return "=?UTF-8?B?" + Buffer.from(v, "utf8").toString("base64") + "?=";
}

function rfc5322Date(d) {
  const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const mons = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const p = (n) => String(n).padStart(2, "0");
  const off = -d.getTimezoneOffset();
  const sign = off >= 0 ? "+" : "-";
  const tz = sign + p(Math.floor(Math.abs(off) / 60)) + p(Math.abs(off) % 60);
  return `${days[d.getDay()]}, ${p(d.getDate())} ${mons[d.getMonth()]} ${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())} ${tz}`;
}

const digest = createHash("sha256").update(text).update(html).digest("hex");
const boundary = "=_lumendesk_alt_" + digest.slice(0, 24);
const now = process.env.EML_DATE ? new Date(process.env.EML_DATE) : new Date();

const headers = [
  `From: "Lumen Desk" <hello@lumendesk.example>`,
  `Reply-To: pricing@lumendesk.example`,
  `To: "Jordan Reyes" <jordan.reyes@harborpine.example>`,
  `Subject: ${headerValue(subject)}`,
  `Date: ${rfc5322Date(now)}`,
  `Message-ID: <pro-pricing-2027.${digest.slice(0, 16)}@lumendesk.example>`,
  `List-Unsubscribe: <mailto:unsubscribe@lumendesk.example?subject=unsubscribe>, <https://lumendesk.example/preferences>`,
  `X-Sample-Data: Lumen Desk is a fictional company; this message is an example.`,
  `MIME-Version: 1.0`,
  `Content-Type: multipart/alternative; boundary="${boundary}"`,
];

// Fold header lines longer than 78 characters at whitespace (RFC 5322 section 2.2.3).
function fold(line) {
  if (line.length <= 78) return line;
  const out = [];
  let rest = line;
  while (rest.length > 78) {
    const cut = rest.lastIndexOf(" ", 78);
    if (cut <= 0) break;
    out.push(rest.slice(0, cut));
    rest = rest.slice(cut); // continuation keeps its leading space
  }
  out.push(rest);
  return out.join(CRLF);
}

const part = (type, body) =>
  [
    `--${boundary}`,
    `Content-Type: ${type}; charset="UTF-8"`,
    `Content-Transfer-Encoding: quoted-printable`,
    ``,
    qpEncode(body),
  ].join(CRLF);

const eml =
  headers.map(fold).join(CRLF) + CRLF + CRLF +
  "This is a multi-part message in MIME format." + CRLF + CRLF +
  part("text/plain", text) + CRLF +
  part("text/html", html) + CRLF +
  `--${boundary}--` + CRLF;

writeFileSync(join(here, "pricing-update.eml"), eml);
console.log(`Wrote pricing-update.eml (${Buffer.byteLength(eml)} bytes), subject: ${subject}`);
