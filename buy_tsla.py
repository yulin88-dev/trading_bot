from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
import os

# Load from environment variables, NOT hardcoded
API_KEY = os.environ['ALPACA_API_KEY']
SECRET_KEY = os.environ['ALPACA_SECRET_KEY']

client = TradingClient(API_KEY, SECRET_KEY, paper=True)

# Market order, Time-in-Force = OPG means "at market open"
order = MarketOrderRequest(
    symbol="TSLA",
    qty=5,
    side=OrderSide.BUY,
    time_in_force=TimeInForce.OPG
)

result = client.submit_order(order)
print(f"Order submitted: {result.id}, status: {result.status}")