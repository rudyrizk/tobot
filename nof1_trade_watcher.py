# #!/usr/bin/env python3
# """
# nof1_trade_watcher.py
# Monitor and log trades for a designated Nof1 AI model/agent.

# Usage:
#     python nof1_trade_watcher.py --agent deepseek-chat-v3.1 --interval 30

# Outputs:
#   - trades.csv : appended CSV of observed trades
#   - trades.db  : SQLite DB with `trades` table (id TEXT PRIMARY KEY)
# """

# import argparse
# import csv
# import json
# import os
# import sqlite3
# import time
# from datetime import datetime
# from typing import List, Dict, Optional

# import requests
# from bs4 import BeautifulSoup

# # ------------------------------
# # Configuration
# # ------------------------------
# DEFAULT_INTERVAL = 30  # seconds
# CSV_FILE = "trades.csv"
# DB_FILE = "trades.db"
# USER_AGENT = "nof1-trade-watcher/1.0 (+https://nof1.ai/)"

# # Candidate endpoints (the script will try them in order).
# # These are heuristics — some repos and dashboards poll site endpoints or embedded JSON.
# CANDIDATE_API_URLS = [
#     "https://nof1.ai/api/agents/{agent}/trades",          # common REST pattern
#     "https://nof1.ai/api/models/{agent}/trades",
#     "https://nof1.ai/agents/{agent}/trades",
#     "https://nof1.ai/models/{agent}/trades",
#     "https://nof1.ai/agent/{agent}/trades",
#     "https://nof1.ai/model/{agent}/trades",
# ]

# # ------------------------------
# # Helpers: persistence
# # ------------------------------
# def init_db(path: str = DB_FILE):
#     conn = sqlite3.connect(path)
#     cur = conn.cursor()
#     cur.execute("""
#         CREATE TABLE IF NOT EXISTS trades (
#             id TEXT PRIMARY KEY,
#             agent TEXT,
#             pair TEXT,
#             side TEXT,
#             qty REAL,
#             price REAL,
#             timestamp INTEGER,
#             raw JSON
#         )
#     """)
#     conn.commit()
#     return conn

# def trade_exists(conn: sqlite3.Connection, trade_id: str) -> bool:
#     cur = conn.cursor()
#     cur.execute("SELECT 1 FROM trades WHERE id = ?", (trade_id,))
#     return cur.fetchone() is not None

# def save_trade(conn: sqlite3.Connection, t: Dict, agent: str):
#     cur = conn.cursor()
#     cur.execute(
#         "INSERT OR IGNORE INTO trades (id, agent, pair, side, qty, price, timestamp, raw) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
#         (
#             t["id"],
#             agent,
#             t.get("pair"),
#             t.get("side"),
#             t.get("qty"),
#             t.get("price"),
#             int(t.get("timestamp", int(time.time()))),
#             json.dumps(t, ensure_ascii=False)
#         )
#     )
#     conn.commit()

# def append_csv_row(path: str, row: Dict):
#     file_exists = os.path.exists(path)
#     with open(path, "a", newline="", encoding="utf-8") as f:
#         writer = csv.DictWriter(f, fieldnames=list(row.keys()))
#         if not file_exists:
#             writer.writeheader()
#         writer.writerow(row)

# # ------------------------------
# # Data extraction heuristics
# # ------------------------------
# def try_api_poll(agent: str, session: requests.Session) -> Optional[List[Dict]]:
#     """Try candidate JSON endpoints. Return list of trade dicts if successful."""
#     for template in CANDIDATE_API_URLS:
#         url = template.format(agent=agent)
#         try:
#             r = session.get(url, timeout=10)
#             if r.status_code != 200:
#                 continue
#             # Try parse JSON
#             data = r.json()
#             # Heuristic: find list of trades inside JSON
#             if isinstance(data, list):
#                 return normalize_trades(data)
#             if isinstance(data, dict):
#                 # common keys: 'trades', 'data', 'items', 'completedTrades'
#                 for k in ("trades", "data", "items", "completedTrades", "completed_trades"):
#                     if k in data and isinstance(data[k], list):
#                         return normalize_trades(data[k])
#                 # fallback: maybe the dict itself represents a trade or single item
#                 if all(k in data for k in ("id", "price")):
#                     return normalize_trades([data])
#         except ValueError:
#             # not JSON
#             continue
#         except requests.RequestException:
#             continue
#     return None

# def parse_embedded_json_from_html(html_text: str) -> Optional[List[Dict]]:
#     """Look for <script> tags containing JSON (e.g., window.__INITIAL_STATE__ or JSON blobs)."""
#     soup = BeautifulSoup(html_text, "html.parser")
#     scripts = soup.find_all("script")
#     for s in scripts:
#         text = s.string
#         if not text:
#             continue
#         # common patterns
#         if "window.__INITIAL_STATE__" in text or "window.__DATA__" in text or "initialState" in text:
#             # find the first JSON object inside text
#             start = text.find("{")
#             try:
#                 obj = json.loads(text[start:])
#             except Exception:
#                 # sometimes there's other JS after JSON; try to extract braces
#                 try:
#                     # crude: find matching braces substring
#                     brace_level = 0
#                     start_idx = None
#                     for i, ch in enumerate(text):
#                         if ch == "{":
#                             if start_idx is None:
#                                 start_idx = i
#                             brace_level += 1
#                         elif ch == "}":
#                             brace_level -= 1
#                             if brace_level == 0 and start_idx is not None:
#                                 candidate = text[start_idx:i+1]
#                                 obj = json.loads(candidate)
#                                 # if parse succeeded, proceed
#                                 if obj:
#                                     # try find trades in nested structure
#                                     for k in ("trades", "completedTrades", "agents", "models"):
#                                         if k in obj and isinstance(obj[k], list):
#                                             return normalize_trades(obj[k])
#                 except Exception:
#                     continue
#     return None

# def scrape_model_page_for_trades(agent: str, session: requests.Session) -> Optional[List[Dict]]:
#     """Fetch the model/agent page and attempt to extract trades from HTML."""
#     # some likely pages
#     candidates = [
#         f"https://nof1.ai/models/{agent}",
#         f"https://nof1.ai/agents/{agent}",
#         f"https://nof1.ai/{agent}",
#     ]
#     for url in candidates:
#         try:
#             r = session.get(url, timeout=10)
#             if r.status_code != 200:
#                 continue
#             html = r.text
#             # Try embedded JSON first
#             trades = parse_embedded_json_from_html(html)
#             if trades:
#                 return trades
#             # Otherwise look for HTML tables / rows labeled 'Completed Trades' or 'trades'
#             soup = BeautifulSoup(html, "html.parser")
#             # Common: table rows with trade info
#             # Look for tables that contain headers like "Pair", "Side", "Price", "Qty", "Time"
#             tables = soup.find_all("table")
#             for table in tables:
#                 headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
#                 if any(h in headers for h in ("pair", "price", "side", "time", "qty", "quantity")):
#                     rows = []
#                     for tr in table.find_all("tr"):
#                         cols = [td.get_text(strip=True) for td in tr.find_all("td")]
#                         if not cols:
#                             continue
#                         # naive map by headers
#                         d = {}
#                         for i, h in enumerate(headers):
#                             if i < len(cols):
#                                 d[h] = cols[i]
#                         # Map to normalized trade format later
#                         rows.append(d)
#                     if rows:
#                         return normalize_trades(rows)
#             # If nothing found, continue to next candidate
#         except requests.RequestException:
#             continue
#     return None

# def normalize_trades(raw_list: List[Dict]) -> List[Dict]:
#     """Normalize trade dicts to a minimal canonical form:
#        id, pair, side, qty, price, timestamp
#     """
#     res = []
#     for item in raw_list:
#         # item may be nested or keys vary
#         # Try common keys
#         tid = item.get("id") or item.get("trade_id") or item.get("order_id") or item.get("oid")
#         # fallback: build id from timestamp+pair+side
#         if not tid:
#             # try timestamp
#             ts = item.get("timestamp") or item.get("time") or item.get("ts")
#             pair = item.get("pair") or item.get("symbol") or item.get("instrument")
#             side = item.get("side") or item.get("direction")
#             tid = f"{pair}-{side}-{ts}" if pair and side and ts else json.dumps(item, sort_keys=True)[:60]
#         pair = item.get("pair") or item.get("symbol") or item.get("instrument") or item.get("coin")
#         side = item.get("side") or item.get("direction") or item.get("action")
#         qty = _coerce_number(item.get("qty") or item.get("quantity") or item.get("size") or item.get("amount"))
#         price = _coerce_number(item.get("price") or item.get("px") or item.get("execution_price") or item.get("avg_price"))
#         ts = item.get("timestamp") or item.get("time") or item.get("ts") or item.get("created_at")
#         # normalize timestamp to integer epoch seconds if possible
#         timestamp = _coerce_timestamp(ts)
#         res.append({
#             "id": str(tid),
#             "pair": pair,
#             "side": side,
#             "qty": qty,
#             "price": price,
#             "timestamp": timestamp or int(time.time()),
#             "raw": item
#         })
#     return res

# def _coerce_number(x):
#     if x is None:
#         return None
#     try:
#         return float(x)
#     except Exception:
#         # strip commas/currency
#         try:
#             s = str(x).replace(",", "").replace("$", "")
#             return float(s)
#         except Exception:
#             return None

# def _coerce_timestamp(ts):
#     if ts is None:
#         return None
#     # Accept epoch (s or ms), or ISO string
#     try:
#         t = int(ts)
#         # Heuristic: if > 1e12 it's ms
#         if t > 1_000_000_000_000:
#             return int(t // 1000)
#         return t
#     except Exception:
#         # try parse ISO
#         try:
#             dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
#             return int(dt.timestamp())
#         except Exception:
#             return None

# # ------------------------------
# # Main loop
# # ------------------------------
# def watch_agent(agent: str, interval: int = DEFAULT_INTERVAL):
#     session = requests.Session()
#     session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, text/html"})
#     conn = init_db(DB_FILE)
#     print(f"[{datetime.utcnow().isoformat()}Z] Starting watcher for agent='{agent}' (interval={interval}s). CSV={CSV_FILE}, DB={DB_FILE}")

#     # Prime: try to poll once and detect approach
#     approach = None  # "api" or "scrape"
#     last_seen_ids = set()

#     while True:
#         trades = None
#         # Strategy A: API candidates
#         trades = try_api_poll(agent, session)
#         if trades:
#             approach = "api"
#         else:
#             # Strategy B: scrape model page
#             trades = scrape_model_page_for_trades(agent, session)
#             if trades:
#                 approach = "scrape"

#         if trades is None:
#             print(f"[{datetime.utcnow().isoformat()}] No trade data found for agent '{agent}' (approach={approach}). Will retry in {interval}s.")
#             time.sleep(interval)
#             continue

#         # Process trades: sort by timestamp (oldest first)
#         trades_sorted = sorted(trades, key=lambda t: t.get("timestamp", time.time()))
#         new_count = 0
#         for t in trades_sorted:
#             tid = t["id"]
#             if trade_exists(conn, tid):
#                 continue
#             # save
#             save_trade(conn, t, agent)
#             # append to CSV
#             csv_row = {
#                 "id": t["id"],
#                 "agent": agent,
#                 "pair": t.get("pair"),
#                 "side": t.get("side"),
#                 "qty": t.get("qty"),
#                 "price": t.get("price"),
#                 "timestamp": t.get("timestamp"),
#                 "datetime_utc": datetime.utcfromtimestamp(t.get("timestamp", int(time.time()))).isoformat() + "Z"
#             }
#             append_csv_row(CSV_FILE, csv_row)
#             print(f"[{datetime.utcnow().isoformat()}] NEW TRADE: {csv_row}")
#             new_count += 1

#         if new_count == 0:
#             print(f"[{datetime.utcnow().isoformat()}] No new trades. ({len(trades_sorted)} total discovered)")

#         time.sleep(interval)

# # ------------------------------
# # CLI
# # ------------------------------
# def main():
#     p = argparse.ArgumentParser(description="Nof1 agent trade watcher")
#     p.add_argument("--agent", default="qwen3-max_358", help="Agent name (e.g. deepseek-chat-v3.1 or gpt-5)")

#     p.add_argument("--interval", type=int, default=DEFAULT_INTERVAL, help=f"Poll interval in seconds (default {DEFAULT_INTERVAL})")
#     args = p.parse_args()
#     watch_agent(args.agent, args.interval)

# if __name__ == "__main__":
#     main()
