# jev-desk

One Jev call sorts the inbox. Your code decides who gets it.

A support-inbox triage demo. Paste one customer message. The app sends that message to TypeSafe Jev once, with three typed questions in the same call: which team should handle it, how soon it needs a person, and whether the customer is asking for a refund. Jev does not write a reply. It returns a team, an urgency, and a refund probability. Ordinary Python then routes the message. The screen shows the message, the three answers with their probabilities, and the queue it landed in.

Jev is a hosted decision model. This project does not ship model weights. A live call needs an API key.

## Run

Python 3.10 or newer.

Install:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Set `TYPESAFE_API_KEY`:

```bash
export TYPESAFE_API_KEY=your_key_here
```

Start the app:

```bash
python -m jev_desk
```

Open the page: [http://127.0.0.1:8000](http://127.0.0.1:8000)

The client is `TypeSafeClient(model="jev-latest")`. Each message is one `system_one` call. The model id on the response is logged and shown on the page.

## Without a key

If `TYPESAFE_API_KEY` is missing, the app does not crash and does not invent a live call. It runs in sample mode. The page says live Jev is off. Four built-in messages still render the same screen, and the queue is still chosen by the code in `jev_desk/routing.py`. Any other message stays unsorted.

1. Charged twice, wants the money back today.
2. Stripe integration failing for three days, losing sales, needs help ASAP.
3. Asking what the annual plan costs.
4. A vague "it does not work" with no product or error.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Routing tests use fake SDK answers and do not use the network. One test checks that a message produces a single `system_one` call with all three questions.
