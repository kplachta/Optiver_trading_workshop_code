# Optiver Trading Workshop Code

Trading strategies and helper utilities built during trading workshop with Optiver using the Optibook synchronous API.

## Overview
This repository contains educational examples of algorithmic trading strategies implemented against a simulated exchange. The focus is on understanding market mechanics, quoting logic, hedging, and inventory management rather than production-ready trading systems.

The code was written during 2 workshops and contains a few strategies. The market making strategies were consistently profitable (although there was still large room for improvement) while the dual_listing arbitrage was profitable during thinner trading and uneven when everyone ran their scripts.

## Contents
- **`dual_listings_arbitrage.py`**  
  Opportunistic arbitrage strategy between a stock and its dual listing using IOC orders and basic position management.

- **`market_making.py`**  
  Simple market-making strategy with:
  - Limit order quoting
  - Inventory-aware position limits
  - Hedging between dual listings
  - ETF fair-value estimation using futures
  - ETF–futures hedging logic

- **`README.md`**  
  Project documentation.

## Requirements
- Python 3.8+
- Optibook synchronous client (`optibook`)
- Standard Python libraries (`datetime`, `time`, `math`, `logging`)
