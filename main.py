import json
import os
import socket
import smtplib
import requests
import time
import signal
from datetime import datetime
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

previous_state = None
running = True

def handle_shutdown(signum, frame):
    global running
    running = False

signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)

DOMAIN = os.getenv("DOMAIN", "")
URL = os.getenv("URL", "")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))
STATE_FILE = os.getenv("STATE_FILE", "data/state.json")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "true").lower() in ("1", "true", "yes", "on")
SMTP_FROM = os.getenv("SMTP_FROM")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_TO = os.getenv("SMTP_TO") or SMTP_FROM
EMAIL_SUBJECT_PREFIX = os.getenv("EMAIL_SUBJECT_PREFIX", "[DownDetector]")
SHOULD_CHECK_IP_CHANGE = os.getenv("SHOULD_CHECK_IP_CHANGE", "true").lower() in ("1", "true", "yes", "on")


def format_local_timestamp(timestamp) -> str:
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "unknown"


def load_state():
    if not os.path.exists(STATE_FILE):
        return None

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load state file: {e}")
        return None


def save_state(state: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def check_dns(domain: str):
    try:
        ip = socket.gethostbyname(domain)
        return True, ip, "DNS resolved"
    except Exception as e:
        return False, None, f"DNS failed: {e}"


def check_url(url: str):
    try:
        response = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "site-monitor/1.0"},
        )
        ok = response.status_code < 500
        if ok:
            return True, response.status_code, "HTTP reachable"
        return False, response.status_code, f"HTTP bad status: {response.status_code}"
    except Exception as e:
        return False, None, f"HTTP failed: {e}"


def get_current_state():
    dns_ok, ip, dns_message = check_dns(DOMAIN)
    http_ok, status_code, http_message = check_url(URL)

    overall_up = dns_ok and http_ok

    return {
        "domain": DOMAIN,
        "url": URL,
        "status": "up" if overall_up else "down",
        "dns_ok": dns_ok,
        "dns_message": dns_message,
        "ip": ip,
        "http_ok": http_ok,
        "http_status": status_code,
        "http_message": http_message,
        "checked_at": int(time.time()),
    }


def state_changed(old_state, new_state) -> bool:
    if old_state is None:
        return False
    if old_state.get("status") != new_state.get("status"):
        return True
    if old_state.get("http_status") != new_state.get("http_status"):
        return True
    if SHOULD_CHECK_IP_CHANGE and old_state.get("ip") != new_state.get("ip"):
        return True
    return False


def print_changes(old_state, new_state):
    print("STATE CHANGE DETECTED")
    print(f"Old: {old_state.get('status')}")
    print(f"New: {new_state.get('status')}")
    print(f"Checked at: {format_local_timestamp(new_state.get('checked_at'))}")
    print(f"IP: {new_state.get('ip')}")
    print(f"HTTP status: {new_state.get('http_status')}")
    print(json.dumps(new_state, indent=2))


def send_email(old_state, new_state):
    if not SMTP_HOST or not SMTP_PORT or not SMTP_FROM or not SMTP_PASSWORD or not SMTP_TO:
        print(
            "Email skipped: missing SMTP_HOST, SMTP_PORT, "
            "SMTP_FROM, SMTP_PASSWORD, or SMTP_TO"
        )
        return

    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = SMTP_TO
    msg["Subject"] = (
        f"{EMAIL_SUBJECT_PREFIX} {new_state.get('domain')} is {new_state.get('status')}"
    )
    previous_change_at = format_local_timestamp(old_state.get("last_changed"))
    msg.set_content(
        "\n".join(
            [
                "DownDetector status change",
                f"Domain: {new_state.get('domain')}",
                f"URL: {new_state.get('url')}",
                f"Old status: {old_state.get('status')}",
                f"New status: {new_state.get('status')}",
                f"IP: {new_state.get('ip')}",
                f"HTTP status: {new_state.get('http_status')}",
                f"Checked at: {format_local_timestamp(new_state.get('checked_at'))}",
                f"Last changed: {previous_change_at}",
                "",
                f"DNS: {new_state.get('dns_message')}",
                f"HTTP: {new_state.get('http_message')}",
            ]
        )
    )

    try:
        if SMTP_USE_SSL:
            smtp = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
        else:
            smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT)

        with smtp:
            if not SMTP_USE_SSL:
                smtp.starttls()
            smtp.login(SMTP_FROM, SMTP_PASSWORD)
            smtp.send_message(msg)

        print(f"Email sent to {SMTP_TO}")
    except Exception as e:
        print(f"Failed to send email: {e}")


def compute_last_changed(old_state, new_state) -> int:
    if old_state is None:
        return new_state["checked_at"]

    if state_changed(old_state, new_state):
        return new_state["checked_at"]

    return int(old_state.get("last_changed"))


def main():
    global previous_state

    previous_state = load_state()

    while running:
        current_state = get_current_state()
        current_state["last_changed"] = compute_last_changed(previous_state, current_state)

        if previous_state is None:
            print(f"Initial state: {current_state['status']} checked_at={format_local_timestamp(current_state['checked_at'])}")
            if current_state["status"] == "down":
                fresh_state = current_state.copy()
                fresh_state["status"] = "unknown"
                print_changes(fresh_state, current_state)
                send_email(fresh_state, current_state)

        elif state_changed(previous_state, current_state):
            print_changes(previous_state, current_state)
            send_email(previous_state, current_state)

        else:
            print(f"No change: status={current_state['status']} dns_ok={current_state['dns_ok']} http_status={current_state['http_status']} last_changed={format_local_timestamp(current_state['last_changed'])} checked_at={format_local_timestamp(current_state['checked_at'])}")

        save_state(current_state)
        previous_state = current_state
        
        remaining = CHECK_INTERVAL
        while running and remaining > 0:
            time.sleep(min(1, remaining))
            remaining -= 1


if __name__ == "__main__":
    main()