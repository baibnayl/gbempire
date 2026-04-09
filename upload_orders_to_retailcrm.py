import json
import os
import re
from pathlib import Path
from typing import Any

import requests


# =========================
# Настройки
# =========================
BASE_URL = os.getenv("RETAILCRM_BASE_URL").rstrip("/")
API_KEY = os.getenv("RETAILCRM_API_KEY")
SITE = os.getenv("RETAILCRM_SITE", "site-code")
ORDERS_FILE = Path(os.getenv("RETAILCRM_ORDERS_FILE", "mock_orders.json"))

TEST_MODE = False # True -> не отправляем все заказы, а только первые TEST_LIMIT
TEST_LIMIT = 1
TIMEOUT = 60
SKIP_INVALID_LOCAL = False # False -> если есть локальные ошибки, ничего не отправляем
FAILED_ORDERS_DUMP = Path("failed_orders.json")


# =========================
# Утилиты
# =========================
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def mask_secret(value: str | None, keep: int = 4) -> str:
    if not value:
        return "<не задан>"
    if len(value) <= keep * 2:
        return "*" * len(value)
    return f"{value[:keep]}...{value[-keep:]}"


def print_section(title: str) -> None:
    print(f"\n{'=' * 18} {title} {'=' * 18}")


def load_orders(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path.resolve()}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("JSON-файл должен содержать массив заказов")

    if not data:
        raise ValueError("JSON-файл пустой")

    for i, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Элемент #{i} должен быть JSON-объектом")

    return data


def validate_item(item: dict, order_index: int, item_index: int) -> list[str]:
    errors: list[str] = []

    if not isinstance(item, dict):
        return [f"товар #{item_index}: должен быть объектом"]

    if not is_non_empty_str(item.get("productName")):
        errors.append(f"товар #{item_index}: отсутствует productName")

    if not is_positive_number(item.get("quantity")):
        errors.append(f"товар #{item_index}: quantity должен быть > 0")

    if not is_positive_number(item.get("initialPrice")):
        errors.append(f"товар #{item_index}: initialPrice должен быть > 0")

    return errors


def validate_order(order: dict, index: int) -> list[str]:
    errors: list[str] = []

    if not is_non_empty_str(order.get("firstName")):
        errors.append("отсутствует firstName")

    if not is_non_empty_str(order.get("lastName")):
        errors.append("отсутствует lastName")

    phone = order.get("phone")
    email = order.get("email")

    if not is_non_empty_str(phone) and not is_non_empty_str(email):
        errors.append("нужен хотя бы один контакт: phone или email")

    if is_non_empty_str(phone):
        normalized_phone = phone.strip()
        if not normalized_phone.startswith("+") or len(normalized_phone) < 8:
            errors.append("phone должен быть в международном формате, например +77001234567")

    if is_non_empty_str(email) and not EMAIL_RE.match(email.strip()):
        errors.append("email имеет некорректный формат")

    if "orderType" in order and not is_non_empty_str(order.get("orderType")):
        errors.append("orderType пустой")

    if "orderMethod" in order and not is_non_empty_str(order.get("orderMethod")):
        errors.append("orderMethod пустой")

    if "status" in order and not is_non_empty_str(order.get("status")):
        errors.append("status пустой")

    items = order.get("items")
    if not isinstance(items, list) or not items:
        errors.append("items должен быть непустым массивом")
    else:
        for item_index, item in enumerate(items, start=1):
            errors.extend(validate_item(item, index, item_index))

    delivery = order.get("delivery")
    if delivery is not None:
        if not isinstance(delivery, dict):
            errors.append("delivery должен быть объектом")
        else:
            address = delivery.get("address")
            if address is not None:
                if not isinstance(address, dict):
                    errors.append("delivery.address должен быть объектом")
                else:
                    if "city" in address and not is_non_empty_str(address.get("city")):
                        errors.append("delivery.address.city пустой")
                    if "text" in address and not is_non_empty_str(address.get("text")):
                        errors.append("delivery.address.text пустой")

    custom_fields = order.get("customFields")
    if custom_fields is not None and not isinstance(custom_fields, dict):
        errors.append("customFields должен быть объектом")

    return errors


def prepare_order(order: dict, index: int) -> dict:
    prepared = dict(order)
    prepared.setdefault("externalId", f"import-{index:04d}")
    return prepared


def print_local_validation_errors(invalid_orders: list[dict]) -> None:
    print_section("Локальные ошибки валидации")
    for invalid in invalid_orders:
        print(f"- Заказ #{invalid['index']} (externalId={invalid['externalId']}):")
        for error in invalid["errors"]:
            print(f"    • {error}")


def print_api_result(http_status: int, result: dict, sent_orders: list[dict]) -> None:
    print_section("Ответ RetailCRM")
    print(f"HTTP: {http_status}")
    print(f"success: {result.get('success')}")
    print(f"errorMsg: {result.get('errorMsg')}")

    uploaded_orders = result.get("uploadedOrders") or []
    failed_orders = result.get("failedOrders") or []
    errors = result.get("errors") or []

    print(f"Успешно загружено: {len(uploaded_orders)}")
    print(f"С ошибками: {len(failed_orders)}")

    if uploaded_orders:
        print("\nУспешные externalId:")
        for item in uploaded_orders:
            if isinstance(item, dict):
                print(f"  - {item.get('externalId') or item.get('id') or item}")
            else:
                print(f"  - {item}")

    if failed_orders:
        print("\nПроблемные заказы:")
        failed_external_ids: set[str] = set()

        for item in failed_orders:
            if isinstance(item, dict):
                external_id = item.get("externalId") or item.get("id") or "<unknown>"
                failed_external_ids.add(str(external_id))
                print(f"  - {external_id}")
            else:
                print(f"  - {item}")

        if errors:
            print("\nОшибки RetailCRM:")
            for err in errors:
                print(f"  • {err}")

        failed_payload = [
            order for order in sent_orders
            if str(order.get("externalId")) in failed_external_ids
        ]

        if failed_payload:
            with FAILED_ORDERS_DUMP.open("w", encoding="utf-8") as f:
                json.dump(failed_payload, f, ensure_ascii=False, indent=2)
            print(f"\nНевалидные/непринятые заказы сохранены в: {FAILED_ORDERS_DUMP.resolve()}")


def send_orders(orders: list[dict]) -> tuple[int, dict]:
    if not API_KEY:
        raise ValueError(
            "Не задан RETAILCRM_API_KEY. "
            "Пример:\n"
            "Windows PowerShell: $env:RETAILCRM_API_KEY='your_key'\n"
            "Linux/macOS: export RETAILCRM_API_KEY='your_key'"
        )

    payload = {
        "site": SITE,
        "orders": json.dumps(orders, ensure_ascii=False),
    }

    response = requests.post(
        f"{BASE_URL}/api/v5/orders/upload",
        headers={"X-API-KEY": API_KEY},
        data=payload,
        timeout=TIMEOUT,
    )

    try:
        result = response.json()
    except ValueError:
        result = {
            "success": False,
            "errorMsg": "Ответ не является JSON",
            "rawText": response.text,
        }

    return response.status_code, result


def main() -> None:
    print_section("Старт")
    print(f"BASE_URL: {BASE_URL}")
    print(f"SITE: {SITE}")
    print(f"ORDERS_FILE: {ORDERS_FILE.resolve()}")
    print(f"API_KEY: {mask_secret(API_KEY)}")
    print(f"TEST_MODE: {TEST_MODE}")

    orders = load_orders(ORDERS_FILE)

    prepared_orders: list[dict] = []
    invalid_orders: list[dict] = []

    for index, order in enumerate(orders, start=1):
        prepared = prepare_order(order, index)
        errors = validate_order(prepared, index)

        if errors:
            invalid_orders.append({
                "index": index,
                "externalId": prepared.get("externalId", f"import-{index:04d}"),
                "errors": errors,
                "order": prepared,
            })
        else:
            prepared_orders.append(prepared)

    print_section("Результат локальной проверки")
    print(f"Всего заказов в файле: {len(orders)}")
    print(f"Валидных локально: {len(prepared_orders)}")
    print(f"С локальными ошибками: {len(invalid_orders)}")

    if invalid_orders:
        print_local_validation_errors(invalid_orders)

        with Path("invalid_orders_local.json").open("w", encoding="utf-8") as f:
            json.dump(
                [x["order"] for x in invalid_orders],
                f,
                ensure_ascii=False,
                indent=2,
            )
        print("\nЛокально невалидные заказы сохранены в: invalid_orders_local.json")

        if not SKIP_INVALID_LOCAL:
            print("\nОтправка остановлена: сначала исправь локальные ошибки.")
            return

    if TEST_MODE:
        prepared_orders = prepared_orders[:TEST_LIMIT]
        print(f"\nТестовый режим: отправляем только {len(prepared_orders)} заказ(ов).")

    if not prepared_orders:
        print("\nНет заказов для отправки.")
        return

    try:
        http_status, result = send_orders(prepared_orders)
    except requests.RequestException as e:
        print_section("Сетевая ошибка")
        print(f"{type(e).__name__}: {e}")
        return

    print_api_result(http_status, result, prepared_orders)

    if not result.get("success") and "rawText" in result:
        print("\nСырой ответ сервера:")
        print(result["rawText"])


if __name__ == "__main__":
    main()