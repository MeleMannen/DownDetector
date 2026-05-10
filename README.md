# DownDetector

A small Python monitor that checks whether a domain/website is up or down.

It does the following:
- Checks DNS resolution for the domain.
- Checks HTTP response from the URL.
- Saves the latest state in `data/state.json`.
- Stores time as Unix timestamps (seconds).
- Prints timestamps in local timezone using the format `YYYY-MM-DD hh:mm:ss`.
- Sends an email on status change (up <-> down), including IP and HTTP status code.

## Requirements

- Python 3.10+

Install dependencies:

```bash
pip install --no-cache-dir -r requirements.txt
```


## Environment Variables

You can set variables in a `.env` file (local run), or in Docker Compose YAML under `environment`/`env_file`.

| Variable | Required | Default | Description |
|---|---|---|---|
| DOMAIN | No | empty | Domain to check with DNS |
| URL | No | empty | URL to check with HTTP |
| CHECK_INTERVAL | No | 300 | Seconds between checks |
| STATE_FILE | No | data/state.json | File path for persisted state |
| SMTP_HOST | No | smtp.gmail.com | SMTP server host |
| SMTP_PORT | No | 465 | SMTP server port |
| SMTP_USE_SSL | No | true | Use SSL directly (`true`/`false`) |
| SMTP_FROM | Yes (for email) | empty | SMTP username |
| SMTP_PASSWORD | Yes (for email) | empty | SMTP password |
| SMTP_TO | No | SMTP_FROM | Recipient email address |
| EMAIL_SUBJECT_PREFIX | No | [DownDetector] | Prefix used in email subject |
| SHOULD_CHECK_IP_CHANGE | No | false | Checks if IP has changed |

If required email variables are missing, the monitor still runs but skips email notifications.

## Example: .env (local)

```env
DOMAIN=your_domain.com
URL=https://your_domain.com
CHECK_INTERVAL=300
STATE_FILE=data/state.json

SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USE_SSL=true
SMTP_FROM=you@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_TO=you@gmail.com
EMAIL_SUBJECT_PREFIX=[DownDetector]
SHOULD_CHECK_IP_CHANGE=true
```

## Example: Docker Compose YAML

```yaml
services:
  downdetector:
    build: .
    environment:
      DOMAIN: your_domain.com
      URL: https://your_domain.com
      CHECK_INTERVAL: "300"
      STATE_FILE: data/state.json
      SMTP_HOST: smtp.gmail.com
      SMTP_PORT: "465"
      SMTP_USE_SSL: "true"
      SMTP_FROM: you@gmail.com
      SMTP_PASSWORD: your_app_password
      SMTP_TO: you@gmail.com
      EMAIL_SUBJECT_PREFIX: "[DownDetector]"
      SHOULD_CHECK_IP_CHANGE: "true"
      TZ: "Europe/Oslo"
    volumes:
      - ./data:/app/data
```

You can also use:

```yaml
env_file:
  - .env
```

## Run

```bash
python main.py
```

State is persisted in `data/state.json` between runs.