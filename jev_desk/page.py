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
  --desk: #e5ded1;
  --paper: #fbf7f0;
  --ink: #1c1915;
  --muted: #5e564c;
  --rule: #d5cbbd;
  --stamp: #8f2d24;
  --fill: #1c1915;
  --track: #e7e0d4;
  --live: #1d4e45;
  --sample: #8a5a12;
  --shadow: 0 18px 40px rgba(48, 36, 18, 0.08);
  --serif: "Liberation Serif", "DejaVu Serif", Georgia, serif;
  --sans: Inter, "Liberation Sans", "Noto Sans", sans-serif;
  --mono: "JetBrains Mono", "Liberation Mono", ui-monospace, monospace;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  color: var(--ink);
  background: var(--desk);
  font-family: var(--sans);
  font-size: 16px;
  line-height: 1.45;
}}
.wrap {{
  max-width: 1080px;
  margin: 0 auto;
  padding: 0 1.25rem;
}}
.mast {{ background: #161411; color: #f6f1e7; }}
.mast-row {{
  display: flex;
  justify-content: space-between;
  gap: 1.5rem;
  align-items: flex-end;
  padding: 1.35rem 0 1.4rem;
}}
main.wrap {{ padding-top: 1.25rem; padding-bottom: 3rem; }}
.brand {{
  font-family: var(--serif);
  font-size: 2.6rem;
  line-height: 0.9;
  letter-spacing: -0.03em;
  margin: 0;
  color: #f7f1e6;
}}
.tagline {{
  margin: 0.5rem 0 0;
  max-width: 30rem;
  font-family: var(--serif);
  font-size: 1.18rem;
  font-weight: 400;
  color: #e7dccb;
}}
.mode {{
  margin: 0;
  max-width: 18rem;
  padding: 0.6rem 0.75rem;
  border: 1px solid currentColor;
  font-size: 0.82rem;
}}
.mode.live {{ color: #d7efe8; border-color: #8fbfb3; }}
.mode.sample {{ color: #3d2c10; background: #f3e2c4; border-color: #f3e2c4; }}
.desk {{
  display: grid;
  grid-template-columns: minmax(280px, 0.92fr) minmax(320px, 1.08fr);
  gap: 1rem;
  align-items: start;
}}
.card {{
  background: var(--paper);
  border: 1px solid var(--rule);
  box-shadow: var(--shadow);
  padding: 1.1rem 1.15rem 1.2rem;
}}
h2 {{
  margin: 0 0 0.7rem;
  font-family: var(--serif);
  font-size: 1.35rem;
  font-weight: 400;
}}
label {{ display: block; font-size: 0.78rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }}
textarea {{
  width: 100%;
  margin-top: 0.4rem;
  min-height: 9.5rem;
  resize: vertical;
  padding: 0.75rem 0.8rem;
  border: 1px solid var(--rule);
  background: #fffdf9;
  color: var(--ink);
  font: 1rem/1.45 var(--sans);
}}
textarea:focus, button:focus-visible {{
  outline: 2px solid var(--ink);
  outline-offset: 2px;
}}
.actions {{ display: flex; justify-content: space-between; gap: 0.75rem; align-items: center; margin-top: 0.75rem; }}
button, .samples button {{
  font: 600 0.92rem/1 var(--sans);
  color: var(--paper);
  background: var(--ink);
  border: 1px solid var(--ink);
  padding: 0.72rem 0.9rem;
  cursor: pointer;
}}
button:hover, .samples button:hover {{ background: #322c26; }}
.hint {{ margin: 0; color: var(--muted); font-size: 0.82rem; }}
.samples {{ margin-top: 1.15rem; }}
.samples h3 {{
  margin: 0 0 0.45rem;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
}}
.samples form {{ margin: 0 0 0.4rem; }}
.samples button {{
  width: 100%;
  text-align: left;
  color: var(--ink);
  background: transparent;
  border-color: var(--rule);
  font-weight: 450;
  line-height: 1.35;
  padding: 0.55rem 0.7rem;
}}
.samples button:hover {{ background: #f3ece2; }}
.notice {{
  margin: 0 0 0.8rem;
  padding: 0.55rem 0.7rem;
  background: #f8efe3;
  border-left: 3px solid var(--sample);
}}
.slip {{ min-height: 100%; }}
.queue {{
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  padding-bottom: 0.9rem;
  margin-bottom: 0.9rem;
  border-bottom: 1px solid var(--rule);
}}
.kicker {{
  margin: 0 0 0.35rem;
  font-size: 0.75rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
}}
.queue-name {{
  margin: 0;
  font-family: var(--serif);
  font-size: 2.7rem;
  line-height: 0.95;
  letter-spacing: -0.03em;
}}
.queue-name[data-queue="billing"] {{ color: #8f2d24; }}
.queue-name[data-queue="on-call"] {{ color: #8a3b12; }}
.queue-name[data-queue="human-review"] {{ color: #6d4e12; }}
.queue-name[data-queue="technical"] {{ color: #1d4e45; }}
.queue-name[data-queue="sales"] {{ color: #2a3b78; }}
.queue-reason {{ margin: 0.35rem 0 0; font-size: 1rem; }}
.stamp {{
  flex: 0 0 auto;
  margin-top: 0.2rem;
  padding: 0.35rem 0.5rem;
  border: 2px solid var(--stamp);
  color: var(--stamp);
  font-family: var(--mono);
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  transform: rotate(-2deg);
}}
.message {{
  margin: 0 0 1rem;
  padding: 0.7rem 0.8rem;
  background: #f3eee6;
  white-space: pre-wrap;
}}
.answers {{ display: grid; gap: 0.85rem; }}
.answer h3 {{
  margin: 0;
  font-size: 0.75rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
}}
.chosen {{
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: baseline;
  margin: 0.15rem 0 0.45rem;
}}
.chosen strong {{ font-family: var(--serif); font-size: 1.45rem; font-weight: 400; }}
.meta {{ margin: 0; color: var(--muted); font-family: var(--mono); font-size: 0.78rem; }}
ul.probs {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 0.28rem; }}
ul.probs li {{
  display: grid;
  grid-template-columns: 6.5rem 1fr 3.2rem;
  gap: 0.45rem;
  align-items: center;
  font-size: 0.86rem;
}}
ul.probs li.picked .name {{ font-weight: 650; }}
.track {{ height: 0.45rem; background: var(--track); }}
.fill {{ display: block; height: 100%; background: #b7aea0; }}
li.picked .fill {{ background: var(--fill); }}
.value {{ font-family: var(--mono); font-size: 0.78rem; text-align: right; }}
.refund .track {{ height: 0.7rem; }}
.footnote {{
  margin: 1rem 0 0;
  color: var(--muted);
  font-size: 0.82rem;
}}
.empty {{
  min-height: 18rem;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}}
.empty p {{ margin: 0.3rem 0 0; max-width: 26rem; }}
.rules {{ margin: 0.8rem 0 0; padding-left: 1.1rem; color: var(--muted); font-size: 0.88rem; }}
footer {{
  margin-top: 1rem;
  color: var(--muted);
  font-size: 0.82rem;
}}
@media (max-width: 800px) {{
  .mast-row {{ flex-direction: column; align-items: flex-start; }}
  .mode {{ max-width: none; }}
  .desk {{ grid-template-columns: 1fr; }}
  .queue-name {{ font-size: 2.2rem; }}
  ul.probs li {{ grid-template-columns: 5.6rem 1fr 2.8rem; }}
}}
</style>
</head>
<body>
<header class="mast">
  <div class="wrap mast-row">
    <div>
      <h1 class="brand">jev-desk</h1>
      <p class="tagline">{escape(TAGLINE)}</p>
    </div>
    {mode}
  </div>
</header>
<main class="wrap">
<div class="desk">
  <section class="card intake">
    <h2>Customer message</h2>
    <form method="post" action="/">
      <label for="message">Paste one message</label>
      <textarea id="message" name="message" maxlength="8000" placeholder="I was charged twice this morning. Please send the money back today.">{escape(page.draft)}</textarea>
      <div class="actions">
        <p class="hint">One call. Three questions. No drafted reply.</p>
        <button type="submit">Sort this message</button>
      </div>
    </form>
    <div class="samples">
      <h3>Built-in messages</h3>
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
    if page.result is not None:
        return notice + _result(page.result)
    if page.notice:
        return (
            notice
            + '<p class="hint">No team, urgency, or refund probability was invented for this message.</p>'
        )
    return _empty(page.live)


def _empty(live: bool) -> str:
    if live:
        lead = "Paste a message, or try a built-in one. Jev answers the three questions. This page routes it."
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
  <p class="stamp">In code</p>
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
