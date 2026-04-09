import json
import os
import time
from pathlib import Path

import requests

RETAILCRM_BASE_URL = os.getenv("RETAILCRM_BASE_URL", "").rstrip("/")
RETAILCRM_API_KEY = os.getenv("RETAILCRM_API_KEY", "")
RETAILCRM_SITE = os.getenv("RETAILCRM_SITE", "").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

THRESHOLD = 50000
STATE_FILE = Path("retailcrm_bot_state.json")
CHECK_EVERY_SECONDS = 300

session = requests.Session()
session.headers.update({"X-API-KEY": RETAILCRM_API_KEY})


def load_state() -> dict:
    if STATE_FILE.exists():
        with STATE_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_since_id": None, "sent_order_ids": []}


def save_state(state: dict) -> None:
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_telegram_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=30)
    resp.raise_for_status()


def get_orders_history(since_id: int | None) -> tuple[list[dict], int | None]:
    history = []
    current_since_id = since_id
    last_since_id = since_id

    while True:
        params = {"limit": 100}
        if current_since_id is not None:
            params["filter[sinceId]"] = current_since_id

        resp = session.get(
            f"{RETAILCRM_BASE_URL}/api/v5/orders/history",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        batch = data.get("history") or []
        if not batch:
            break

        history.extend(batch)
        last_since_id = batch[-1]["id"]
        current_since_id = last_since_id

        if len(batch) < 100:
            break

    return history, last_since_id


def extract_orders(history_entries: list[dict]) -> list[dict]:
    unique_orders = {}

    for entry in history_entries:
        order = entry.get("order")
        if isinstance(order, dict) and order.get("id") is not None:
            unique_orders[int(order["id"])] = order

    return list(unique_orders.values())


def extract_total(order: dict) -> float:
    for key in ("totalSumm", "summ", "totalSum"):
        value = order.get(key)
        if value is not None:
            return float(value)
    return 0.0


def build_message(order: dict, total: float) -> str:
    order_id = order.get("id")
    number = order.get("number")
    first_name = order.get("firstName") or ""
    last_name = order.get("lastName") or ""
    phone = order.get("phone") or ""
    return (
        f"Новый крупный заказ\n"
        f"ID: {order_id}\n"
        f"Номер: {number}\n"
        f"Сумма: {total:.2f}\n"
        f"Клиент: {first_name} {last_name}".strip() + "\n"
        f"Телефон: {phone}"
    )


def check_once() -> None:
    state = load_state()
    history_entries, new_since_id = get_orders_history(state["last_since_id"])

    if not history_entries:
        return

    sent_order_ids = set(state.get("sent_order_ids", []))
    orders = extract_orders(history_entries)

    for order in orders:
        order_id = int(order["id"])

        if order_id in sent_order_ids:
            continue

        total = extract_total(order)

        if total > THRESHOLD:
            send_telegram_message(build_message(order, total))

        sent_order_ids.add(order_id)

    state["last_since_id"] = new_since_id
    state["sent_order_ids"] = list(sent_order_ids)[-1000:]
    save_state(state)


if __name__ == "__main__":
    while True:
        try:
            check_once()
        except Exception as e:
            print("ERROR:", e)
        time.sleep(CHECK_EVERY_SECONDS)