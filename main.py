# region imports
from AlgorithmImports import *
import pandas as pd
import random
import numpy as np
import string


# endregion


class TestStrategy(QCAlgorithm):
    def Initialize(self):
        # Set the start and end date for the backtest
        self.SetStartDate(2021, 1, 1)
        self.SetEndDate(2022, 1, 1)

        # Set the initial cash
        self.SetCash(100000)

        # Add Forex security
        self._symbol = self.add_forex("AUDUSD", Resolution.HOUR).symbol

        # Define take profit and stop loss
        self.take_profit = 0.003
        self.stop_loss = 0.001

        # Initialize data storage
        self.df = pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close"])

        # df for managing trades
        self.market_order_df = pd.DataFrame(
            columns=["Date", "Trade ID", "Order ID", "Type", "Status", "Price", "Quantity"])

        # Log initialization
        self.Debug("Algorithm initialized.")

    def OnData(self, slice: Slice) -> None:
        bar = slice.quote_bars.get(self._symbol)

        # Create a pandas Series from the TradeBar
        candle = pd.Series({
            'Date': bar.Time,
            'Open': bar.Open,
            'High': bar.High,
            'Low': bar.Low,
            'Close': bar.Close,
        })

        # Add latest candle to df
        self.df = pd.concat([self.df, pd.DataFrame([candle])], ignore_index=True)

        # Check if the last three candles are bearish
        self.place_market_order(candle["Date"], candle["Close"], candle["Close"] + self.take_profit,
                                candle["Close"] - self.stop_loss, 1)

    def place_market_order(self, date, entry_price, take_profit_price, stop_loss_price, quantity):
        # Place entry order
        entry_ticket = self.MarketOrder(self._symbol, quantity)

        # Place SL and TP orders
        take_profit_ticket = self.LimitOrder(self._symbol, -quantity, take_profit_price)
        stop_loss_ticket = self.StopMarketOrder(self._symbol, -quantity, stop_loss_price)

        # Generates a random ID for the trade
        trade_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

        # Store market order details
        self.market_order_df.loc[len(self.market_order_df)] = [date, trade_id, entry_ticket.OrderId, "Entry",
                                                               "Not Filled", entry_price, quantity]

        # Store limit order details
        self.market_order_df.loc[len(self.market_order_df)] = [date, trade_id, take_profit_ticket.OrderId,
                                                               "Take Profit", "Not Filled", take_profit_price,
                                                               -quantity]

        # Store stop market order details
        self.market_order_df.loc[len(self.market_order_df)] = [date, trade_id, stop_loss_ticket.OrderId, "Stop Loss",
                                                               "Not Filled", stop_loss_price, -quantity]

    def OnOrderEvent(self, orderEvent):
        # Manage open trades as they are filled
        self.manage_open_trades(orderEvent)

    def manage_open_trades(self, orderEvent):
        # Get the row of the order that has been updated
        row_index = self.market_order_df[self.market_order_df['Order ID'] == orderEvent.OrderId].index

        if len(row_index) > 0 and orderEvent.Status == OrderStatus.Filled:
            self.market_order_df.at[row_index[0], "Status"] = "Take Profit Hit"

            if self.market_order_df.at[row_index[0], "Type"] != "Entry":

                # Get trade_id of the filled order
                trade_id = self.market_order_df.at[row_index[0], "Trade ID"]

                # Find related orders by Trade ID
                related_orders = self.market_order_df[self.market_order_df['Trade ID'] == trade_id]

                # If TP was hit, cancel SL and vice versa
                if self.market_order_df.at[row_index[0], "Type"] == "Take Profit":
                    sl_order_id = related_orders[related_orders['Type'] == 'Stop Loss']['Order ID'].values[0]
                    entry_order_id = related_orders[related_orders['Type'] == 'Entry']['Order ID'].values[0]

                    self.Transactions.CancelOrder(sl_order_id)
                    self.market_order_df.loc[self.market_order_df['Order ID'] == sl_order_id, 'Status'] = 'Canceled'
                    self.market_order_df.loc[self.market_order_df['Order ID'] == entry_order_id, 'Status'] = 'Filled'
                    self.market_order_df.loc[
                        self.market_order_df["Order ID"] == orderEvent.OrderId, "Status"] = "Take Profit Hit"
                    # self.Debug(f"Take Profit hit for Trade ID {trade_id}. Stop Loss order canceled.")

                elif self.market_order_df.at[row_index[0], "Type"] == "Stop Loss":
                    tp_order_id = related_orders[related_orders['Type'] == 'Take Profit']['Order ID'].values[0]
                    entry_order_id = related_orders[related_orders['Type'] == 'Entry']['Order ID'].values[0]

                    self.Transactions.CancelOrder(tp_order_id)
                    self.market_order_df.loc[self.market_order_df['Order ID'] == tp_order_id, 'Status'] = 'Canceled'
                    self.market_order_df.loc[self.market_order_df['Order ID'] == entry_order_id, 'Status'] = 'Filled'
                    self.market_order_df.loc[
                        self.market_order_df["Order ID"] == orderEvent.OrderId, "Status"] = "Stop Loss Hit"
                    # self.Debug(f"Stop Loss hit for Trade ID {trade_id}. Take Profit order canceled.")

    def OnEndOfAlgorithm(self):
        # Calculate total entries made
        total_entries = len(self.market_order_df[self.market_order_df['Type'] == 'Entry'])

        # Calculate winning trades
        winning_trades = len(self.market_order_df[
                                 (self.market_order_df['Type'] == 'Take Profit') &
                                 (self.market_order_df['Status'] == 'Take Profit Hit')
                                 ])

        # Calculate overall win rate
        win_rate = winning_trades / total_entries if total_entries > 0 else 0

        # Log the results
        self.Debug(f"Total Entries: {total_entries}")
        self.Debug(f"Winning Trades: {winning_trades}")
        self.Debug(f"Overall Win Rate: {win_rate:.2%}")

        # Additional Debugging Information
        losing_trades = len(self.market_order_df[
                                (self.market_order_df['Type'] == 'Stop Loss') &
                                (self.market_order_df['Status'] == 'Stop Loss Hit')
                                ])
        self.Debug(f"Losing Trades: {losing_trades}")