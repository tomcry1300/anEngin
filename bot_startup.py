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
import ccxt.binance
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers import cron
import asyncio
import time
import ccxt.async_support as a_ccxt
from hypercorn.asyncio import serve
from hypercorn.config import Config
from CraftCrypto_Helpers.Helpers import get_store, save_store, archive_store, delete_store, dir_path
from TradeEngine.tele_api_calls import TeleBot
from TradeEngine.trade_api_calls import engine_api
from CraftCrypto_Helpers.BaseRecord import BaseRecord, convert_record


async def initialize(self):
    # Set up initial variables and such
    await self.my_msg('Initializing...')

    # Now get Telegram Going
    store = get_store('TeleKeys')
    await self.my_msg('Starting Telegram Bot...')
    token = None
    chat_id = None
    try:
        if store:
            token = store['tele_token']
            chat_id = store['tele_chat']
    except Exception as e:
        await self.my_msg('Error in Loading Telegram Keys: ' + str(e))

    if token and chat_id:
        await self.my_msg('Connecting to Telegram....', to_broad=True)
        await self.init_tele_bot(token, chat_id)
        await self.my_msg('Connected to Telegram.', to_broad=True, to_tele=True)
    else:
        await self.my_msg('No Telegram Keys Found.')
        # await self.q.put('set tele keys')

    tt = time.time()

    await self.my_msg('Loading Exchanges...')
    self.a_binance = a_ccxt.binance({'options': {'adjustForTimeDifference': True}})
    self.a_binanceUS = a_ccxt.binanceus({'options': {'adjustForTimeDifference': True}})
    self.a_bitmex = a_ccxt.bitmex({'options': {'adjustForTimeDifference': True}})
    self.a_cbp = a_ccxt.coinbasepro({'options': {'adjustForTimeDifference': True}})
    self.a_kraken = a_ccxt.kraken({'options': {'adjustForTimeDifference': True}})
    self.a_ftx = a_ccxt.ftx({'options': {'adjustForTimeDifference': True}})

    self.exchanges = ['Binance', 'Binance US', 'BitMEX', 'Coinbase Pro', 'Kraken', 'FTX']

    for exchange in self.exchanges:
        ex = self.exchange_selector(exchange)
        ex.timeout = 30000
        ex.socket = None
        ex.socket_connected = False
        ex.api_ok = False
        ex.prices = {}
        ex.balance = {}
        ex.rate_limit = 10  # per second. Updates to more correct amount

    await self.my_msg('Checking for API Keys...')
    store = get_store('APIKeys')
    if store:
        for exchange in self.exchanges:
            ex = self.exchange_selector(exchange)
            try:
                ex.apiKey = store[exchange]['key']
                ex.secret = store[exchange]['secret']
                if exchange == 'Coinbase Pro':
                    ex.password = store[exchange]['password']
            except Exception as e:
                self.my_msg('Error in getting API Store ' + exchange)
        # print('did I get here?')
        need_keys = await self.test_apis()
        # if need_keys:
        #     await self.q.put('set API keys')
    else:
        await self.my_msg('No Keys Found...')
        # await self.q.put('set API keys')

    await self.my_msg('Loading Strategies...')
    store = get_store('BasicStrats')
    if not store or not '4' in store:
        strat = BaseRecord()
        strat.title = 'RSI DCA Minute Trading'
        strat.description = ('This strategy uses 1 minute candles and the Relative Strength Index to ' +
                             'initiate buys. It then looks for quick profit opportunities, and chances to ' +
                             'Down Cost Average on the dips.')
        strat.candle = "1m"
        strat.take_profit_per = "2"
        strat.trail_per = ".5"
        strat.dca_buyback_per = "10"
        strat.rsi_buy = "30"

        strat1 = BaseRecord()
        strat1.title = 'Cross and Pop'
        strat1.description = ('Combining Simple Moving Average Crosses with Trailing Stop Losses and ' +
                              'Down Cost Averaging is a great way to earning profit off a volatile market in ' +
                              'the 5 minute candle.')
        strat1.candle = "5m"
        strat1.take_profit_per = "2"
        strat1.trail_per = ".5"
        strat1.dca_buyback_per = "10"
        strat1.sma_cross_fast = "17"
        strat1.sma_cross_slow = "55"
        strat1.sma_cross_buy = "Yes"

        strat2 = BaseRecord()
        strat2.title = 'Buy The Dip'
        strat2.description = ('This works on the 30min candle to buy when the price dips 10% past the 100 EMA. ' +
                              'It the sets a decent Take Profit with a trail and a DCA.')
        strat2.candle = "30m"
        strat2.take_profit_per = "6"
        strat2.trail_per = "2"
        strat2.dca_buyback_per = "15"
        strat2.ema = "100"
        strat2.ema_percent = "10"
        strat2.ema_buy = "Yes"

        strat3 = BaseRecord()
        strat3.title = 'MACD Stoch Long Haul'
        strat3.description = ('A Strategy that works on the 4 hour candle, but tends to find just the ' +
                              'perfect time to buy. The Long Haul waits to buy when the MACD to cross up and ' +
                              'be in the red, with a Stoch under 30, and keeps a moderate take profit, stop ' +
                              'loss, and trail.')
        strat3.candle = "4h"
        strat3.take_profit_per = "10"
        strat3.trail_per = "1"
        strat3.stop_per = "20"
        strat3.macd_cross_buy = "Yes"
        strat3.macd_color_buy = "Yes"
        strat3.stoch_val_buy = "30"

        strat_store = {'1': strat.to_dict(),
                       '2': strat1.to_dict(),
                       '3': strat2.to_dict(),
                       '4': strat3.to_dict()
                      }
        save_store('BasicStrats', strat_store)

    await self.my_msg('Loading Saved Trades...')

    # Check for Legacy
    try:
        store = get_store('LiteBot')
        if store:
            for cc in store['trades']:
                new_rec = convert_record(cc)
                new_rec.kind = 'Basic Bot'
                self.bb_trades.append(new_rec)
            archive_store('LiteBot')
            await self.update_strat('Binance', '1', 'USD', True)
            self.bb_strat.pair_minmult = '2'
            await self.save()
        else:
            delete_store('LiteBot')
            store = get_store('BasicBot')
            if store:
                try:
                    if 'trades' in store:
                        # Have legacy
                        for cc in store['trades']:
                            new_rec = convert_record(cc)
                            new_rec.kind = 'Basic Bot'
                            self.bb_trades.append(new_rec)
                        archive_store('BasicBot')
                        delete_store('BasicBot')
                        await self.update_strat('Binance', '1', 'USD', True)
                        self.bb_strat.pair_minmult = '2'
                        await self.save()
                    else:
                        self.bb_strat.set_record(store['bb_strat'])
                        for cc in store['bb_cards']:
                            rec = BaseRecord()
                            rec.set_record(cc)
                            self.bb_cards.append(rec)
                        for tc in store['bb_trades']:
                            rec = BaseRecord()
                            rec.set_record(tc)
                            self.bb_trades.append(rec)
                        self.bb_trade_limit = store['bb_trade_limit']
                    await self.my_msg('Found Basic Bot Trades:')
                except Exception as e:
                    # print(e)
                    await self.my_msg('Error loading Basic Bot Trades: ' + str(e))

            else:
                await self.my_msg('No Saved Basic Bot Trades Found.')
                # await self.q.put('set strat')

        # Check for Legacy Advanced Bot
        store_cc = get_store('coincard')
        store_tc = get_store('coincard_trade')
        if store_cc or store_tc:
            # Have legacy
            if store_cc:
                for cc in store_cc['coincards']:
                    new_rec = convert_record(store_cc['coincards'][cc])
                    new_rec.kind = 'Advanced Bot'
                    self.ab_cards.append(new_rec)
                archive_store('coincard')
                await self.save()
            if store_tc:
                # Have legacy
                for cc in store_tc['trades']:
                    new_rec = convert_record(store_tc['trades'][cc])
                    new_rec.kind = 'Advanced Bot'
                    self.ab_trades.append(new_rec)
                archive_store('coincard_trade')
                await self.save()
        else:
            delete_store('coincard')
            delete_store('coincard_trade')

            store = get_store('AdvancedBot')
            if store:
                try:
                    for cc in store['ab_cards']:
                        rec = BaseRecord()
                        rec.set_record(cc)
                        self.ab_cards.append(rec)
                    for tc in store['ab_trades']:
                        rec = BaseRecord()
                        rec.set_record(tc)
                        self.ab_trades.append(rec)
                    self.ab_trade_limit = store['ab_trade_limit']
                    await self.my_msg('Found Advanced Bot Trades:')
                except Exception as e:
                    await self.my_msg('Error loading Advanced Bot Trades')

            else:
                await self.my_msg('No Saved Advanced Bot Trades Found.')

    except Exception as e:
        await self.my_msg('Error in loading Saved Bot Cards: ' + str(e))

    # Manual Trade Cards
    try:
        store = get_store('ManualTrade')
        if store:
            try:
                for mt in store['mt_cards']:
                    rec = BaseRecord()
                    rec.set_record(mt)
                    self.mt_cards.append(rec)
                await self.my_msg('Found Basic Bot Trades:')
            except Exception as e:
                # print(e)
                await self.my_msg('Error loading Basic Bot Trades: ' + str(e))

        else:
            rec = BaseRecord()
            rec.coin = 'BTC'
            rec.pair = 'USDT'
            rec.exchange = 'Binance'
            self.mt_cards.append(rec)
            await self.my_msg('No Saved Manual Trades Found.')
            # await self.q.put('set strat')

    except Exception as e:
        await self.my_msg('Error in loading Saved Manual Trade Cards: ' + str(e))

    #
    # await self.my_msg('Strategy: ' + self.strat_name, False, False)
    # await self.my_msg('Exchange: ' + str(self.active_exchange), False, False)
    # await self.my_msg('Pair: ' + self.pair, False, False)
    # await self.my_msg('Pair Min Mult: ' + self.pair_minmult, False, False)
    # await self.my_msg('Trade Limit: ' + self.limit, False, False)

    await self.my_msg('Setting Trade Data Scheduler...')
    self.sched = AsyncIOScheduler()

    t1 = cron.CronTrigger(second=3)
    t3 = cron.CronTrigger(minute='*/3', second=5)
    t5 = cron.CronTrigger(minute='*/5', second=5)
    t15 = cron.CronTrigger(minute='*/15', second=5)
    t30 = cron.CronTrigger(minute='*/30', second=5)
    t1h = cron.CronTrigger(minute=0, second=5)
    t2h = cron.CronTrigger(hour='*/2', minute=0, second=5)
    t4h = cron.CronTrigger(hour='*/4', minute=0, second=5)
    t6h = cron.CronTrigger(hour='*/6', minute=0, second=5)
    t8h = cron.CronTrigger(hour='*/8', minute=0, second=5)
    t12h = cron.CronTrigger(hour='*/12', minute=0, second=5)
    t1d = cron.CronTrigger(hour=0, minute=0, second=5)

    candles = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d']
    trigs = [t1, t3, t5, t15, t30, t1h, t2h, t4h, t6h, t8h, t12h, t1d]

    for i in range(len(candles)):
        self.sched.add_job(self.check_bot_cards, args=[candles[i]], trigger=trigs[i], max_instances=5,
                           misfire_grace_time=5, coalesce=True)

    #
    #
    # self.sched.add_job(self.check_bot_cards, args=['Advanced Bot', '3m'], trigger=t3)
    # self.sched.add_job(self.check_bot_cards, args=['Advanced Bot', '5m'], trigger=t5)
    # self.sched.add_job(self.check_bot_cards, args=['Advanced Bot', '15m'], trigger=t15)
    # self.sched.add_job(self.check_bot_cards, args=['Advanced Bot', '30m'], trigger=t30)
    # self.sched.add_job(self.check_bot_cards, args=['Advanced Bot', '1h'], trigger=t1h)
    # self.sched.add_job(self.check_bot_cards, args=['Advanced Bot', '2h'], trigger=t2h)
    # self.sched.add_job(self.check_bot_cards, args=['Advanced Bot', '4h'], trigger=t4h)
    # self.sched.add_job(self.check_bot_cards, args=['Advanced Bot', '6h'], trigger=t6h)
    # self.sched.add_job(self.check_bot_cards, args=['Advanced Bot', '8h'], trigger=t8h)
    # self.sched.add_job(self.check_bot_cards, args=['Advanced Bot', '12h'], trigger=t12h)
    # self.sched.add_job(self.check_bot_cards, args=['Advanced Bot', '1d'], trigger=t1d)

    #
    self.sched.add_job(self.gather_update_bals, trigger=t1, max_instances=5)
    self.sched.add_job(self.save, trigger=t1, max_instances=5)
    #

    # Set up server
    await self.my_msg('Setting Up Trade Server...')
    await asyncio.sleep(.5)
    config = Config()
    config.bind = ["0.0.0.0:8080"]  # As an exa
    self.trade_server = engine_api
    self.trade_server.worker = self
    asyncio.ensure_future(serve(self.trade_server, config))

    # Exchange Finishing Up
    await self.my_msg('Finishing Up Exchanges...')
    asyncio.ensure_future(self.refresh_api())
    self.a_binanceUS.rate_limit = 5
    await self.gather_update_bals()

    # Maybe I need a wait function here for everything to truly finish up. But Also probably not
    await asyncio.sleep(3)
    asyncio.ensure_future(self.check_prices_sells())
    self.sched.start()
    await self.my_msg('Initialization Complete.')
    await self.my_msg(f'TradeEngine Data Can be found in {dir_path}')
    await self.my_msg('*******')
    await self.my_msg('Enter \'setup\' to set up trading.')


async def test_apis(self, *args):
    # This can just test all of them at once
    under_test = self.exchanges
    if args:
        under_test = [args[0]]
    need_keys = True
    for ex in under_test:
        exchange = self.exchange_selector(ex)
        if exchange.apiKey and exchange.secret:
            if str(exchange) in ['Binance', 'Binance US']:
                await self.a_debit_exchange(exchange, 5, 'test_apis')
            else:
                await self.a_debit_exchange(exchange, 1, 'test_apis')

            try:
                await self.update_bals(exchange)
                # print(bal)
                if exchange.balance:
                    exchange.api_ok = True
                    msg = str(exchange) + ' API Keys Accepted'
                    await self.my_msg(msg, to_broad=True)
                    # await exchange.close()
                    need_keys = False
                    for n in range(1, 5):
                        try:
                            msg = 'Attempt ' + str(n) + ' to load markets...'
                            await self.my_msg(msg, to_broad=True)
                            await exchange.load_markets()
                            await self.my_msg('Market loaded.', to_broad=True)
                            break
                        except Exception as e:
                            msg = 'Connection Error: ' + str(e)
                            await self.my_msg(msg, to_broad=True)
                            if n == 5:
                                msg = 'Exceeded Maximum number of retries'
                                await self.my_msg(msg, to_broad=True)

                    # Coinbase actually does not allow fetch tickers right now
                    if not str(exchange) == 'Coinbase Pro':
                        await self.my_msg('Collecting Market Prices...', to_broad=True)
                        price = await exchange.fetch_tickers()
                        if str(exchange) in ['Binance', 'Binance US', 'Kraken']:
                            try:
                                for ky in price:
                                    exchange.prices[ky.replace('/', '')] = price[ky]['close']
                            except Exception as e:
                                await self.my_msg(str(exchange) + 'Fetch Ticker Error: ' + str(e), to_broad=True)
                        elif str(exchange) == 'FTX':
                            try:
                                for ky in price:
                                    self.a_ftx.prices[ky.replace('/', '').replace('-', '')] = price[ky]['close']
                            except Exception as e:
                                await self.my_msg('FTX Fetch Ticker Error: ' + str(e), to_broad=True)

                    if not exchange.socket:
                        await self.my_msg('Activating Web Socket...', to_broad=True)
                        if str(exchange) == 'Binance':
                            exchange.socket = asyncio.ensure_future(self.websocket_bin())
                        elif str(exchange) == 'Binance US':
                            exchange.socket = asyncio.ensure_future(self.websocket_binUS())
                        elif str(exchange) == 'BitMEX':
                            exchange.socket = asyncio.ensure_future(self.websocket_bm())
                        elif str(exchange) == 'Coinbase Pro':
                            exchange.socket = asyncio.ensure_future(self.websocket_cbp())
                        elif str(exchange) == 'FTX':
                            exchange.socket = asyncio.ensure_future(self.websocket_ftx())
                        elif str(exchange) == 'Kraken':
                            exchange.socket = asyncio.ensure_future(self.websocket_kraken())
                    await self.my_msg(str(exchange) + ' loaded.', to_broad=True)

            except Exception as e:
                exchange.api_ok = False
                msg = 'Error with ' + ex + ' API Keys: ' + str(e)
                await self.my_msg(msg, to_broad=True)
        else:
            msg = 'No keys found for ' + ex
            await self.my_msg(msg)
    return need_keys


async def init_tele_bot(self, token, chat_id):
    if not self.tele_bot:
        self.tele_bot = TeleBot(token, chat_id, self)
        await self.tele_bot.set_commands()
        await self.tele_bot.set_dispatcher()
    else:
        self.tele_bot.token = token
        self.tele_bot.chat_id = chat_id
        await self.my_msg('Telegram Bot Activated', to_tele=True, to_broad=True)
