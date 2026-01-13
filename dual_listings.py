import datetime as dt
import time
import random
import logging

from optibook.synchronous_client import Exchange

exchange = Exchange()
exchange.connect()
time.sleep(0.5)

logging.getLogger('client').setLevel('ERROR')

# Support functions
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

def max_position(stock1):
    # insert a function that would return max possible volumes that we can trade either way
    positions = exchange.get_positions()
    max1_buy = 99 - positions[stock1]
    max1_sell = 198 - max1_buy
    return (max1_buy, max1_sell)

def clear_mismatch(stock1, stock2):
    positions = exchange.get_positions()
    pos1 = positions[stock1]
    pos2 = positions[stock2]
    abspos1 = abs(pos1)
    abspos2 = abs(pos2)

    book1 = exchange.get_last_price_book(stock1)
    book2 = exchange.get_last_price_book(stock2)

    bids1 = book1.bids #PRICE TO BUY
    asks1 = book1.asks #PRICE TO SELL
    bids2 = book2.bids
    asks2 = book2.asks

    if pos1 > 0 and pos2 >0:
        exchange.insert_order(stock1, price=bids1[0].price, volume = abspos1, side='ask', order_type='ioc')
        exchange.insert_order(stock2, price=bids2[0].price, volume = abspos2, side='ask', order_type='ioc')
        # sell both positions
    elif pos1 >= 0 and pos2 <=0:
        if pos1 > abs(pos2):
            volume = pos1 - abs(pos2)
            print(volume)
            exchange.insert_order(stock1, price=bids1[0].price, volume = volume, side='ask', order_type='ioc')
            #sell s1
        elif pos1 < abs(pos2):
            volume = abs(pos2) - pos1
            print(volume)
            exchange.insert_order(stock2, price=asks2[0].price, volume = volume, side='bid', order_type='ioc')
            #buy pos2
    elif pos1 <= 0 and pos2 >=0:
        if abs(pos1) > pos2:
            volume = abs(pos1) - pos2
            print(volume)
            exchange.insert_order(stock2, price=asks2[0].price, volume = volume, side='bid', order_type='ioc')
            #buy pos2
        elif abs(pos1) < pos2:
            volume = pos2 - abs(pos1)
            print(volume)
            exchange.insert_order(stock2, price=bids2[0].price, volume = volume, side='ask', order_type='ioc')
            #sell pos2
    elif pos1 < 0 and pos2 <0:
        exchange.insert_order(stock1, price=asks1[0].price, volume = abspos1, side='bid', order_type='ioc')
        exchange.insert_order(stock2, price=asks2[0].price, volume = abspos2, side='bid', order_type='ioc')
        #close both shorts (buy)

def clear_book(stock1, stock2, max_spread=0.02):
    global total_pnl
    book1 = exchange.get_last_price_book(stock1)
    book2 = exchange.get_last_price_book(stock2)
    
    bids1 = book1.bids
    asks1 = book1.asks
    
    bids2 = book2.bids
    asks2 = book2.asks

    positions = exchange.get_positions()
    pos1 = positions[stock1]
    pos2 = positions[stock2]

    if pos1 == -pos2:
        if pos1 > 0:
            if asks2[0].price - bids1[0].price <= max_spread:
                volume = min(bids1[0].volume, asks2[0].volume, abs(pos1))
                exchange.insert_order(stock1, price=bids1[0].price, volume = volume, side='ask', order_type='ioc') #sell SAN
                exchange.insert_order(stock2, price=asks2[0].price, volume = volume, side='bid', order_type='ioc') #buy SAN_dual
                Pnl = volume*(bids1[0].price - asks2[0].price)
                total_pnl += Pnl
                print('Cleared shares: ' + str(volume) + ' at: ' + str(Pnl) + ' the strat pnl is now: ' + str(total_pnl))
        elif pos2 > 0:
            if asks1[0].price - bids2[0].price <= max_spread:
                volume = min(bids2[0].volume, asks1[0].volume, abs(pos1))
                exchange.insert_order(stock2, price=bids2[0].price, volume = volume, side='ask', order_type='ioc') #sell SAN_dual
                exchange.insert_order(stock1, price=asks1[0].price, volume = volume, side='bid', order_type='ioc') #buy SAN                
                Pnl = volume*(bids2[0].price - asks1[0].price)
                total_pnl += Pnl
                print('Cleared shares: ' + str(volume) + ' at: ' + str(Pnl) + ' the strat pnl is now: ' + str(total_pnl))

# Trading strategies
def arbitrage_1(stock1, stock2, max_positions, min_spread = 0.1):
    global total_pnl
    book1 = exchange.get_last_price_book(stock1)
    book2 = exchange.get_last_price_book(stock2)
    
    bids1 = book1.bids #PRICE TO BUY
    asks1 = book1.asks #PRICE TO SELL
    
    bids2 = book2.bids
    asks2 = book2.asks
    
    if bids1[0].price - min_spread > asks2[0].price: #if price to buy SAN is greater than price to sell SAN_dual
        volume = min(bids1[0].volume, asks2[0].volume, max_positions[1]) #select available volume
        if volume > 0:
            exchange.insert_order(stock1, price=bids1[0].price, volume = volume, side='ask', order_type='ioc') #sell 1 at high price
            exchange.insert_order(stock2, price=asks2[0].price, volume = volume, side='bid', order_type='ioc') #buy 2 at low price
        Pnl = volume*(bids1[0].price-asks2[0].price)
        total_pnl += Pnl
        print('executed 1, P&L:', Pnl, bids1[0].price, asks2[0].price, volume, total_pnl)

    if bids2[0].price - min_spread > asks1[0].price: #if price to buy SAN_dual is greater than price to sell SAN
        volume = min(bids2[0].volume, asks1[0].volume, max_positions[0])
        if volume > 0:
            exchange.insert_order(stock2, price=bids2[0].price, volume = volume, side='ask', order_type='ioc') #sell 2 (SAN_Dual) at high
            exchange.insert_order(stock1, price=asks1[0].price, volume = volume, side='bid', order_type='ioc') #buy 1 (SAN) at low
        Pnl = volume*(bids2[0].price-asks1[0].price)
        total_pnl += Pnl
        print('executed 2, P&L:', Pnl,bids2[0].price, asks1[0].price, volume, total_pnl)       



def futures_arbitrage(stock):
    
    #F = S*(1+r)^t 
    pass



        
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

    max_positions = max_position(STOCK_A_ID)
    max_positions2 = max_position('NVDA')
    try:
        arbitrage_1(STOCK_A_ID, STOCK_B_ID, max_positions, min_spread = 0.2) #running the strat
    except:
        print('Exception')
    try:
        arbitrage_1(stock1= 'NVDA', stock2='NVDA_DUAL', max_positions = max_positions2, min_spread = 0.2)
    except:
        print('Exception NVDA')
    clear_mismatch(STOCK_A_ID, STOCK_B_ID)
    clear_mismatch('NVDA', 'NVDA_DUAL')
    clear_book(STOCK_A_ID, STOCK_B_ID, max_spread=0.1)
    clear_book('NVDA', 'NVDA_DUAL', max_spread=0.05)

    print(f'\nSleeping for 5 seconds.')
    time.sleep(5)
