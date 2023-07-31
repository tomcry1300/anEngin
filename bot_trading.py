# -----------------------------------------------------------------------------
# Copyright (c) 2022 Tom McLaughlin @ Craft-Crypto, LLC
#
# Other libraries used in the project:
#
# Copyright (c) 2015-2019 Digital Sapphire - PyUpdater
# Copyright (c) 2017 Igor Kroitor - ccxt
# Copyright (c) 2018 P G Jones - hypercorn
# Copyright (c) 2017 P G Jones - quart
# Copyright (c) 2007 vxgmichel - aioconsole
# Copyright (c) 2013-2021 Aymeric Augustin and contributors - websockets
# Copyright (c) 2017-2018 Alex Root Junior - aiogram
# Copyright (c) 2022 Craft-Crypto, LLC - Craft-Crypto Helpers
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# -----------------------------------------------------------------------------

from CraftCrypto_Helpers.Helpers import is_float, copy_prec
import time
import asyncio
from MarketMath import calculate_market_indicators, determine_buy_sell
from CraftCrypto_Helpers.BaseRecord import BaseRecord
from aioconsole import ainput
from .trade_api_calls import broadcast


async def check_bot_cards(self, candle):
    bb_cards = [card for card in self.bb_cards if card.candle == candle]
    tasks = []
    self.bb_active_trades = 0
    for tc in self.bb_trades:
        if not tc.sold:
            self.bb_active_trades += 1

    if self.bb_active and bb_cards:
        for card in bb_cards:
            tasks.append(asyncio.create_task(self.do_check_bot_cards(candle, card, self.bb_trades)))
        data = await asyncio.gather(*tasks)
        # await self.do_check_bot_cards(candle, card, self.bb_trades, self.bb_trade_limit, self.bb_active_trades)
    tasks = []
    self.ab_active_trades = 0
    for tc in self.ab_trades:
        if not tc.sold:
            self.ab_active_trades += 1
    ab_cards = [card for card in self.ab_cards if card.candle == candle]
    if self.ab_active and ab_cards:
        for card in ab_cards:
            tasks.append(asyncio.create_task(self.do_check_bot_cards(candle, card, self.ab_trades)))
        data = await asyncio.gather(*tasks)


async def do_check_bot_cards(self, candle, coin_card, trades):
    # We can gain some effeciency by checking on the cards with trades first, and then going on to others.
    # this way if over limit, that is cool.
    ex = self.exchange_selector(coin_card.exchange)
    if coin_card.active: # ex.balance[card.pair] > 0 and card.active:  # Can be better by determining min buy and checking this first before continuing
        for coin in coin_card.coin.split(','):
            cp = coin.strip() + '/' + coin_card.pair
            if cp in ex.symbols:
                # needed_ohlc.append([ex, cp, card.candle, card.my_id])
                msg = 'Starting checks of ' + cp
                await self.my_msg(msg, verbose=True)
                ohlc = await self.async_get_ohlc(ex, cp, candle, 1000)
                make_buy = False
                make_sell = False
                dca_trade = False
                try:
                    if ohlc:
                        make_buy, make_sell, price = await check_card_trade(coin_card, ohlc)
                except Exception as e:
                    msg = 'Error in calculating trade data for ' + cp + ': ' + str(e)
                    await self.my_msg(msg, to_tele=True, to_broad=True)
                    coin_card.active = False
                    await broadcast({'action': 'update_cc', 'card': coin_card.to_dict()})

                if make_buy:
                    # Check DCA. Trade limit will be checked right before the bot can buy
                    for tc in trades:
                        if (tc.coin == coin_card.coin and tc.pair == coin_card.pair
                                and not tc.sold and tc.exchange == coin_card.exchange):
                            if is_float(tc.dca_buyback_price):
                                if float(tc.now_price) > float(tc.dca_buyback_price):
                                    make_buy = False
                                    msg = 'Wanted to buy {0}, but price is not below buyback price'.format(cp)
                                    await self.my_msg(msg, verbose=True)
                                else:
                                    make_buy = True
                                    dca_trade = True
                            else:
                                make_buy = False
                                msg = 'Wanted to buy {0}, but there is an existing active trade'.format(cp)
                                await self.my_msg(msg, verbose=True)
                            break

                if make_buy:
                    if is_float(price):
                        msg = 'Making a Buy for ' + cp
                        await self.my_msg(msg, verbose=True)
                        await self.make_bot_buy(coin_card, dca_trade)

                    # print('2nd count and limit', count, trade_limit)
                    else:
                        msg = 'Wanted to by ' + cp + ' but no price data yet'
                        await self.my_msg(msg, verbose=True)

                if make_sell:
                    # if it said make sell, I think all we do is say that it is ready, and let our checker do the rest
                    msg = cp + ' ready to sell.'
                    await self.my_msg(msg, verbose=True)
                    coin_card.ready_sell = True
            else:
                # print(coin_card.coin, coin_card.pair)
                coin_card.last_update = 'Coin/Pair Not Listed'
                coin_card.active = False
                await broadcast({'action': 'update_cc', 'card': coin_card.to_dict()})


async def check_card_trade(coin_card, ohlc, *args):
    # print('starting cp', cp)
    closes = [p[4] for p in ohlc if p[5] > 0]
    # print(closes)

    # print('reference price', test, card['prec'], cp)

    indicators = calculate_market_indicators(closes, ohlc, coin_card)

    make_buy, make_sell, p = determine_buy_sell(indicators, coin_card, closes, -2)
    # print(cp, len(closes), len(indicators))
    coin_card.last_evaluated_price = str(p)
    coin_card.last_update = time.strftime('%I:%M:%S %p %m/%d/%y')
    await broadcast({'action': 'update_cc', 'card': coin_card.to_dict()})
# if not args:
#     self.out_q.put(['update_cc', card])
    # print('ending cp', cp)
    return make_buy, make_sell, p


async def make_bot_buy(self, coin_card, dca_trade=False):
    try:
        # print('trying to buy')
        # cp for advanced bot is in card. for bb it is in args
        coin = coin_card.coin
        pair = coin_card.pair
        kind = coin_card.kind

        cp = coin + '/' + pair
        ex = self.exchange_selector(coin_card.exchange)
        buy_amt = 0
        await self.a_debit_exchange(ex, 1, 'make_bot_buy')

        info = ex.market(cp)
        min_coin_amt = float(info['limits']['amount']['min'])
        min_cost_amt = float(info['limits']['cost']['min'])
        price = float(ex.prices[cp.replace('/', '')])

        if not price:
            # print(ex.prices)
            msg = kind + ' attempted to buy ' + cp + ' But no price has been recorded.'
            await self.my_msg(msg, verbose=True, to_broad=True)
            coin_card.buy_now = False
            return

        num_coin_on_cost = min_cost_amt / price
        while num_coin_on_cost > min_coin_amt:
            min_coin_amt += float(info['limits']['amount']['min'])
        # print(coin_card.pair, ex.balance)
        pair_bal = float(ex.balance[coin_card.pair]) * .99
        msg = 'Balance Data for ' + cp + ': \nPair Balance: ' + str(pair_bal) + '\nMin Trade Amount: ' + str(min_cost_amt)
        await self.my_msg(msg, verbose=True)

        if pair_bal > min_cost_amt:
            # get how much to buy
            pair_amt = 0  # of pair
            coin_amt = 0  # of coin, what we are going to use to buy
            if is_float(coin_card.pair_per):
                # percentage of balance
                pair_amt = float(coin_card.pair_per) / 100 * pair_bal
                coin_amt = pair_amt / price
                if min_coin_amt > coin_amt:
                    coin_amt = min_coin_amt
            elif is_float(coin_card.pair_amt):
                pair_amt = float(coin_card.pair_amt)
                coin_amt = pair_amt / price
                if min_coin_amt > coin_amt:
                    coin_amt = min_coin_amt
            elif is_float(coin_card.pair_minmult):
                # pair_amt = float(card.pair_minmult.strip('x')) * min_cost_amt
                coin_amt = float(coin_card.pair_minmult.strip('x')) * min_coin_amt

            coin_amt = float(ex.amount_to_precision(cp, coin_amt * self.sell_mod))
            # print(coin_amt, min_coin_amt, min_cost_amt, pair_bal, coin_card.pair_minmult)
            if coin_amt:
                msg = 'Trade Data for ' + cp + ': \nCoin Amount: ' + str(coin_amt) + '\nPair Amount: ' + str(pair_amt)
                await self.my_msg(msg, verbose=True)

                try:
                    # check to see if this goes past trade limit:
                    # we want to buy, but we need to check number of trades that are active
                    make_buy = True
                    count = 0
                    if coin_card.kind == 'Basic Bot' and is_float(self.bb_trade_limit):
                        if self.bb_active_trades >= float(self.bb_trade_limit):
                            make_buy = False
                    if coin_card.kind == 'Advanced Bot' and is_float(self.ab_trade_limit):
                        if self.ab_active_trades >= float(self.ab_trade_limit):
                            make_buy = False

                    if not dca_trade and make_buy:
                        if coin_card.kind == 'Basic Bot':
                            self.bb_active_trades += 1
                        else:
                            self.ab_active_trades += 1

                    if not make_buy and not dca_trade:
                        msg = f'Wanted to buy {cp}, but Trades are already at the limit'
                        await self.my_msg(msg, verbose=True)

                    if make_buy or dca_trade:
                        ordr = await ex.create_market_buy_order(cp, coin_amt)
                    else:
                        ordr = None
                    # Then we check to see if it is a dca, if it is, we can buy.
                    # This can override trade limit as we are not adding a new coin

                except Exception as e:
                    if 'MIN_NOTIONAL' in str(e) or 'insufficient balance' in str(e) or '1013' in str(e):
                        msg = 'Trade Error: Too Low of trade amount. Trying to trade all...'
                        await self.my_msg(msg, verbose=True, to_broad=True)
                        ordr = await self.try_trade_all(ex, cp, True)
                    else:
                        msg = kind + ' error in making buy of ' + cp + ': ' + str(e)
                        if '1000ms ahead' in str(e):
                            await ex.load_time_difference()
                            msg += '. Attempting to resync Clocks. If This error continues, use the clock command to see more.'
                        coin_card.active = False
                        await broadcast({'action': 'update_cc', 'card': coin_card.to_dict()})
                        await self.my_msg(msg, to_tele=True, to_broad=True)
                        ordr = None
                        return

                if ordr:
                    msg = 'Order Details: ' + str(ordr)
                    await self.my_msg(msg, verbose=True)
                    if is_float(ordr['average']):
                        pr = copy_prec(ordr['average'], '.11111111')
                    elif is_float(ordr['price']):
                        pr = copy_prec(ordr['price'], '.11111111')
                    else:
                        pr = str(ex.prices[cp.replace('/', '')])

                    if is_float(ordr['filled']):
                        buy_amount = float(ordr['filled'])
                    else:
                        buy_amount = coin_amt

                    # Now it is time to add our buy to the stash
                    await self.add_trade_card(cp, coin_card, pr, buy_amount)

                    msg = kind + ' bought ' + str(buy_amount) + ' ' + coin + ' at ' + str(pr) + ' ' + pair + '.'
                    await self.my_msg(msg, to_tele=True, to_broad=True)
                    await self.gather_update_bals(str(ex))
                # elif not args:
                #     card.active = False
                coin_card.buy_now = False

            else:
                msg = 'Error: Could not determine Coin amount for ' + cp
                await self.my_msg(msg, to_tele=True, to_broad=True)

        else:
            msg = f'{kind} attempted to buy {cp} with {str(pair_bal)} {pair}. Minimum Amount is {min_cost_amt} {pair}'

            await self.my_msg(msg, to_tele=True)

    except Exception as e:
        msg = 'Error in Trying to buy: ' + str(e)
        if '1000ms ahead' in str(e):
            await ex.load_time_difference()
            msg += '. Attempting to resync Clocks. If This error continues, use the clock command to see more.'
        await self.my_msg(msg, verbose=True)
    # if not args:
    #     for old_card in self.ab_cards:
    #         if old_card.my_id == card.my_id:
    #             print('FOUND CARDS!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
    #             old_card.set_record(card.to_dict())

#I need this
# if card['buy_now']:
#     msg = 'Insufficient balance to buy ' + cp + '. Attempted to buy ' + card['coin']
#     msg += ' with ' + str(pair_bal) + ' ' + card['pair'] + '.'
#     await self.out_q.coro_put(['msg', msg])
# card['buy_now'] = False
# await self.out_q.coro_put(['update_cc', card])


async def add_trade_card(self, cp, coin_card, buy_price, buy_amount):
    if coin_card.kind == 'Basic Bot':
        trades = self.bb_trades
    else:
        trades = self.ab_trades

    coin, pair = cp.split('/')

    if is_float(coin_card.dca_buyback_per):
        # look through and see if there is a child
        for dc in trades:
            if cp.replace('/', '') == dc.coin + dc.pair and \
                    coin_card.exchange == dc.exchange and not dc.sold:
                rr = {'buy_price': str(buy_price),
                      'sold_price': '0',
                      'amount': copy_prec(buy_amount, coin_card.precision),
                      'sold': False}
                dc.childs.append(rr)
                await self.sync_trades_to_cards()
                await broadcast({'action': 'update_tc', 'card': dc.to_dict()})
                return

    t = BaseRecord()
    t.set_record(coin_card.to_dict())
    # print('t', t)
    # print('c', card)
    t.coin = coin
    t.pair = pair
    t.amount = copy_prec(buy_amount, coin_card.precision)
    t.buy_price = str(buy_price)
    t.my_id = await self.get_my_id()
    rr = {'buy_price': str(buy_price),
          'sold_price': '0',
          'amount': copy_prec(buy_amount, coin_card.precision),
          'sold': False}
    t.childs.append(rr)

    trades.append(t)

    if coin_card.kind == 'Basic Bot':
        self.bb_active_trades = 0
        for tc in self.bb_trades:
            if not tc.sold:
                self.bb_active_trades += 1
    else:
        self.ab_active_trades = 0
        for tc in self.ab_trades:
            if not tc.sold:
                self.ab_active_trades += 1

    await self.sync_trades_to_cards()

    if coin_card.kind == 'Basic Bot':
        self.bb_trades = trades
    else:
        self.ab_trades = trades

    await broadcast({'action': 'update_tc', 'card': t.to_dict()})


async def update_card_trade_data(self, trade):
    if trade.kind == 'Basic Bot':
        card_data = self.bb_cards
    else:
        card_data = self.ab_cards

    for card in card_data:
        if card.coin == trade.coin and card.pair == trade.pair \
                and card.exchange == trade.exchange:
            cp = card.coin + '/' + card.pair

            if is_float(card.num_trades):
                card.num_trades = str(int(card.num_trades) + 1)
            else:
                card.num_trades = '1'

            if is_float(card.trade_vol):
                new_trade_vol = float(trade.trade_amount) + float(card.trade_vol)
                ex = self.exchange_selector(card.exchange)
                card.trade_vol = str(ex.amount_to_precision(cp, new_trade_vol))
            else:
                card.trade_vol = trade.trade_amount
            # update average buys
            if is_float(card.average_buys):
                mid = float(card.average_buys) * float(card.trade_vol) + float(trade.buy_price) * \
                      float(trade.trade_amount)
                new_avg = mid / (float(trade.trade_amount) + float(card.trade_vol))
                card.average_buys = copy_prec(new_avg, card.precision)
            else:
                card.average_buys = trade.buy_price

            if is_float(card.average_sells):
                mid = float(card.average_sells) * float(card.trade_vol) + float(trade.sold_price) * \
                      float(trade.trade_amount)
                new_avg = mid / (float(trade.trade_amount) + float(card.trade_vol))
                card.average_sells = copy_prec(new_avg, card.precision)
            else:
                card.average_sells = trade.sold_price

            gain = float(card.average_sells) / float(card.average_buys) * 100 - 100
            card.per_gain = str(round(gain, 2))
            await broadcast({'action': 'update_cc', 'card': card.to_dict()})
            break


async def check_trade_sells(self):
    if not self.bb_sells_lock and self.bb_active:
        self.bb_sells_lock = True
        await self.do_check_trade_sells(self.bb_trades)
        self.bb_sells_lock = False

    if not self.ab_sells_lock and self.ab_active:
        self.ab_sells_lock = True
        await self.do_check_trade_sells(self.ab_trades)
        self.ab_sells_lock = False


async def do_check_trade_sells(self, trades):
    for tc in (tc for tc in trades if (not tc.sold and tc.active)):
        sell = False
        # Needs to be updated for BitMEX
        sym = tc.coin + '/' + tc.pair
        ex = self.exchange_selector(tc.exchange)

        # try:
        if tc.sell_now:
            sell = True
            # print('going to sell', tc)
        else:
            if is_float(tc.stop_price):
                if float(tc.now_price) <= float(tc.stop_price) and is_float(tc.now_price):
                    # Sell!!! We hit our stop!
                    sell = True

            if is_float(tc.trail_per):
                if is_float(tc.trail_price) and float(tc.now_price) <= float(tc.trail_price):
                    sell = True
                elif float(tc.now_price) >= float(tc.take_profit_price) and not is_float(tc.trail_price):
                    new_trail_price = float(tc.now_price) * (100 - float(tc.trail_per)) / 100
                    tc.trail_price = copy_prec(new_trail_price, tc.now_price, 1)
                elif is_float(tc.trail_price):
                    # check to see if I need to update trail
                    new_trail_price = float(tc.now_price) * (100 - float(tc.trail_per)) / 100
                    if new_trail_price > float(tc.trail_price):
                        tc.trail_price = copy_prec(new_trail_price, tc.now_price, 1)

                # if no stop, continue
                elif not sell:
                    # check if price is ready to go
                    if is_float(tc.now_price) and is_float(tc.take_profit_price):
                        if float(tc.now_price) >= float(tc.take_profit_price):
                            sell = True

                    # Check in with Trade's coin card.
                    for card in self.ab_cards:
                        if card.coin == tc.coin and card.pair == tc.pair and card.exchange == tc.exchange:
                            # the is the combination of all selling parameters
                            sell = card.ready_sell

                            # If the card is set for DCA, and no take profit, but selling on TI, then we
                            # want to be at least even
                            if is_float(card.dca_buyback_per) and sell:
                                if not float(tc.now_price) > float(tc.buy_price):
                                    sell = False

                    # Checks to see if TI says to sell, but it is under a take profit
                    if is_float(tc.now_price) and is_float(tc.take_profit_price) and sell:
                        if not float(tc.now_price) >= float(tc.take_profit_price):
                            sell = False

            # If the bot has logged no price yet, don't sell
            if not is_float(tc.now_price):
                sell = False

        try:
            if sell:
                coin_bal = is_float(ex.balance[tc.coin])

        except Exception as e:
            await self.update_bals(ex)
            try:
                coin_bal = is_float(ex.balance[tc.coin])
            except Exception as e:
                # print('No balance for trade')
                msg = tc.kind + ' ' + tc.coin + ' balance error: ' + str(e)
                await self.my_msg(msg, to_tele=True, to_broad=True)
                sell = False
                tc.sell_now = False
                await broadcast({'action': 'update_tc', 'card': tc.to_dict()})

        # Finally, we are past all the filters, now we can see if we can make it happen

        if sell:
            # time to sell. let's figure out how much we are selling
            sell_amt = 0

            for child in tc.childs:
                sell_amt += float(child['amount'])

            if sell_amt > 0:
                await self.a_debit_exchange(ex, 1, 'do_check_trade_sells')
                sell_amt = float(ex.amount_to_precision(sym, sell_amt * self.sell_mod))
                msg = 'Time to Sell ' + sym + '!\n Sell Price: ' + tc.take_profit_price + '\nCurrent Price: ' + \
                      tc.now_price + '\nBuy Price: ' + tc.buy_price
                await self.my_msg(msg, verbose=True)
                try:
                    # print('selling', sym, tc.sold)
                    if not tc.sold:
                        tc.sell_now = False
                        tc.sold = True
                        ordr = await ex.create_market_sell_order(sym, sell_amt)
                    else:
                        ordr = None
                    # print(ordr)
                    await self.save()
                except Exception as e:
                    # print(e)
                    if 'MIN_NOTIONAL' in str(e) or 'insufficient balance' in str(e) or '1013' in str(e):
                        msg = 'Trade Error: Too Low of trade amount. Trying to trade all...'
                        await self.my_msg(msg, verbose=True, to_broad=True)
                        tc.sell_now = False
                        tc.sold = True
                        ordr = await self.try_trade_all(ex, sym, False)
                        await self.save()
                    else:
                        msg = tc.kind + ' error in checking sell of ' + sym + ': ' + str(e)
                        if '1000ms ahead' in str(e):
                            await ex.load_time_difference()
                            msg += '. Attempting to resync Clocks. If This error continues, use the clock command to see more.'
                        ordr = None
                        tc.active = False
                        tc.sell_now = False
                        await broadcast({'action': 'update_tc', 'card': tc.to_dict()})
                        await self.my_msg(msg, to_tele=True, to_broad=True)

                if ordr:
                    msg = tc.kind + ' Order Details: ' + str(ordr)
                    await self.my_msg(msg, verbose=True)
                    if is_float(ordr['average']):
                        pr = copy_prec(ordr['average'], '.11111111')
                    elif is_float(ordr['price']):
                        pr = copy_prec(ordr['price'], '.11111111')
                    else:
                        pr = str(ex.prices[sym.replace('/', '')])

                    if is_float(ordr['filled']):
                        sold_amount = float(ordr['filled'])
                    else:
                        sold_amount = sell_amt

                    msg = tc.kind + ' sold ' + str(sold_amount) + ' ' + tc.coin + ' at ' + str(pr) + ' ' + tc.pair
                    await self.my_msg(msg, to_tele=True, to_broad=True)

                    tc.sold_price = pr
                    tc.now_price = pr
                    tc.amount = str(sold_amount)
                    gain = float(tc.sold_price) / float(tc.buy_price) * 100 - 100
                    tc.gl_per = str(round(gain, 2))
                    await broadcast({'action': 'update_tc', 'card': tc.to_dict()})
                # else:
                #     tc.sell_now = False
                #     tc.active = False
                #     tc.sold_price = '0'
                #     tc.gl_per = 'Error'
                #     tc.now_price = '0'
                #     tc.sold = True
                #     await broadcast({'action': 'update_tc', 'card': tc.to_dict()})

                await self.update_card_trade_data(tc)
                await self.gather_update_bals(str(ex))

        # except Exception as e:
        #     print('sell error', e)
        #     msg = 'Error in checking ' + tc.kind + ' sell of ' + sym + ': ' + str(e)
        #     await self.my_msg(msg, to_tele=True, to_broad=True)
        #     tc.sell_now = False
        #     tc.active = False
        #     tc.sold_price = '0'
        #     tc.gl_per = 'Error'
        #     tc.now_price = '0'
        #     tc.sold = True
        #     await broadcast({'action': 'update_tc', 'card': tc.to_dict()})


async def quick_trade(self, *args):
    try:
        kind = None
        ex = None
        cp = None
        amount = None
        if not args:
            await self.my_msg('*******')
            await self.my_msg('Select an Exchange to Trade:')
            await self.my_msg('1 - Binance')
            await self.my_msg('2 - Binance US')
            await self.my_msg('3 - BitMEX')
            await self.my_msg('4 - Coinbase Pro')
            await self.my_msg('5 - FTX')
            await self.my_msg('6 - Kraken')
            msg = await ainput(">")
            ex = ''
            if msg == '1':
                ex = 'Binance'
            elif msg == '2':
                ex = 'Binance US'
            elif msg == '3':
                ex = 'BitMEX'
            elif msg == '4':
                ex = 'Coinbase Pro'
            elif msg == '5':
                ex = 'FTX'
            elif msg == '6':
                ex = 'Kraken'
            try:
                ex = self.exchange_selector(ex)
            except Exception as e:
                await self.my_msg('Error in Exchange Selection')
                return

            await self.my_msg('Enter \'buy\' or \'sell\'')
            msg = await ainput(">")
            if msg.upper().strip() == 'buy':
                kind = 'buy'
            else:
                kind = 'sell'

            await self.my_msg('Enter a Coin/Pair to trade (Example: BTC/USDT)')
            msg = await ainput(">")
            cp = msg.strip().upper()

            await self.my_msg('Choose a % to trade (Example: 5, 10, 50, 75, 100....):')
            msg = await ainput(">")
            amount = msg.strip().strip('%')

        else:
            data = args[0]
            kind = data[0]
            ex = data[1]
            cp = data[2]
            amount = data[3]

        if kind == 'buy':
            # 'quick_buy': #ex, pair, cp, %
            amount = float(ex.balance[cp.split('/')[1]]) * float(amount) / 100
            amount = amount / float(ex.prices[cp.replace('/', '')])

        else:
            amount = float(ex.balance[cp.split('/')[0]]) * float(amount) / 100
        amount = ex.amount_to_precision(cp, amount * .99)

        await self.a_debit_exchange(ex, 1, 'quick_trade')

        price = float(ex.prices[cp.replace('/', '')])

        if not price:
            msg = 'Attempted to Quick Trade ' + cp + ' But no price has been recorded.'
            await self.my_msg(msg, verbose=True)
        else:
            try:
                if kind == 'buy':
                    ordr = await ex.create_market_buy_order(cp, amount)
                else:
                    ordr = await ex.create_market_sell_order(cp, amount)
            except Exception as e:
                    msg = 'Error in Quick Trade of ' + cp + ': ' + str(e)
                    if '1000ms ahead' in str(e):
                        await ex.load_time_difference()
                        msg += '. Attempting to resync Clocks. If This error continues, use the clock command to see more.'
                    await self.my_msg(msg, to_tele=True, to_broad=True)
                    ordr = None
                    self.pause_msg = False

            if ordr:
                msg = 'Quick Trade Order Details: ' + str(ordr)
                await self.my_msg(msg, verbose=True)
                if is_float(ordr['average']):
                    pr = copy_prec(ordr['average'], '.11111111')
                elif is_float(ordr['price']):
                    pr = copy_prec(ordr['price'], '.11111111')
                else:
                    pr = str(ex.prices[cp.replace('/', '')])

                if is_float(ordr['filled']):
                    amount = float(ordr['filled'])

                if kind == 'buy':
                    msg = 'Bought ' + str(amount) + ' ' + cp + ' at ' + str(pr) + '.'
                else:
                    msg = 'Sold ' + str(amount) + ' ' + cp + ' at ' + str(pr) + '.'

                await self.my_msg(msg, to_tele=True, to_broad=True)
                await self.gather_update_bals()

    except Exception as e:
        # print('sell all error', e)
        if 'MIN_NOTIONAL' in str(e) or 'insufficient balance' in str(e) or '1013' in str(e):
            # print('too low')
            msg = 'Quick Trade Amount too low for Exchange.'
            await self.my_msg(msg, to_tele=True, to_broad=True)
        else:
            msg = 'Error in Quick Trade ' + cp + ': ' + str(e)
            if '1000ms ahead' in str(e):
                await ex.load_time_difference()
                msg += '. Attempting to resync Clocks. If This error continues, use the clock command to see more.'
            await self.my_msg(msg, to_tele=True, to_broad=True)

