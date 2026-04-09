import os
import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable

import requests
from supabase import create_client


# =========================
# ENV
# =========================
RETAILCRM_BASE_URL = os.getenv("RETAILCRM_BASE_URL", "").rstrip("/")
RETAILCRM_API_KEY = os.getenv("RETAILCRM_API_KEY", "")
RETAILCRM_SITE = os.getenv("RETAILCRM_SITE", "nbaibakushev").strip() or None

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

SYNC_MODE = os.getenv("SYNC_MODE", "full").strip().lower()
SYNC_SOURCE = os.getenv("SYNC_SOURCE", "retailcrm_orders")

RETAILCRM_PAGE_LIMIT = int(os.getenv("RETAILCRM_PAGE_LIMIT", "100"))
SUPABASE_BATCH_SIZE = int(os.getenv("SUPABASE_BATCH_SIZE", "100"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "60"))
SLEEP_BETWEEN_REQUESTS = float(os.getenv("SLEEP_BETWEEN_REQUESTS", "0.12"))


# =========================
# HELPERS
# =========================
def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def chunks(seq: list[dict], size: int) -> Iterable[list[dict]]:
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def as_jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: as_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [as_jsonable(v) for v in value]
    return value


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return str(value)


def extract_code(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return (
            clean_text(value.get("code"))
            or clean_text(value.get("name"))
            or clean_text(value.get("id"))
        )
    return clean_text(value)


def extract_phone(order: dict) -> str | None:
    direct = clean_text(order.get("phone"))
    if direct:
        return direct

    customer = order.get("customer") or {}
    phones = customer.get("phones") or []
    if isinstance(phones, list) and phones:
        first = phones[0]
        if isinstance(first, dict):
            return clean_text(first.get("number"))
        return clean_text(first)

    return None


def extract_email(order: dict) -> str | None:
    direct = clean_text(order.get("email"))
    if direct:
        return direct

    customer = order.get("customer") or {}
    return clean_text(customer.get("email"))


def normalize_dt(value: Any) -> str | None:
    value = clean_text(value)
    if not value:
        return None

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.isoformat()
        except ValueError:
            pass

    if value.endswith("Z"):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.isoformat()
        except ValueError:
            pass

    return value


def get_nested(data: dict, *path: str) -> Any:
    cur = data
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


# =========================
# RETAILCRM CLIENT
# =========================
class RetailCRMClient:
    def __init__(self, base_url: str, api_key: str, site: str | None = None):
        if not base_url:
            raise ValueError("RETAILCRM_BASE_URL is required")
        if not api_key:
            raise ValueError("RETAILCRM_API_KEY is required")

        self.base_url = base_url
        self.api_key = api_key
        self.site = site
        self.session = requests.Session()
        self.session.headers.update({"X-API-KEY": self.api_key})

    def _get(self, path: str, params: dict | None = None) -> dict:
        time.sleep(SLEEP_BETWEEN_REQUESTS)
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=params or {}, timeout=REQUEST_TIMEOUT)
        if not resp.ok:
            print("HTTP:", resp.status_code)
            print("URL:", resp.url)
            print("BODY:", resp.text)
            resp.raise_for_status()
        data = resp.json()
        if data.get("success") is False:
            raise RuntimeError(
                f"RetailCRM error on {path}: {data.get('errorMsg')} | {data.get('errors')}"
            )
        return data

    def list_orders_page(self, page: int, limit: int = 100) -> dict:
        params = {"page": page, "limit": limit}
        if self.site:
            params["filter[sites][]"] = self.site
        return self._get("/api/v5/orders", params=params)

    def list_all_orders(self) -> list[dict]:
        page = 1
        all_orders: list[dict] = []

        while True:
            data = self.list_orders_page(page=page, limit=RETAILCRM_PAGE_LIMIT)
            orders = data.get("orders") or []
            all_orders.extend(orders)

            pagination = data.get("pagination") or {}
            current_page = pagination.get("currentPage", page)
            total_pages = pagination.get("totalPageCount", current_page)

            print(f"[RetailCRM] page={current_page}/{total_pages}, orders_in_page={len(orders)}")

            if current_page >= total_pages:
                break
            page += 1

        return all_orders

    def get_order_by_id(self, order_id: int) -> dict:
        params = {"by": "id"}
        if self.site:
            params["site"] = self.site
        data = self._get(f"/api/v5/orders/{order_id}", params=params)
        order = data.get("order")
        if not order:
            raise RuntimeError(f"RetailCRM returned no 'order' for id={order_id}")
        return order

    def orders_history_since(self, since_id: int | None) -> tuple[list[dict], int | None]:
        """
        Возвращает:
        - список записей history
        - last history id, который нужно сохранить в sync_state
        """
        history_entries: list[dict] = []
        current_since_id = since_id
        last_history_id = since_id

        while True:
            params = {"limit": RETAILCRM_PAGE_LIMIT}
            if current_since_id is not None:
                params["filter[sinceId]"] = current_since_id

            data = self._get("/api/v5/orders/history", params=params)
            batch = data.get("history") or []

            if not batch:
                break

            history_entries.extend(batch)

            last_entry = batch[-1]
            current_since_id = last_entry.get("id")
            last_history_id = current_since_id

            pagination = data.get("pagination") or {}
            current_page = pagination.get("currentPage", 1)
            total_pages = pagination.get("totalPageCount", 1)

            print(
                f"[RetailCRM history] batch={len(batch)}, "
                f"currentPage={current_page}, totalPages={total_pages}, "
                f"next_since_id={current_since_id}"
            )

            if len(batch) < RETAILCRM_PAGE_LIMIT:
                break

        return history_entries, last_history_id


# =========================
# SUPABASE CLIENT
# =========================
class SupabaseSync:
    def __init__(self, url: str, key: str):
        if not url:
            raise ValueError("SUPABASE_URL is required")
        if not key:
            raise ValueError("SUPABASE_KEY is required")

        self.client = create_client(url, key)

    def get_sync_state(self, source: str) -> dict:
        response = (
            self.client.table("sync_state")
            .select("*")
            .eq("source", source)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if rows:
            return rows[0]
        row = {"source": source, "last_since_id": None, "last_sync_at": None}
        (
            self.client.table("sync_state")
            .upsert(row, on_conflict="source")
            .execute()
        )
        return row

    def update_sync_state(self, source: str, last_since_id: int | None) -> None:
        row = {
            "source": source,
            "last_since_id": last_since_id,
            "last_sync_at": now_utc_iso(),
        }
        (
            self.client.table("sync_state")
            .upsert(row, on_conflict="source")
            .execute()
        )

    def upsert_orders(self, rows: list[dict]) -> None:
        if not rows:
            return

        rows_with_id = [r for r in rows if r.get("retailcrm_order_id") is not None]
        rows_with_external_only = [
            r for r in rows
            if r.get("retailcrm_order_id") is None and r.get("retailcrm_external_id")
        ]

        for batch in chunks(rows_with_id, SUPABASE_BATCH_SIZE):
            (
                self.client.table("retailcrm_orders")
                .upsert(
                    batch,
                    on_conflict="retailcrm_order_id",
                    returning="minimal",
                )
                .execute()
            )

        for batch in chunks(rows_with_external_only, SUPABASE_BATCH_SIZE):
            (
                self.client.table("retailcrm_orders")
                .upsert(
                    batch,
                    on_conflict="retailcrm_external_id",
                    returning="minimal",
                )
                .execute()
            )

    def replace_order_items(self, order_rows: list[dict], item_rows: list[dict]) -> None:
        order_ids = [
            row["retailcrm_order_id"]
            for row in order_rows
            if row.get("retailcrm_order_id") is not None
        ]

        for order_id in order_ids:
            (
                self.client.table("retailcrm_order_items")
                .delete()
                .eq("retailcrm_order_id", order_id)
                .execute()
            )

        if not item_rows:
            return

        for batch in chunks(item_rows, SUPABASE_BATCH_SIZE):
            (
                self.client.table("retailcrm_order_items")
                .insert(batch, returning="minimal")
                .execute()
            )


# =========================
# TRANSFORM
# =========================
def order_to_order_row(order: dict) -> dict:
    delivery_address = get_nested(order, "delivery", "address") or {}

    first_name = clean_text(order.get("firstName"))
    last_name = clean_text(order.get("lastName"))

    if not first_name:
        first_name = clean_text(get_nested(order, "customer", "firstName"))
    if not last_name:
        last_name = clean_text(get_nested(order, "customer", "lastName"))

    total_sum = (
        order.get("totalSumm")
        if order.get("totalSumm") is not None
        else order.get("summ")
    )
    if total_sum is None:
        total_sum = order.get("totalSum")

    return {
        "retailcrm_order_id": order.get("id"),
        "retailcrm_external_id": clean_text(order.get("externalId")),
        "order_number": clean_text(order.get("number")),
        "site": extract_code(order.get("site")),
        "status": extract_code(order.get("status")),
        "order_type": extract_code(order.get("orderType")),
        "order_method": extract_code(order.get("orderMethod")),
        "first_name": first_name,
        "last_name": last_name,
        "phone": extract_phone(order),
        "email": extract_email(order),
        "city": clean_text(delivery_address.get("city")),
        "address_text": clean_text(delivery_address.get("text")),
        "total_sum": total_sum,
        "currency": clean_text(order.get("currency")),
        "order_created_at": normalize_dt(order.get("createdAt")),
        "order_updated_at": normalize_dt(order.get("updatedAt")),
        "synced_at": now_utc_iso(),
        "raw_order": as_jsonable(order),
    }


def order_to_item_rows(order: dict) -> list[dict]:
    order_id = order.get("id")
    items = order.get("items") or []
    rows: list[dict] = []

    for idx, item in enumerate(items, start=1):
        rows.append(
            {
                "retailcrm_order_id": order_id,
                "line_position": idx,
                "product_name": clean_text(item.get("productName")),
                "quantity": item.get("quantity"),
                "initial_price": item.get("initialPrice"),
                "raw_item": as_jsonable(item),
            }
        )

    return rows


def transform_orders(orders: list[dict]) -> tuple[list[dict], list[dict]]:
    order_rows: list[dict] = []
    item_rows: list[dict] = []

    for order in orders:
        order_row = order_to_order_row(order)
        order_rows.append(order_row)
        item_rows.extend(order_to_item_rows(order))

    return order_rows, item_rows


# =========================
# HISTORY HELPERS
# =========================
def extract_order_refs_from_history(entries: list[dict]) -> list[dict]:
    """
    Пытаемся вытащить идентификаторы заказа из history.
    Форматы могут отличаться, поэтому поддерживаем несколько вариантов.
    """
    refs: list[dict] = []
    seen: set[tuple] = set()

    for entry in entries:
        candidates = []

        # Частый вариант: запись содержит вложенный order
        order_obj = entry.get("order")
        if isinstance(order_obj, dict):
            candidates.append(
                {
                    "id": order_obj.get("id"),
                    "externalId": order_obj.get("externalId"),
                }
            )

        # Возможный вариант: идентификаторы лежат прямо в записи
        if "orderId" in entry or "orderExternalId" in entry:
            candidates.append(
                {
                    "id": entry.get("orderId"),
                    "externalId": entry.get("orderExternalId"),
                }
            )

        # Осторожный fallback: если запись выглядит как объект заказа
        if "site" in entry and ("number" in entry or "externalId" in entry):
            candidates.append(
                {
                    "id": entry.get("id"),
                    "externalId": entry.get("externalId"),
                }
            )

        for cand in candidates:
            order_id = cand.get("id")
            external_id = cand.get("externalId")
            key = (order_id, external_id)
            if key == (None, None):
                continue
            if key in seen:
                continue
            seen.add(key)
            refs.append(cand)

    return refs


# =========================
# MAIN FLOWS
# =========================
def run_full_sync(retail: RetailCRMClient, sb: SupabaseSync) -> None:
    print("[Sync] FULL sync started")
    orders = retail.list_all_orders()
    print(f"[Sync] Orders fetched: {len(orders)}")

    order_rows, item_rows = transform_orders(orders)
    sb.upsert_orders(order_rows)
    sb.replace_order_items(order_rows, item_rows)

    # При full sync since_id не двигаем, только фиксируем last_sync_at
    state = sb.get_sync_state(SYNC_SOURCE)
    sb.update_sync_state(SYNC_SOURCE, state.get("last_since_id"))

    print(f"[Sync] FULL sync completed: orders={len(order_rows)}, items={len(item_rows)}")


def run_history_sync(retail: RetailCRMClient, sb: SupabaseSync) -> None:
    print("[Sync] HISTORY sync started")
    state = sb.get_sync_state(SYNC_SOURCE)
    since_id = state.get("last_since_id")
    print(f"[Sync] last_since_id={since_id}")

    history_entries, new_since_id = retail.orders_history_since(since_id)
    print(f"[Sync] history entries fetched: {len(history_entries)}")

    if not history_entries:
        sb.update_sync_state(SYNC_SOURCE, since_id)
        print("[Sync] No changes")
        return

    refs = extract_order_refs_from_history(history_entries)
    print(f"[Sync] unique changed order refs found: {len(refs)}")

    if not refs:
        print("[Sync] Could not extract order refs from history; state will still be advanced")
        sb.update_sync_state(SYNC_SOURCE, new_since_id)
        return

    full_orders: list[dict] = []

    for ref in refs:
        order_id = ref.get("id")
        external_id = ref.get("externalId")

        if order_id is not None:
            try:
                full_orders.append(retail.get_order_by_id(int(order_id)))
                continue
            except Exception as e:
                print(f"[Warn] Failed to fetch order by id={order_id}: {e}")

        # Если нет id, а только externalId, тут можно будет добавить отдельный fetch по externalId
        if external_id:
            print(f"[Warn] externalId-only ref is not handled yet: {external_id}")

    print(f"[Sync] full changed orders fetched: {len(full_orders)}")

    if not full_orders:
        sb.update_sync_state(SYNC_SOURCE, new_since_id)
        print("[Sync] No full orders fetched")
        return

    order_rows, item_rows = transform_orders(full_orders)
    sb.upsert_orders(order_rows)
    sb.replace_order_items(order_rows, item_rows)
    sb.update_sync_state(SYNC_SOURCE, new_since_id)

    print(
        f"[Sync] HISTORY sync completed: orders={len(order_rows)}, "
        f"items={len(item_rows)}, new_since_id={new_since_id}"
    )


def main() -> None:
    retail = RetailCRMClient(
        base_url=RETAILCRM_BASE_URL,
        api_key=RETAILCRM_API_KEY,
        site=RETAILCRM_SITE,
    )
    sb = SupabaseSync(
        url=SUPABASE_URL,
        key=SUPABASE_KEY,
    )

    print(f"SYNC_MODE={SYNC_MODE}")

    if SYNC_MODE == "full":
        run_full_sync(retail, sb)
    elif SYNC_MODE == "history":
        run_history_sync(retail, sb)
    else:
        raise ValueError("SYNC_MODE must be 'full' or 'history'")


if __name__ == "__main__":
    main()