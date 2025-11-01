#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from binance.spot import Spot
from binance.error import ClientError
import time

# Load environment variables
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

# For testnet:
client = Spot(api_key=API_KEY, api_secret=API_SECRET, base_url="https://testnet.binance.vision")

# For live trading:
# client = Spot(key=API_KEY, secret=API_SECRET)

def check_balance(asset="USDT"):
    """Check account balance for a specific asset."""
    account = client.account()
    for balance in account['balances']:
        if balance['asset'] == asset:
            return float(balance['free'])
    return 0.0

def place_market_order(symbol, side, quantity):
    """Place a simple market order."""
    try:
        print(f"Placing {side} {quantity} {symbol}...")
        order = client.new_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=quantity
        )
        print("Order placed:", order)
        return order
    except ClientError as e:
        print(f"Error placing order: {e.error_message}")
        return None

def get_order_status(symbol, order_id):
    """Check order status."""
    try:
        order = client.get_order(symbol=symbol, orderId=order_id)
        print("Order status:", order)
        return order
    except ClientError as e:
        print(f"Error getting order status: {e.error_message}")

def cancel_order(symbol, order_id):
    """Cancel an existing order."""
    try:
        result = client.cancel_order(symbol=symbol, orderId=order_id)
        print("Order cancelled:", result)
        return result
    except ClientError as e:
        print(f"Error cancelling order: {e.error_message}")

def main():
    symbol = "BTCUSDT"
    side = "BUY"
    quantity = 0.0001

    print(f"Free USDT balance: {check_balance('USDT')}")

    order = place_market_order(symbol, side, quantity)
    if not order:
        return

    order_id = order["orderId"]
    time.sleep(2)
    get_order_status(symbol, order_id)

    # Optional: cancel order (for limit or open ones)
    # cancel_order(symbol, order_id)

    print(f"Free BTC balance: {check_balance('BTC')}")
    print(f"Free USDT balance: {check_balance('USDT')}")

if __name__ == "__main__":
    main()
