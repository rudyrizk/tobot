# #!/usr/bin/env python3
# import requests
# import logging

# # Set up logging
# logging.basicConfig(filename="model_trades.log", level=logging.INFO, format="%(asctime)s - %(message)s")

# # Function to fetch model data from nof1.ai
# def fetch_model_trades(model_id):
#     url = f"https://nof1.ai/api/models/{model_id}/trades"  # Replace with the actual endpoint
#     try:
#         response = requests.get(url, timeout=10)
#         response.raise_for_status()
#         trades = response.json()  # Assuming the API returns JSON data
#         return trades
#     except requests.RequestException as e:
#         logging.error(f"Error fetching model trades: {e}")
#         return []

# # Function to log and print trades
# def log_trades(trades):
#     for trade in trades:
#         symbol = trade.get("symbol")
#         action = trade.get("action")  # "BUY" or "SELL"
#         quantity = trade.get("quantity")
#         price = trade.get("price")

#         # Log the trade
#         logging.info(f"Model Trade - Symbol: {symbol}, Action: {action}, Quantity: {quantity}, Price: {price}")
#         print(f"Model Trade - Symbol: {symbol}, Action: {action}, Quantity: {quantity}, Price: {price}")

# # Example usage
# if __name__ == "__main__":
#     model_id = "qwen3-max_358"  # Replace with the actual model ID
#     trades = fetch_model_trades(model_id)
#     log_trades(trades)