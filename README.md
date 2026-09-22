# jev-desk

One Jev call sorts the inbox. Your code decides who gets it.

A support-inbox triage demo. Paste one customer message, or upload a CSV, text file, or PDF. The app sends that text to TypeSafe Jev once, with three typed questions in the same call: which team should handle it, how soon it needs a person, and whether the customer is asking for a refund. Jev returns a team, an urgency, and a refund probability. Ordinary Python then routes the message. The screen shows the message, the three answers with their probabilities, and the queue it landed in.

Jev is a hosted decision model. This project does not ship model weights. A live call needs an API key. You can play the whole screen without one.

## Play with no API key

Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m jev_desk
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

The banner says **Live Jev is off**. Nothing is sent to Jev. The four example buttons still fill the same screen, and `jev_desk/routing.py` still picks the queue. The model line says **not called**.

Click the examples in this order. Each one hits a different rule.

| Example | Queue | Reason | What to notice |
| --- | --- | --- | --- |
| Charged twice, wants the money back today. | Billing | refund requested | Refund probability is 0.93. The rule is 0.70 or higher, so Billing wins before team or urgency is considered. |
| Stripe integration failing for three days, losing sales, needs help ASAP. | On-call | technical and urgent | Refund is 0.08. Team is technical with confidence 0.86. Urgency score is 1.88, and On-call starts at 1.50. |
| Asking what the annual plan costs. | Sales | sales team | Team is sales with confidence 0.93. Urgency is "Can wait" (score 0.46). The team label becomes the queue. |
| A vague "it does not work" with no product or error. | Human review | low confidence | Team confidence is 0.44 and urgency confidence is 0.37. Either one under 0.60 sends it to a person. |

On each result, read the three answer blocks:

- **Team** is a Choice. You get the chosen label, a probability for billing, technical, sales, and other, and a confidence.
- **Urgency** is a Score on an ordered scale: Can wait is 0, This week is 1, Today is 2. The score is the probability-weighted number. For the first example that is `0.05×0 + 0.18×1 + 0.77×2 = 1.72`. The chosen label is the level with the highest probability.
- **Refund** is a Noul. One probability from 0 to 1. A noul has no confidence.

The stamp **Decided in code** means the queue came from Python. The rules on the empty screen are the same ones in `route()`:

1. Refund probability 0.70 or higher goes to Billing.
2. Team or urgency confidence below 0.60 goes to Human review.
3. Technical and urgency 1.50 or higher goes to On-call.
4. Otherwise the team label maps to Billing, Technical, Sales, or General.

### Try a message that is not an example

Paste any other sentence and press **Sort this message**. The page says the message was not sent, and it leaves the queue empty. Sample mode does not invent team, urgency, or refund numbers.

### Try a file

Use **Or upload a file**, then sort. A `.txt`, `.csv`, or `.pdf` is read into one message.

- A text file, or a one-line CSV, whose text is exactly one of the four examples gets that example's queue.
- A CSV with a short header becomes labeled lines, such as `team: billing` and `note: Charged twice`. In sample mode that combined text is not an example, so the queue stays empty and the extracted text is shown.
- A PDF has to contain selectable text. A scan, a password-protected PDF, a file over 20 pages, or any other file type is not sorted.

Files are not stored. An upload can be up to 2 MB. The message itself can be up to 8,000 characters.

## See the call in the code

When a key is set, one sort does this:

```python
client = TypeSafeClient(model="jev-latest")
result = client.system_one(message, build_questions())
```

`build_questions()` in `jev_desk/questions.py` returns the three questions together:

| Key | Type | Question |
| --- | --- | --- |
| `team` | Choice | Which team should handle this message? |
| `urgency` | Score | How soon does this need a person? |
| `refund` | Noul | The customer is asking for a refund or their money back. |

`jev_desk/triage.py` reads `result.choices["team"]`, `result.scores["urgency"]`, and `result.nouls["refund"]`. It logs `result.model`. The page shows that model id. `jev_desk/routing.py` turns those three answers into the queue.

## Play with a live key

```bash
export TYPESAFE_API_KEY=your_key_here
python -m jev_desk
```

Restart the process after setting the key. Any pasted message or uploaded file goes out once. The model id on the response is shown on the page and written to the log. Leave the key out of git.

The process listens on `0.0.0.0` and `PORT` (8000 when unset).

## Run the tests

```bash
pip install -e ".[dev]"
pytest
```

The tests stay on this machine. They use fake SDK answers and do not call the network.

- `tests/test_routing.py` checks the thresholds: refund first, then low confidence, then on-call, then the team label.
- `tests/test_triage.py` checks that one message makes one `system_one` call carrying all three questions.
- `tests/test_page.py` checks the screen, including a custom message that stays unsorted when live Jev is off.
- `tests/test_uploads.py` checks CSV, text, and PDF extraction, and that a bad file type does not invent a queue.
- `tests/test_server.py` checks `PORT`, `GET /health`, the rate limit, and shutdown on `SIGTERM`.

`GET /health` returns `{"status":"ok","mode":"sample"}` or `"mode":"live"`. It does not call Jev.

## Deploy on Railway

Railway builds the default branch, `main`, with Railpack. `requirements.txt` installs the SDK and `pypdf`. `main.py` and `railway.toml` start the app. Railway checks `GET /health` before sending traffic.

1. Create a Railway service from this repository.
2. Add the variable `TYPESAFE_API_KEY`. Do not set `PORT`. Railway assigns `PORT`.
3. Enable public networking and open the service URL.

Without the key, the public site stays in sample mode and the four examples still work. Live sorts are limited to 30 a minute per client (`JEV_DESK_SORTS_PER_MINUTE`, or `0` to turn the limit off). The client address is the first hop of `X-Forwarded-For`. The process exits on `SIGTERM` so a new deploy can take the port.
