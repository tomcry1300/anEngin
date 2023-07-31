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

import websockets
import asyncio
import json
import traceback


# Sockets for all of the Exchanges
async def websocket_bin(self):
    while self.running:
        try:
            # outer loop restarted every time the connection fails
            await self.my_msg('Connecting to Binance Websocket...', to_broad=True, to_tele=True)
            websocket = await websockets.connect("wss://stream.binance.com:9443/ws/!ticker@arr")
            test = await websocket.send('{"method": "SUBSCRIBE", "params": ["!ticker@arr"], "id": 1}')
            try:
                await self.my_msg('Connected to Binance.', to_broad=True, to_tele=True)
                while self.running:
                    # listener loop
                    try:
                        message = await websocket.recv()
                        message = json.loads(message)
                        try:
                            for msg in message:
                                if not msg in ['result', 'id']:
                                    self.a_binance.prices[msg['s']] = msg['c']
                        except Exception as e:
                            await self.my_msg('Binance Websocket Error: ' + str(e), to_tele=True, to_broad=True)
                    except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                        await asyncio.sleep(1)
                        break  # inner loop

                    if not self.a_binance.socket_connected:
                        self.a_binance.socket_connected = True

            except ConnectionRefusedError:
                await self.my_msg('Binance Connection Refused: ' + str(e), to_tele=True, to_broad=True)
            await asyncio.sleep(5)
        except Exception as e:
            await self.my_msg('Binance Websocket Secondary Error: ' + str(e), to_tele=True, to_broad=True)
            await asyncio.sleep(5)


async def websocket_binUS(self):
    while self.running:
        try:
            # outer loop restarted every time the connection fails
            await self.my_msg('Connecting to Binance US Websocket...', to_broad=True, to_tele=True)
            websocket = await websockets.connect("wss://stream.binance.us:9443/ws/!ticker@arr")
            test = await websocket.send('{"method": "SUBSCRIBE", "params": ["!ticker@arr"], "id": 1}')
            try:
                await self.my_msg('Connected to Binance US.', to_broad=True, to_tele=True)
                while self.running:
                    # listener loop
                    try:
                        message = await websocket.recv()
                        message = json.loads(message)
                        try:
                            for msg in message:
                                if not msg in ['result', 'id']:
                                    self.a_binanceUS.prices[msg['s']] = msg['c']
                        except Exception as e:
                            await self.my_msg('Binance US Websocket Error: ' + str(e) + ': ' + str(msg), to_tele=True, to_broad=True)
                    except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                        await asyncio.sleep(1)
                        break  # inner loop

                    if not self.a_binanceUS.socket_connected:
                        self.a_binanceUS.socket_connected = True
            except ConnectionRefusedError:
                await self.my_msg('Binance US Connection Refused: ' + str(e), to_tele=True, to_broad=True)
            await asyncio.sleep(5)
        except Exception as e:
            await self.my_msg('Binance US Websocket Secondary Error: ' + str(e), to_tele=True, to_broad=True)
            await asyncio.sleep(5)


async def websocket_bm(self):
    while self.running:
        try:
            # outer loop restarted every time the connection fails
            await self.my_msg('Connecting to BitMEX Websocket...', to_broad=True, to_tele=True)
            websocket = await websockets.connect("wss://ws.bitmex.com/realtime/?subscribe=trade")
            # test = await websocket.send('{"method": "SUBSCRIBE", "params": ["!ticker@arr"], "id": 1}')
            try:
                await self.my_msg('Connected to BitMEX.', to_broad=True, to_tele=True)
                while self.running:
                    # listener loop
                    try:
                        message = await websocket.recv()
                        message = json.loads(message)
                        try:
                            if 'data' in message.keys():
                                for msg in message['data']:
                                    self.a_bitmex.prices[msg['symbol']] = msg['price']
                        except Exception as e:
                            await self.my_msg('BitMEX Websocket Error: ' + str(e), to_tele=True, to_broad=True)
                    except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                        await asyncio.sleep(1)
                        break  # inner loop
                        # do stuff with reply object
                    if not self.a_bitmex.socket_connected:
                        self.a_bitmex.socket_connected = True
            except ConnectionRefusedError:
                await self.my_msg('BitMEX Connection Refused: ' + str(e), to_tele=True, to_broad=True)
            await asyncio.sleep(5)
        except Exception as e:
            await self.my_msg('BitMEX US Websocket Secondary Error: ' + str(e), to_tele=True, to_broad=True)
            await asyncio.sleep(5)


async def websocket_cbp(self):
    while self.running:
        try:
            # outer loop restarted every time the connection fails
            await self.my_msg('Connecting to Coinbase Pro Websocket...', to_broad=True, to_tele=True)
            cbp_sym = str(['"{}"'.format(t) for t in self.a_cbp.markets]).replace("'", "").replace('/', '-')
            cbp_msg = '{"type": "subscribe", "product_ids":' + str(cbp_sym) + ', "channels": ["ticker", "heartbeat"]}'
            websocket = await websockets.connect("wss://ws-feed.pro.coinbase.com/")
            test = await websocket.send(cbp_msg)
            try:
                await self.my_msg('Connected to Coinbase Pro.', to_broad=True, to_tele=True)
                while self.running:
                    # listener loop
                    try:
                        await asyncio.sleep(0)
                        message = await websocket.recv()
                        # print(len(message), message)
                        try:
                            message = json.loads(message)
                            if message['type'] == 'ticker':
                                self.a_cbp.prices[message['product_id'].replace('-', '')] = message['price']
                        except Exception as e:
                            if message:
                                await self.my_msg('Coinbase Pro Websocket Error: ' + str(e), to_tele=True, to_broad=True)
                    except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                        await asyncio.sleep(1)
                        break  # inner loop

                    if not self.a_cbp.socket_connected:
                        self.a_cbp.socket_connected = True
            except ConnectionRefusedError:
                await self.my_msg('Coinbase Pro Connection Refused: ' + str(e), to_tele=True, to_broad=True)
            await asyncio.sleep(5)
        except Exception as e:
            await self.my_msg('Coinbase Pro Websocket Secondary Error: ' + str(e), to_tele=True, to_broad=True)
            await asyncio.sleep(5)


async def websocket_ftx(self):
    while self.running:
        try:
            # outer loop restarted every time the connection fails
            await self.my_msg('Connecting to FTX Websocket...', to_broad=True, to_tele=True)
            ftx_sym = [t for t in self.a_ftx.markets]
            ftx_msg = []
            for sym in ftx_sym:
                ftx_msg.append('{"op": "subscribe", "channel": "ticker", "market": "' + str(sym) + '"}')
            websocket = await websockets.connect("wss://ftx.com/ws/")
            for msg in ftx_msg:
                test = await websocket.send(msg)
            try:
                await self.my_msg('Connected to FTX.', to_broad=True, to_tele=True)
                while self.running:
                    # listener loop
                    try:
                        message = await websocket.recv()
                        try:
                            message = json.loads(message)
                            if 'data' in message:
                                self.a_ftx.prices[message['market'].replace('-', '').replace('/', '')] = message['data']['last']
                        except Exception as e:
                            await self.my_msg('FTX Websocket Error: ' + str(e), to_tele=True, to_broad=True)
                    except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                        await asyncio.sleep(1)
                        break  # inner loop, try reconnect

                    if not self.a_ftx.socket_connected:
                        self.a_ftx.socket_connected = True

            except ConnectionRefusedError:
                await self.my_msg('FTX Connection Refused: ' + str(e), to_tele=True, to_broad=True)
            await asyncio.sleep(5)
        except Exception as e:
            await self.my_msg('FTX Websocket Secondary Error: ' + str(e), to_tele=True, to_broad=True)
            await asyncio.sleep(5)


async def websocket_kraken(self):
    while self.running:
        try:
            # outer loop restarted every time the connection fails
            await self.my_msg('Connecting to Kraken Websocket...', to_broad=True, to_tele=True)
            kraken_syms = [t for t in self.a_kraken.markets]
            kraken_msg = []#['{"event":"subscribe", "subscription":{"name":"ticker"}, "pair":["BTC/USD"]}']
            i = 0
            j = i + 20
            while j < len(kraken_syms):
                if j >= len(kraken_syms):
                    j = len(kraken_syms) - 1

                kraken_sym = str(['"{}"'.format(t) for t in kraken_syms[i:j]]).replace("'", "")
                kraken_msg.append('{"event":"subscribe", "subscription":{"name":"ticker"}, "pair":' + kraken_sym + '}')
                i = j + 1
                j = i + 20

            # kraken_sym = str(['"{}"'.format(t) for t in self.a_kraken.markets]).replace("'", "")
            # kraken_msg = '{"event":"subscribe", "subscription":{"name":"ticker"}, "pair":' + str(kraken_sym) + '}'

            websocket = await websockets.connect("wss://ws.kraken.com/")
            # print('kraken', websocket)
            for msg in kraken_msg:
                # print(msg)
                test = await websocket.send(msg)
            # test = await websocket.send(kraken_msg)
            #     print('kraken test', test)
            try:
                await self.my_msg('Connected to Kraken.', to_broad=True, to_tele=True)
                while self.running:
                    # listener loop
                    try:
                        message = await websocket.recv()
                        try:
                            message = json.loads(message)
                            if isinstance(message, list):
                                self.a_kraken.prices[message[3].replace('/', '').replace('XBT', 'BTC')] = message[1]['c'][0]
                                # print(self.a_kraken.prices)
                            # print('kraken', message)
                        except Exception as e:
                            await self.my_msg('Kraken Websocket Error: ' + str(e), to_tele=True, to_broad=True)
                    except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed) as e:
                        await self.my_msg(f'Kraken Websocket Secondary Error: {str(e)}. Attempting to reconnect...',
                                          to_tele=True, to_broad=True)
                        await asyncio.sleep(5)
                        break  # inner loop

                    if not self.a_kraken.socket_connected:
                        self.a_kraken.socket_connected = True
            except ConnectionRefusedError as e:
                # log something else
                await self.my_msg('Kraken Connection Refused: ' + str(e), to_tele=True, to_broad=True)
            await asyncio.sleep(5)
        except Exception as e:
            await self.my_msg('Kraken Websocket Tertiary Error: ' + str(e), to_tele=True, to_broad=True)
            if '1013' in str(e):
                await self.my_msg('Retrying connection in 5 minutes...', to_tele=True, to_broad=True)
                await asyncio.sleep(295)
            await asyncio.sleep(5)



