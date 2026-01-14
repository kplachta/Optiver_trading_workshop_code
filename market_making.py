import datetime as dt
import time
import random
import logging
import math
from optibook.synchronous_client import Exchange


exchange = Exchange()
exchange.connect()
time.sleep(0.5)

logging.getLogger('client').setLevel('ERROR')

# Support functions
def calculate_current_time_to_date(expiry_date) -> float:
    """
    Returns the current total time remaining until some future datetime. The remaining time is provided in fractions of
    years.

    Example usage:
        import datetime as dt

        expiry_date = dt.datetime(2022, 12, 31, 12, 0, 0)
        tte = calculate_current_time_to_date(expiry_date)

    Arguments:
        expiry_date: A dt.datetime object representing the datetime of expiry.
    """
    now = dt.datetime.now()
    return calculate_time_to_date(expiry_date, now)


def calculate_time_to_date(expiry_date, current_time) -> float:
    """
    Returns the total time remaining until some future datetime. The remaining time is provided in fractions of years.

    Example usage:
        import datetime as dt

        expiry_date = dt.datetime(2022, 12, 31, 12, 0, 0)
        now = dt.datetime.now()
        tte = calculate_time_to_date(expiry_date, now)

    Arguments:
        expiry_date: A dt.datetime object representing the datetime of expiry.
        current_time: A dt.datetime object representing the current datetime to assume.
    """

    return (expiry_date - current_time) / dt.timedelta(days=1) / 365

def trade_would_breach_position_limit(instrument_id, volume, side, position_limit=100):
    positions = exchange.get_positions()
    position_instrument = positions[instrument_id]

    if side == 'bid':
        return position_instrument + volume > position_limit
    elif side == 'ask':
        return position_instrument - volume < -position_limit
    else:
        raise Exception(f'''Invalid side provided: {side}, expecting 'bid' or 'ask'.''')

def print_positions_and_pnl(always_display=None):
    positions = exchange.get_positions()
    print('Positions:')
    for instrument_id in positions:
        if not always_display or instrument_id in always_display or positions[instrument_id] != 0:
            print(f'  {instrument_id:20s}: {positions[instrument_id]:4.0f}')

    pnl = exchange.get_pnl()
    if pnl:
        print(f'\nPnL: {pnl:.2f}')

def get_data(mm_stock, hedge_stock):
    mm_book = exchange.get_last_price_book(mm_stock)
    hedge_book = exchange.get_last_price_book(hedge_stock)
    return(mm_book, hedge_book)

def get_data_etf(etf, future):
    etf_book = exchange.get_last_price_book(etf)
    future_book = exchange.get_last_price_book(future)
    return(etf_book, future_book)

def get_index_price():
    book = exchange.get_last_price_book('OB5X_202409_F')
    #book_ETF = exchange.get_last_price_book('OB5X_ETF')

    best_bid = book.bids[0]
    best_ask = book.asks[0]

    #bb_etf = book_ETF.bids[0]
    #ba_etf = book_ETF.asks[0]

    Future = (best_bid.price + best_ask.price) / 2
    #ETF = (bb_etf.price + ba_etf.price) / 2

    expiry_date = dt.datetime.strptime('2024-09-20 12:00:00', '%Y-%m-%d %H:%M:%S')
    time = calculate_current_time_to_date(expiry_date)

    Index = Future * math.exp(-0.03*time)
    ETF_basket = Index / 3.6

    Index_bid = best_bid.price * math.exp(-0.03*time) / 3.6
    Index_ask = best_ask.price * math.exp(-0.03*time) / 3.6

    return(Index_bid, Index_ask, book)

def market_making(mm_stock, mm_book, hedge_book, min_spread=0.2):
    
    mm_bids = mm_book.bids #PRICE TO BUY
    mm_asks = mm_book.asks #PRICE TO SELL
    hedge_bids = hedge_book.bids
    hedge_asks = hedge_book.asks
    
    mm_midpoint = (mm_bids[0].price + mm_asks[0].price) / 2

    bid_price = min(mm_midpoint - min_spread/2, hedge_asks[0].price - 0.05)
    ask_price = max(mm_midpoint + min_spread/2, hedge_bids[0].price + 0.05)

    if bid_price == ask_price:
        bid_price = bid_price - 0.05
        ask_price = ask_price + 0.05

    vol_trade = 40
    if trade_would_breach_position_limit(mm_stock, vol_trade, "bid") != True:
        exchange.insert_order(mm_stock, price= bid_price, volume = vol_trade, side='bid', order_type='limit')
    if trade_would_breach_position_limit(mm_stock, vol_trade, "ask") != True:
        exchange.insert_order(mm_stock, price= ask_price, volume = vol_trade, side='ask', order_type='limit')

    if trade_would_breach_position_limit(mm_stock, 1.5*vol_trade, "bid") != True:
        exchange.insert_order(mm_stock, price= bid_price-0.1, volume = 0.5*vol_trade, side='bid', order_type='limit')
    if trade_would_breach_position_limit(mm_stock, 1.5*vol_trade, "ask") != True:
        exchange.insert_order(mm_stock, price= ask_price+0.1, volume = 0.5*vol_trade, side='ask', order_type='limit')


def hedging(mm_stock, hedge_stock, mm_book, hedge_book):
    positions = exchange.get_positions()
    mm_pos = positions[mm_stock]
    hedge_pos = positions[hedge_stock]

    bids1 = mm_book.bids #PRICE TO BUY
    asks1 = mm_book.asks #PRICE TO SELL
    bids2 = hedge_book.bids
    asks2 = hedge_book.asks

            
    if mm_pos > 0 and hedge_pos >0: # If delta is doubled
            hedge_vol = mm_pos + hedge_pos
            exchange.insert_order(hedge_stock, price=bids2[0].price, volume = hedge_vol, side='ask', order_type='ioc')
            # Sell hedge stock to even out the position
    elif mm_pos >= 0 and hedge_pos <=0: 
        if mm_pos > abs(hedge_pos): # If stock is underhedged
            hedge_vol = mm_pos - abs(hedge_pos)
            exchange.insert_order(hedge_stock, price=bids2[0].price, volume = hedge_vol, side='ask', order_type='ioc')
            # Sell more of hedge stock
        elif mm_pos < abs(hedge_pos): # If stock is overhedged
            hedge_vol = abs(hedge_pos) - mm_pos
            exchange.insert_order(hedge_stock, price=asks2[0].price, volume = hedge_vol, side='bid', order_type='ioc')
            # Buy hedge stock to even out position
    elif mm_pos <= 0 and hedge_pos >=0:
        if abs(mm_pos) > hedge_pos: # If stock is underhedged
            hedge_vol = abs(mm_pos) - hedge_pos
            exchange.insert_order(hedge_stock, price=asks2[0].price, volume = hedge_vol, side='bid', order_type='ioc')
            # Buy more of hedge stock
        elif abs(mm_pos) < hedge_pos: # If stock is overhedged
            volume = hedge_pos - abs(mm_pos)
            exchange.insert_order(hedge_stock, price=bids2[0].price, volume = volume, side='ask', order_type='ioc')
            # Sell excess hedge stock
    elif mm_pos < 0 and hedge_pos < 0: # If negative delta is doubled
        hedge_vol = abs(mm_pos) + abs(hedge_pos)
        exchange.insert_order(hedge_stock, price=asks2[0].price, volume = hedge_vol, side='bid', order_type='ioc')
        # Buy hedge stock


def market_making_ETF(etf, etf_book, etf_bid, etf_ask, hedge_book, min_spread=0.2):
    exchange.delete_orders(etf)

    etf_bb = etf_book.bids[0]
    etf_ba = etf_book.asks[0]

    bid_price = max(etf_bb.price + 0.05, etf_bid - min_spread/2)
    ask_price = max(etf_ba.price + 0.05, etf_ask + min_spread/2)


    vol_trade = 40
    if trade_would_breach_position_limit(etf, vol_trade, "bid") != True:
        exchange.insert_order(etf, price= bid_price, volume = vol_trade, side='bid', order_type='limit')
    if trade_would_breach_position_limit(etf, vol_trade, "ask") != True:
        exchange.insert_order(etf, price= ask_price, volume = vol_trade, side='ask', order_type='limit')

    if trade_would_breach_position_limit(etf, 1.5*vol_trade, "bid") != True:
        exchange.insert_order(etf, price= bid_price-0.1, volume = 0.5*vol_trade, side='bid', order_type='limit')
    if trade_would_breach_position_limit(etf, 1.5*vol_trade, "ask") != True:
        exchange.insert_order(etf, price= ask_price+0.1, volume = 0.5*vol_trade, side='ask', order_type='limit')

def hedging_ETF(etf, future, hedge_book):
    positions = exchange.get_positions()
    mm_pos = round(positions[etf] / 3.6)
    hedge_pos = positions[future]

    bids2 = hedge_book.bids
    asks2 = hedge_book.asks
            
    if mm_pos > 0 and hedge_pos >0: # If delta is doubled
            hedge_vol = mm_pos + hedge_pos
            exchange.insert_order(future, price=bids2[0].price, volume = hedge_vol, side='ask', order_type='ioc')
            # Sell hedge stock to even out the position
    elif mm_pos >= 0 and hedge_pos <=0: 
        if mm_pos > abs(hedge_pos): # If stock is underhedged
            hedge_vol = mm_pos - abs(hedge_pos)
            exchange.insert_order(future, price=bids2[0].price, volume = hedge_vol, side='ask', order_type='ioc')
            # Sell more of hedge stock
        elif mm_pos < abs(hedge_pos): # If stock is overhedged
            hedge_vol = abs(hedge_pos) - mm_pos
            exchange.insert_order(future, price=asks2[0].price, volume = hedge_vol, side='bid', order_type='ioc')
            # Buy hedge stock to even out position
    elif mm_pos <= 0 and hedge_pos >=0:
        if abs(mm_pos) > hedge_pos: # If stock is underhedged
            hedge_vol = abs(mm_pos) - hedge_pos
            exchange.insert_order(future, price=asks2[0].price, volume = hedge_vol, side='bid', order_type='ioc')
            # Buy more of hedge stock
        elif abs(mm_pos) < hedge_pos: # If stock is overhedged
            volume = hedge_pos - abs(mm_pos)
            exchange.insert_order(future, price=bids2[0].price, volume = volume, side='ask', order_type='ioc')
            # Sell excess hedge stock
    elif mm_pos < 0 and hedge_pos < 0: # If negative delta is doubled
        hedge_vol = abs(mm_pos) + abs(hedge_pos)
        exchange.insert_order(future, price=asks2[0].price, volume = hedge_vol, side='bid', order_type='ioc')
        # Buy hedge stock


STOCK_A_ID = 'SAN'
STOCK_B_ID = 'SAN_DUAL'
total_pnl = 0

while True:
    print(f'')
    print(f'-----------------------------------------------------------------')
    print(f'TRADE LOOP ITERATION ENTERED AT {str(dt.datetime.now()):18s} UTC.')
    print(f'-----------------------------------------------------------------')

    print_positions_and_pnl(always_display=[STOCK_A_ID, STOCK_B_ID])
    print(f'')

    exchange.delete_orders(STOCK_A_ID)
    exchange.delete_orders(STOCK_B_ID)
    exchange.delete_orders("NVDA")
    exchange.delete_orders("NVDA_DUAL")

    data = get_data(STOCK_B_ID, STOCK_A_ID)
    data2 = get_data("NVDA_DUAL", "NVDA")
    try:
        market_making(STOCK_B_ID, data[0], data[1], min_spread=0.4)
    except:
        print('Exception MM SAN')
    try:
        market_making("NVDA_DUAL", data2[0], data2[1], min_spread=0.4)
    except:
        print('Exception MM NVDA')

    data_etf = get_data_etf("OB5X_ETF", "OB5X_202409_F")
    try:
        index = get_index_price()
    except:
        'Exception get index price'
    try:
        market_making_ETF("OB5X_ETF", data[0], index[0], index[1], index[2], 0.2)
    except:
        print('Exception ETF') 

    time.sleep(2.5)

    hedging(STOCK_B_ID, STOCK_A_ID, data[0], data[1])
    hedging("NVDA_DUAL", "NVDA", data2[0], data2[1])
    hedging_ETF("OB5X_ETF", "OB5X_202409_F", data_etf[1])


    print(f'\nSleeping for 2.5 seconds.')
    time.sleep(2.5)
