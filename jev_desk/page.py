"""One screen: the message, three answers, and the queue."""

from dataclasses import dataclass
from html import escape

from jev_desk.samples import SAMPLES
from jev_desk.triage import GradedAnswer, SortedMessage

TAGLINE = "One Jev call sorts the inbox. Your code decides who gets it."


@dataclass(frozen=True)
class Page:
    live: bool
    draft: str
    result: SortedMessage | None
    notice: str | None
    source: str | None = None


def render_page(page: Page) -> str:
    mode = _live_banner() if page.live else _sample_banner()
    notice = f'<p class="notice">{escape(page.notice)}</p>' if page.notice else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>jev-desk</title>
<style>
:root {{
  --bg: #f5f5f7;
  --surface: #ffffff;
  --ink: #1d1d1f;
  --muted: #6e6e73;
  --line: rgba(0, 0, 0, 0.08);
  --blue: #0071e3;
  --blue-press: #0077ed;
  --track: #e8e8ed;
  --fill: #1d1d1f;
  --sans: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{
  margin: 0;
  min-height: 100vh;
  color: var(--ink);
  background:
    radial-gradient(900px 420px at 50% -80px, #ffffff 0%, rgba(255, 255, 255, 0) 70%),
    var(--bg);
  font-family: var(--sans);
  font-size: 17px;
  line-height: 1.47;
  letter-spacing: -0.011em;
  -webkit-font-smoothing: antialiased;
}}
.nav {{
  position: sticky;
  top: 0;
  z-index: 2;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid var(--line);
}}
.nav-inner {{
  max-width: 1120px;
  margin: 0 auto;
  padding: 0 28px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}}
.wordmark {{
  margin: 0;
  font-size: 21px;
  font-weight: 600;
  letter-spacing: -0.02em;
}}
.mode {{
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.35;
  text-align: right;
  max-width: 28rem;
}}
.mode.live {{ color: #1d1d1f; }}
.wrap {{
  max-width: 1120px;
  margin: 0 auto;
  padding: 0 28px 72px;
}}
.hero {{ padding: 72px 0 36px; }}
.eyebrow {{
  margin: 0 0 12px;
  color: var(--muted);
  font-size: 14px;
  font-weight: 600;
}}
.tagline {{
  margin: 0;
  max-width: 16ch;
  font-size: clamp(40px, 6vw, 72px);
  font-weight: 600;
  line-height: 1.04;
  letter-spacing: -0.035em;
}}
.lede {{
  margin: 18px 0 0;
  max-width: 34rem;
  color: var(--muted);
  font-size: 21px;
  line-height: 1.38;
  letter-spacing: -0.016em;
}}
.desk {{
  display: grid;
  grid-template-columns: minmax(300px, 0.92fr) minmax(340px, 1.08fr);
  gap: 20px;
  align-items: start;
}}
.card {{
  background: var(--surface);
  border-radius: 28px;
  padding: 28px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.04);
}}
h2 {{
  margin: 0 0 16px;
  font-size: 28px;
  font-weight: 600;
  letter-spacing: -0.025em;
}}
label {{
  display: block;
  margin-bottom: 8px;
  color: var(--muted);
  font-size: 14px;
  font-weight: 600;
}}
textarea {{
  width: 100%;
  min-height: 160px;
  resize: vertical;
  padding: 16px 18px;
  border: 0;
  border-radius: 18px;
  background: var(--bg);
  color: var(--ink);
  font: 17px/1.47 var(--sans);
  letter-spacing: -0.011em;
}}
textarea:focus {{
  outline: 2px solid var(--blue);
  outline-offset: 2px;
}}
.actions {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-top: 16px;
}}
button {{
  border: 0;
  border-radius: 980px;
  background: var(--blue);
  color: #fff;
  font: 600 17px/1 var(--sans);
  letter-spacing: -0.015em;
  padding: 12px 22px;
  cursor: pointer;
  transition: background 160ms ease, transform 160ms ease;
}}
button:hover {{ background: var(--blue-press); }}
button:active {{ transform: scale(0.98); }}
button:focus-visible {{
  outline: 2px solid var(--blue);
  outline-offset: 3px;
}}
.hint {{ margin: 0; color: var(--muted); font-size: 13px; }}
.upload {{ margin-top: 22px; }}
input[type="file"] {{
  width: 100%;
  padding: 10px 12px;
  border: 0;
  border-radius: 16px;
  background: var(--bg);
  color: var(--ink);
  font: 15px/1.35 var(--sans);
}}
input[type="file"]::file-selector-button {{
  margin-right: 14px;
  border: 0;
  border-radius: 980px;
  background: #fff;
  color: var(--ink);
  font: 600 14px/1 var(--sans);
  padding: 10px 16px;
  cursor: pointer;
}}
input[type="file"]:focus {{
  outline: 2px solid var(--blue);
  outline-offset: 2px;
}}
.file-source {{
  margin: 0 0 14px;
  color: var(--muted);
  font-size: 13px;
  font-weight: 600;
}}
.samples {{ margin-top: 28px; }}
.samples h3 {{
  margin: 0 0 8px;
  color: var(--muted);
  font-size: 14px;
  font-weight: 600;
}}
.samples form {{ margin: 0; }}
.samples button {{
  width: 100%;
  margin-top: 8px;
  padding: 14px 16px;
  border-radius: 16px;
  background: var(--bg);
  color: var(--ink);
  font-weight: 500;
  font-size: 15px;
  line-height: 1.35;
  text-align: left;
}}
.samples button:hover {{ background: #e8e8ed; }}
.notice {{
  margin: 0 0 18px;
  padding: 14px 16px;
  border-radius: 16px;
  background: #f5f5f7;
  color: var(--ink);
  font-size: 15px;
}}
.slip {{ min-height: 100%; }}
.queue {{ margin-bottom: 22px; }}
.kicker {{
  margin: 0 0 6px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}}
.queue-name {{
  margin: 0;
  font-size: clamp(48px, 6vw, 80px);
  font-weight: 600;
  line-height: 0.98;
  letter-spacing: -0.045em;
}}
.queue-reason {{
  margin: 10px 0 0;
  color: var(--muted);
  font-size: 21px;
  letter-spacing: -0.016em;
}}
.stamp {{
  margin: 14px 0 0;
  color: var(--muted);
  font-size: 14px;
  font-weight: 600;
}}
.message {{
  margin: 0 0 28px;
  padding: 0;
  border: 0;
  color: var(--ink);
  font-size: 19px;
  line-height: 1.4;
  letter-spacing: -0.016em;
  white-space: pre-wrap;
}}
.answers {{ display: grid; gap: 22px; }}
.answer {{
  padding-top: 18px;
  border-top: 1px solid var(--line);
}}
.answer h3 {{
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}}
.chosen {{
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 16px;
  margin: 4px 0 12px;
}}
.chosen strong {{
  font-size: 28px;
  font-weight: 600;
  letter-spacing: -0.03em;
}}
.meta {{
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}}
ul.probs {{
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}}
ul.probs li {{
  display: grid;
  grid-template-columns: 92px 1fr 44px;
  gap: 10px;
  align-items: center;
  color: var(--muted);
  font-size: 14px;
}}
ul.probs li.picked {{ color: var(--ink); font-weight: 600; }}
.track {{
  height: 6px;
  border-radius: 999px;
  background: var(--track);
  overflow: hidden;
}}
.fill {{
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #c7c7cc;
  transition: width 480ms ease;
}}
li.picked .fill {{ background: var(--ink); }}
.value {{
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  text-align: right;
}}
.footnote {{
  margin: 22px 0 0;
  color: var(--muted);
  font-size: 13px;
}}
.empty h2 {{
  margin: 0;
  font-size: clamp(40px, 5vw, 64px);
  line-height: 1.02;
  letter-spacing: -0.04em;
  color: #86868b;
}}
.empty p {{ margin: 14px 0 0; max-width: 36rem; color: var(--muted); font-size: 19px; }}
.rules {{
  margin: 22px 0 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 10px;
  color: var(--ink);
  font-size: 15px;
}}
.rules li {{
  padding-left: 16px;
  border-left: 2px solid #d2d2d7;
}}
footer {{
  margin-top: 28px;
  color: var(--muted);
  font-size: 12px;
  text-align: center;
}}
@media (max-width: 860px) {{
  .nav-inner {{ height: auto; padding: 12px 20px; align-items: flex-start; flex-direction: column; gap: 4px; }}
  .mode {{ text-align: left; max-width: none; }}
  .wrap {{ padding: 0 20px 56px; }}
  .hero {{ padding: 40px 0 24px; }}
  .tagline {{ max-width: 12ch; }}
  .lede {{ font-size: 19px; }}
  .desk {{ grid-template-columns: 1fr; }}
  .card {{ border-radius: 22px; padding: 22px; }}
  .actions {{ flex-direction: column; align-items: stretch; }}
  button {{ width: 100%; }}
  ul.probs li {{ grid-template-columns: 78px 1fr 40px; }}
}}
@media (prefers-reduced-motion: reduce) {{
  html {{ scroll-behavior: auto; }}
  .fill, button {{ transition: none; }}
}}
</style>
</head>
<body>
<header class="nav">
  <div class="nav-inner">
    <p class="wordmark">jev-desk</p>
    {mode}
  </div>
</header>
<main class="wrap">
  <section class="hero">
    <p class="eyebrow">Support inbox</p>
    <h1 class="tagline">{escape(TAGLINE)}</h1>
    <p class="lede">Paste one message, or upload a CSV, text file, or PDF. Jev answers three questions. Your code picks the queue.</p>
  </section>
  <div class="desk">
    <section class="card intake">
      <h2>Message</h2>
      <form method="post" action="/" enctype="multipart/form-data">
        <label for="message">Paste one message</label>
        <textarea id="message" name="message" maxlength="8000" placeholder="I was charged twice this morning. Please send the money back today.">{escape(page.draft)}</textarea>
        <div class="upload">
          <label for="upload">Or upload a file</label>
          <input id="upload" name="upload" type="file" accept=".csv,.txt,.text,.pdf,text/csv,text/plain,application/pdf">
          <p class="hint">CSV, text, or PDF. The text inside is one message.</p>
        </div>
        <div class="actions">
          <p class="hint">One call. Three questions. No drafted reply.</p>
          <button type="submit">Sort this message</button>
        </div>
      </form>
      <div class="samples">
        <h3>Examples</h3>
        {_sample_forms()}
      </div>
    </section>
    <section class="card slip" aria-live="polite">
      {_slip(page, notice)}
    </section>
  </div>
  <footer>Jev is a hosted decision model. This app ships no weights. A live call needs an API key.</footer>
</main>
</body>
</html>
"""


def _live_banner() -> str:
    return '<p class="mode live">Live Jev is on. This message goes out once, with team, urgency, and refund in the same call.</p>'


def _sample_banner() -> str:
    return '<p class="mode sample">Live Jev is off. Built-in samples still use the desk rules. No live call is made.</p>'


def _sample_forms() -> str:
    parts = []
    for sample in SAMPLES:
        message = escape(sample.message)
        parts.append(
            "<form method=\"post\" action=\"/\">"
            f'<button type="submit" name="message" value="{message}">{message}</button>'
            "</form>"
        )
    return "\n".join(parts)


def _slip(page: Page, notice: str) -> str:
    source = f'<p class="file-source">From {escape(page.source)}</p>' if page.source else ""
    if page.result is not None:
        return source + notice + _result(page.result)
    if page.notice:
        return (
            source
            + notice
            + '<p class="hint">No team, urgency, or refund probability was invented for this message.</p>'
        )
    return _empty(page.live)


def _empty(live: bool) -> str:
    if live:
        lead = "Paste a message or upload a CSV, text file, or PDF. Jev answers the three questions. This page routes it."
    else:
        lead = "Live Jev is off. Choose a built-in message to see the same screen with sample answers."
    return f"""
<div class="empty">
  <p class="kicker">Queue</p>
  <h2>Nothing sorted yet</h2>
  <p>{lead}</p>
  <ol class="rules">
    <li>Refund probability 0.70 or higher goes to Billing.</li>
    <li>Team or urgency confidence below 0.60 goes to Human review.</li>
    <li>Technical and urgency 1.50 or higher goes to On-call.</li>
    <li>Otherwise the team label maps to Billing, Technical, Sales, or General.</li>
  </ol>
</div>
"""


def _result(result: SortedMessage) -> str:
    model = escape(result.model) if result.model else "not called"
    model_note = "Returned on the response." if result.live else "Sample mode. Jev was not called."
    return f"""
<div class="queue">
  <div>
    <p class="kicker">Queue</p>
    <h2 class="queue-name" data-queue="{escape(result.queue.lower().replace(" ", "-"))}">{escape(result.queue)}</h2>
    <p class="queue-reason">{escape(result.reason)}</p>
  </div>
  <p class="stamp">Decided in code</p>
</div>
<p class="kicker">Message</p>
<blockquote class="message">{escape(result.message)}</blockquote>
<div class="answers">
  {_graded("Team", result.team, score=None)}
  {_graded("Urgency", result.urgency, score=result.urgency.score)}
  {_refund(result.refund_noul)}
</div>
<p class="footnote">Model <span class="model-id">{model}</span>. {model_note} Python chose the queue. Jev did not write a reply.</p>
"""


def _graded(title: str, answer: GradedAnswer, score: float | None) -> str:
    bits = [f"confidence {fmt(answer.confidence)}"]
    if score is not None:
        bits.insert(0, f"score {fmt(score)}")
    rows = "\n".join(_prob_row(item.label, item.value, item.chosen) for item in answer.probabilities)
    return f"""
<article class="answer">
  <h3>{escape(title)}</h3>
  <div class="chosen">
    <strong>{escape(answer.chosen_label)}</strong>
    <p class="meta">{escape(" · ".join(bits))}</p>
  </div>
  <ul class="probs">{rows}</ul>
</article>
"""


def _refund(noul: float) -> str:
    return f"""
<article class="answer refund">
  <h3>Refund</h3>
  <div class="chosen">
    <strong>{fmt(noul)}</strong>
    <p class="meta">probability, 0 to 1</p>
  </div>
  <ul class="probs">{_prob_row("refund", noul, True)}</ul>
  <p class="meta">No separate confidence on a noul.</p>
</article>
"""


def _prob_row(label: str, value: float, chosen: bool) -> str:
    width = max(0.0, min(100.0, value * 100))
    css = ' class="picked"' if chosen else ""
    return (
        f"<li{css}>"
        f'<span class="name">{escape(label)}</span>'
        f'<span class="track"><span class="fill" style="width:{width:.1f}%"></span></span>'
        f'<span class="value">{fmt(value)}</span>'
        "</li>"
    )


def fmt(value: float) -> str:
    return f"{value:.2f}"
