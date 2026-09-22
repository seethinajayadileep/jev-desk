# jev-desk

One Jev call sorts the inbox. Your code decides who gets it.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![typesafe-sdk](https://img.shields.io/pypi/v/typesafe-sdk?label=typesafe-sdk)](https://pypi.org/project/typesafe-sdk/)
[![Jev](https://img.shields.io/badge/model-jev--latest-111111)](https://docs.typesafe.ai)
[![tests](https://github.com/seethinajayadileep/jev-desk/actions/workflows/tests.yml/badge.svg)](https://github.com/seethinajayadileep/jev-desk/actions/workflows/tests.yml)

Paste one customer message. Jev answers three short questions. Your Python code picks the queue.

You can try the whole screen with no API key. The four example buttons use saved answers, and the same rules still choose the queue.

## What Jev is

Jev is a hosted decision model from [TypeSafe](https://docs.typesafe.ai). You send it a piece of text and a list of typed questions. It sends back a label, a score, or a probability, each with the numbers behind that answer.

This demo asks three questions in **one** call:

| You ask | Jev's type | What you get back |
| --- | --- | --- |
| Which team should handle this message? | Choice | billing, technical, sales, or other, plus a probability for each and a confidence |
| How soon does this need a person? | Score | Can wait (0), This week (1), or Today (2). The score is the weighted sum of those levels |
| Is the customer asking for their money back? | Noul | One probability from 0 to 1. A noul has no confidence |

Jev returns those three answers. It does not write the reply to the customer. The queue is chosen in `jev_desk/routing.py`.

This project does not ship model weights. A live call needs an API key. Sample mode needs nothing.

## Try it

Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m jev_desk
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

The banner says **Live Jev is off**. Nothing is sent to Jev. The model line says **not called**.

Click the four examples in this order. Each one lands in a different queue, for a different reason.

| Click this | Queue | Why |
| --- | --- | --- |
| Charged twice, wants the money back today. | Billing | The refund probability is 0.93. Anything at least 0.70 goes to Billing first. |
| Stripe integration failing for three days, losing sales, needs help ASAP. | On-call | Team is technical and the urgency score is 1.88. On-call starts at 1.50. |
| Asking what the annual plan costs. | Sales | The team label is sales, and the confidence is high enough to trust it. |
| A vague "it does not work" with no product or error. | Human review | Team confidence is 0.44 and urgency confidence is 0.37. Under 0.60, a person looks at it. |

Then look under the answers. That block is the playground:

- **Why this queue** shows the four checks with this message's numbers. The check that decided it is highlighted. The rest say they were not used.
- **How the urgency score is made** shows the sum. For the first example that is `0.05×0 + 0.18×1 + 0.77×2 = 1.72`.
- **The one call** shows the Choice, the Score, and the Noul that go out together.
- **Play with the rules** has three sliders: refund cutoff (0.70), confidence floor (0.60), and urgent score (1.50). Let go of a slider. The same answers are routed again, and Jev is not called.

A good first move: on the "charged twice" example, slide the refund cutoff above 0.93. Billing stays the queue, but the reason changes from "refund requested" to "billing team". The probabilities do not change. Only your rule did.

The stamp **Decided in code** means Python picked the queue. The checks, in order:

1. Refund probability 0.70 or higher goes to Billing.
2. Team or urgency confidence below 0.60 goes to Human review.
3. Technical and urgency 1.50 or higher goes to On-call.
4. Otherwise the team label maps to Billing, Technical, Sales, or General.

### A message that is not an example

Paste any other sentence and press **Sort this message**. The page says it was not sent, and the queue stays empty. Sample mode does not invent a team, an urgency, or a refund probability.

### A file

Use **Or upload a file**, then sort.

- A `.txt` or `.pdf` is one message. If the text is exactly one of the four examples, you get that example's queue.
- A `.csv` with several rows sorts each row on its own, up to 20 rows. Put two examples on two lines and both queues show up.
- A header such as `message` or `team,note` labels the cells. A column named `message`, `body`, `text`, or `content` is the message. Put quotes around a cell that contains a comma.
- A PDF has to contain selectable text. A scan, a password-protected PDF, or a file over 20 pages is not sorted.

Files are not stored. An upload can be up to 2 MB. A message can be up to 8,000 characters.

## Where this lives in the code

With an API key, one sort does this:

```python
client = TypeSafeClient(model="jev-latest")
result = client.system_one(message, build_questions())
```

| File | What it does |
| --- | --- |
| `jev_desk/questions.py` | The three questions: team, urgency, refund |
| `jev_desk/triage.py` | Reads `result.choices["team"]`, `result.scores["urgency"]`, and `result.nouls["refund"]`, and logs `result.model` |
| `jev_desk/routing.py` | Turns those answers into a queue |
| `jev_desk/page.py` | The screen, including the playground |
| `jev_desk/samples.py` | The four saved answers used when there is no key |

## Use a live key

```bash
export TYPESAFE_API_KEY=your_key_here
python -m jev_desk
```

Restart after you set the key. Any pasted message or uploaded file goes out once. The model id from the response is shown on the page and written to the log. Keep the key out of git.

The process listens on `0.0.0.0` and `PORT` (8000 when unset).

## Run the tests

```bash
pip install -e ".[dev]"
pytest
```

The tests stay on this machine. They use fake answers and do not call the network.

- `tests/test_routing.py` checks the thresholds, and that moving a cutoff changes the queue.
- `tests/test_triage.py` checks that one message makes one `system_one` call with all three questions.
- `tests/test_page.py` checks the screen, including a custom message that stays unsorted when live Jev is off.
- `tests/test_playground.py` checks the trace, the score math, the sliders, and a two-row CSV.
- `tests/test_uploads.py` checks CSV, text, and PDF reading.
- `tests/test_server.py` checks `PORT`, `GET /health`, the rate limit, and shutdown on `SIGTERM`.

`GET /health` returns `{"status":"ok","mode":"sample"}` or `"mode":"live"`. It does not call Jev.

## Put it on Railway

Railway builds `main` with Railpack. `requirements.txt` installs the SDK and `pypdf`. `main.py` and `railway.toml` start the app. Railway checks `GET /health` before sending traffic.

1. Create a Railway service from this repository.
2. Add the variable `TYPESAFE_API_KEY`. Do not set `PORT`. Railway assigns `PORT`.
3. Turn on public networking and open the service URL.

With no key, the public site stays in sample mode and the four examples still work. Live sorts are limited to 30 a minute per client (`JEV_DESK_SORTS_PER_MINUTE`, or `0` to turn the limit off).

## Share it

The easiest way to show Jev is to let someone click the examples. Lead with the tagline, then the link.

**GitHub About.** On the repository page, use the tagline as the description:

> One Jev call sorts the inbox. Your code decides who gets it.

Topics that help people find it: `python`, `jev`, `typesafe`, `support`, `demo`.

**A post you can copy.**

> One Jev call sorts a support message. Jev answers three typed questions (team, urgency, refund). Ordinary Python picks the queue. No reply is drafted. Try it: https://jev-desk.seethinajayadileep.dev

The source is https://github.com/seethinajayadileep/jev-desk. The live site follows `main`. It is in live mode when `TYPESAFE_API_KEY` is set on Railway.

**What to show.** A short screen recording of two things is enough: the "charged twice" example landing in Billing, then the refund slider moving so the reason changes while the probabilities stay put. That is the whole idea. The queue is your code.

**What to leave out.** Do not paste `TYPESAFE_API_KEY` into a post, a screenshot, or a commit. If you deploy the site, share the public URL and say that sample mode works before anyone adds a key.
