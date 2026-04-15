# RetailCRM Integration Demo

A small demo project that shows how to:

1. upload test orders to RetailCRM from a JSON file
2. sync orders from RetailCRM to Supabase
3. build a dashboard on top of Supabase data
4. send Telegram alerts for large orders

## Stack

- **RetailCRM** — demo CRM account
- **Supabase** — database and storage
- **Vercel** — dashboard deployment
- **Telegram Bot** — order notifications

---

## Project Steps

### Step 1 — Create Accounts
Create free accounts for:

- RetailCRM demo account
- Supabase project
- Vercel account
- Telegram bot via BotFather

### Step 2 — Upload Orders to RetailCRM
The repository contains `mock_orders.json` with **50 test orders**.

Upload them to RetailCRM via API using:

- `upload_orders_to_retailcrm.py`

### Step 3 — RetailCRM → Supabase
Run the sync script that fetches orders from RetailCRM API and stores them in Supabase:

- `sync_retailcrm_to_supabase.py`

### Step 4 — Dashboard
Build a web page with order charts using data from Supabase and deploy it to Vercel.

### Step 5 — Telegram Bot
Run a simple Telegram bot that sends an alert whenever a new RetailCRM order is greater than **50,000 ₸**.

---

## Environment Variables

Replace all placeholder values with your own credentials.

### RetailCRM Upload JSON

#### Linux/macOS
```bash
export RETAILCRM_API_KEY="<your_retailcrm_api_key>"
export RETAILCRM_BASE_URL="https://<your-account>.retailcrm.ru"
export RETAILCRM_SITE="<your_site_code>"
python upload_orders_to_retailcrm.py
```

#### Windows Powershell
```powershell
$env:RETAILCRM_API_KEY="<your_retailcrm_api_key>"
$env:RETAILCRM_BASE_URL="https://<your-account>.retailcrm.ru"
$env:RETAILCRM_SITE="<your_site_code>"
python upload_orders_to_retailcrm.py
```

#### Windows Command Line
```commandline
set RETAILCRM_API_KEY=<your_retailcrm_api_key>
set RETAILCRM_BASE_URL=https://<your-account>.retailcrm.ru
set RETAILCRM_SITE=<your_site_code>
python upload_orders_to_retailcrm.py
```

---

## RetailCRM → Supabase

### Windows Command Prompt
```bat
set SUPABASE_URL=https://<your-project-ref>.supabase.co
set SUPABASE_KEY=<your_supabase_secret_key>

set SYNC_MODE=full
python sync_retailcrm_to_supabase.py

set SYNC_MODE=history
python sync_retailcrm_to_supabase.py
```

- full runs the initial full synchronization.
- history runs incremental sync based on RetailCRM history.

---

## Telegram Bot

### Windows Command Prompt
```bat
set RETAILCRM_API_KEY=<your_retailcrm_api_key>
set RETAILCRM_BASE_URL=https://<your-account>.retailcrm.ru
set RETAILCRM_SITE=<your_site_code>
set TELEGRAM_BOT_TOKEN=<your_telegram_bot_token>
set TELEGRAM_CHAT_ID=<your_telegram_chat_id>
python retailcrm_alert_bot.py
```

---

## Files

- mock_orders.json — 50 test orders
- upload_orders_to_retailcrm.py — uploads test orders to RetailCRM
- sync_retailcrm_to_supabase.py — syncs orders from RetailCRM to Supabase
- retailcrm_alert_bot.py — sends Telegram alerts for large orders

---

## Goal

This project demonstrates a simple end-to-end pipeline:

<b>RetailCRM → Supabase → Dashboard + Telegram alerts</b>
