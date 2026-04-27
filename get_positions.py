from alpaca.trading.client import TradingClient
import os

API_KEY = os.environ['ALPACA_API_KEY']
SECRET_KEY = os.environ['ALPACA_SECRET_KEY']

client = TradingClient(API_KEY, SECRET_KEY, paper=True)

positions = client.get_all_positions()

if not positions:
    print("No open positions.")
else:
    print(f"{'Symbol':<10} {'Qty':<10} {'Avg Entry':<14} {'Current Price':<16} {'P&L':<12} {'P&L %'}")
    print("-" * 70)
    for p in positions:
        print(f"{p.symbol:<10} {p.qty:<10} {float(p.avg_entry_price):<14.2f} {float(p.current_price):<16.2f} {float(p.unrealized_pl):<12.2f} {float(p.unrealized_plpc) * 100:.2f}%")
