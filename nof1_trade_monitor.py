import os
import requests
from datetime import datetime, timedelta, timezone

NOF1_URL = "https://nof1.ai/api/trades"

def send_telegram_message(bot_token, chat_id, message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        print(f"✅ Telegram notification sent: {message}")
    except Exception as e:
        print(f"❌ Telegram send error: {e}")

def fetch_trades():
    headers = {
        "accept": "application/json",
        "user-agent": "Mozilla/5.0"
    }
    response = requests.get(NOF1_URL, headers=headers)
    response.raise_for_status()
    return response.json().get("trades", [])

def get_recent_trades(trades, model_id, within_minutes=60):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=within_minutes)
    recent = []

    for trade in trades:
        if trade.get("model_id") != model_id:
            continue
        trade_time_str = trade.get("exit_human_time") or trade.get("entry_human_time")
        try:
            trade_time = datetime.strptime(trade_time_str, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if trade_time > cutoff:
            recent.append(trade)
    # Sort by exit_time descending
    return sorted(recent, key=lambda t: t.get("exit_time", 0), reverse=True)

def main():
    bot_token = os.getenv("TG_API_KEY")
    chat_id = os.getenv("TG_CHAT_ID")
    model_id = os.getenv("NOF1_MODEL_ID", "gpt-5")
    minutes = int(os.getenv("TRADE_WINDOW_MINUTES", "2880"))

    print(f"🔍 Checking for {model_id} trades within the last {minutes} minutes...")

    try:
        trades = fetch_trades()
    except Exception as e:
        print(f"❌ Failed to fetch trades: {e}")
        return

    recent_trades = get_recent_trades(trades, model_id, within_minutes=minutes)

    if not recent_trades:
        print("No new trades in the past period.")
        return

    print(f"✅ Found {len(recent_trades)} trade(s) in the past {minutes} minutes.")
    message_lines = [f"<b>Recent {model_id} Trades (last {minutes} min)</b>"]

    for t in recent_trades[:3]:
        message_lines.append(
            f"• <b>{t['symbol']}</b> {t['trade_type']} at {t['entry_price']} → {t['exit_price']} "
            f"PNL: {t['realized_net_pnl']:.2f}$ ({t['exit_human_time']})"
        )

    message = "\n".join(message_lines)
    send_telegram_message(bot_token, chat_id, message)

if __name__ == "__main__":
    main()
