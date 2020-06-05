#!/usr/bin/env python3
"""
Simple command line client into RPC commands
Can be used as an alternate to Telegram

Should not import anything from freqtrade,
so it can be used as a standalone script.
"""
import time
import tweepy
import argparse
import inspect
import sqlite3
import re
import logging
import sys
from pathlib import Path
from urllib.parse import urlencode, urlparse, urlunparse

import json
import requests
from requests.exceptions import ConnectionError

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ft_rest_client")


class FtRestClient:
    def __init__(self, serverurl, username=None, password=None):

        self._serverurl = serverurl
        self._session = requests.Session()
        self._session.auth = (username, password)

    def _call(self, method, apipath, params: dict = None, data=None, files=None):

        if str(method).upper() not in ("GET", "POST", "PUT", "DELETE"):
            raise ValueError("invalid method <{0}>".format(method))
        basepath = f"{self._serverurl}/api/v1/{apipath}"

        hd = {"Accept": "application/json", "Content-Type": "application/json"}

        # Split url
        schema, netloc, path, par, query, fragment = urlparse(basepath)
        # URLEncode query string
        query = urlencode(params) if params else ""
        # recombine url
        url = urlunparse((schema, netloc, path, par, query, fragment))

        try:
            resp = self._session.request(method, url, headers=hd, data=json.dumps(data))
            # return resp.text
            return resp.json()
        except ConnectionError:
            logger.warning("Connection error")

    def _get(self, apipath, params: dict = None):
        return self._call("GET", apipath, params=params)

    def _post(self, apipath, params: dict = None, data: dict = None):
        return self._call("POST", apipath, params=params, data=data)

    def start(self):
        """Start the bot if it's in the stopped state.

        :return: json object
        """
        return self._post("start")

    def stop(self):
        """Stop the bot. Use `start` to restart.

        :return: json object
        """
        return self._post("stop")

    def stopbuy(self):
        """Stop buying (but handle sells gracefully). Use `reload_conf` to reset.

        :return: json object
        """
        return self._post("stopbuy")

    def reload_conf(self):
        """Reload configuration.

        :return: json object
        """
        return self._post("reload_conf")

    def balance(self):
        """Get the account balance.

        :return: json object
        """
        return self._get("balance")

    def count(self):
        """Return the amount of open trades.

        :return: json object
        """
        return self._get("count")

    def daily(self, days=None):
        """Return the amount of open trades.

        :return: json object
        """
        return self._get("daily", params={"timescale": days} if days else None)

    def edge(self):
        """Return information about edge.

        :return: json object
        """
        return self._get("edge")

    def profit(self):
        """Return the profit summary.

        :return: json object
        """
        return self._get("profit")

    def performance(self):
        """Return the performance of the different coins.

        :return: json object
        """
        return self._get("performance")

    def status(self):
        """Get the status of open trades.

        :return: json object
        """
        return self._get("status")

    def version(self):
        """Return the version of the bot.

        :return: json object containing the version
        """
        return self._get("version")

    def show_config(self):
        """
        Returns part of the configuration, relevant for trading operations.
        :return: json object containing the version
        """
        return self._get("show_config")

    def trades(self, limit=None):
        """Return trades history.

        :param limit: Limits trades to the X last trades. No limit to get all the trades.
        :return: json object
        """
        return self._get("trades", params={"limit": limit} if limit else 0)

    def whitelist(self):
        """Show the current whitelist.

        :return: json object
        """
        return self._get("whitelist")

    def blacklist(self, *args):
        """Show the current blacklist.

        :param add: List of coins to add (example: "BNB/BTC")
        :return: json object
        """
        if not args:
            return self._get("blacklist")
        else:
            return self._post("blacklist", data={"blacklist": args})

    def forcebuy(self, pair, price=None):
        """Buy an asset.

        :param pair: Pair to buy (ETH/BTC)
        :param price: Optional - price to buy
        :return: json object of the trade
        """
        data = {"pair": pair, "price": price}
        return self._post("forcebuy", data=data)

    def forcesell(self, tradeid):
        """Force-sell a trade.

        :param tradeid: Id of the trade (can be received via status command)
        :return: json object
        """

        return self._post("forcesell", data={"tradeid": tradeid})


def add_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        help="Positional argument defining the command to execute.",
        nargs="?",
    )

    parser.add_argument(
        "--show",
        help="Show possible methods with this client",
        dest="show",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "-c",
        "--config",
        help="Specify configuration file (default: %(default)s). ",
        dest="config",
        type=str,
        metavar="PATH",
        default="config.json",
    )

    parser.add_argument(
        "command_arguments",
        help="Positional arguments for the parameters for [command]",
        nargs="*",
        default=[],
    )

    args = parser.parse_args()
    return vars(args)


def load_config(configfile):
    file = Path(configfile)
    if file.is_file():
        with file.open("r") as f:
            config = json.load(f)
        return config
    else:
        logger.warning(f"Could not load config file {file}.")
        sys.exit(1)


def print_commands():
    # Print dynamic help for the different commands using the commands doc-strings
    client = FtRestClient(None)
    print("Possible commands:\n")
    for x, y in inspect.getmembers(client):
        if not x.startswith("_"):
            doc = re.sub(
                ":return:.*", "", getattr(client, x).__doc__, flags=re.MULTILINE
            ).rstrip()
            print(f"{x}\n\t{doc}\n")


def percentage(part, whole):
    return "%.2f" % (100 * float(part) / float(whole))


def tweet(config, output_profit, output_daily_data, starting_capital, position_size):
    print("Tweeting...")
    api_key = config.get("api_server", {}).get("api_key")
    api_secret_key = config.get("api_server", {}).get("api_secret_key")
    access_token = config.get("api_server", {}).get("access_token")
    access_token_secret = config.get("api_server", {}).get("access_token_secret")

    auth = tweepy.OAuthHandler(api_key, api_secret_key)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth)

    composed = []
    # composed.append(f"Profit open: {int(output_profit['profit_all_coin'])} USDT ({percentage(output_profit['profit_all_coin'], starting_capital)}%)")
    # composed.append(f"Profit closed: {int(output_profit['profit_closed_coin'])} USDT ({percentage(output_profit['profit_closed_coin'], starting_capital)}%)")

    closed_profit_today = percentage(output_daily_data["abs_profit"], starting_capital)
    closed_profit_percentage_total = percentage(
        output_profit["profit_closed_coin"], starting_capital
    )
    open_profit_percentage_total = percentage(
        output_profit["profit_all_coin"], starting_capital
    )
    current_capital = starting_capital + float(output_profit["profit_closed_coin"])
    position_size = percentage(position_size, current_capital)
    best_pair_profit_percentage = percentage(
        output_profit["best_rate"], starting_capital
    )

    composed.append(
        f"Closed profit today ({output_daily_data['date']}): {closed_profit_today}%"
    )
    composed.append(f"Trades today: {output_daily_data['trade_count']}")
    composed.append(
        f"Open/closed total profit: {open_profit_percentage_total}%/{closed_profit_percentage_total}%"
    )
    composed.append(f"Position size: {position_size}%")
    # composed.append(f"Best performer: {output_profit['best_pair']} ({output_profit['best_rate']} USDT)")
    composed.append(
        f"Best: {output_profit['best_pair']} ({best_pair_profit_percentage}%)"
    )
    composed.append(
        f"All trades/closed: {output_profit['trade_count']}/{output_profit['closed_trade_count']}"
    )
    composed.append(f"Last action: {output_profit['latest_trade_date']}")
    composed.append(f"Average trade duration: {output_profit['avg_duration']}")

    to_tweet = "\n".join(composed)
    print(to_tweet)
    api.update_status(to_tweet)


def db_save(config, output_profit, output_daily_data, starting_capital, position_size):
    print("Saving to database...")
    closed_profit_today = percentage(output_daily_data["abs_profit"], starting_capital)
    closed_profit_percentage_total = percentage(
        output_profit["profit_closed_coin"], starting_capital
    )
    open_profit_percentage_total = percentage(
        output_profit["profit_all_coin"], starting_capital
    )
    current_capital = starting_capital + float(output_profit["profit_closed_coin"])
    position_size = percentage(position_size, current_capital)
    best_pair_profit_percentage = percentage(
        output_profit["best_rate"], starting_capital
    )

    timestamp = time.time()

    SQL_CREATE = (
        "CREATE TABLE IF NOT EXISTS trades ( "
        "`timestamp` NUMERIC,"
        " `day` TEXT, "
        "`closed_profit_today` NUMERIC, "
        "`trades_today` NUMERIC, "
        "`closed_profit_percentage_total` NUMERIC, "
        "`open_profit_percentage_total` NUMERIC, "
        "`position_size` NUMERIC, "
        "`best_pair` TEXT, "
        "`best_pair_profit_percentage` TEXT, "
        "`all_trades` NUMERIC, "
        "`closed_trades` NUMERIC, "
        "`last_action` TEXT, "
        "`average_duration` TEXT "
        ")"
    )

    connection = sqlite3.connect("history.db")
    cursor = connection.cursor()

    connection.execute(SQL_CREATE)
    connection.commit()
    connection.execute(
        "INSERT INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            timestamp,
            output_daily_data["date"],
            closed_profit_today,
            output_daily_data["trade_count"],
            closed_profit_percentage_total,
            open_profit_percentage_total,
            position_size,
            best_pair_profit_percentage,
            output_profit["best_pair"],
            output_profit["trade_count"],
            output_profit["closed_trade_count"],
            output_profit["latest_trade_date"],
            output_profit["avg_duration"],
        ),
    )
    connection.commit()


def main(args):

    if args.get("show"):
        print_commands()
        sys.exit()

    server_url = f"http://{url}:{port}"
    client = FtRestClient(server_url, username, password)

    # m = [x for x, y in inspect.getmembers(client) if not x.startswith('_')]

    output_profit = getattr(client, "profit")(*args["command_arguments"])
    output_daily = getattr(client, "daily")(*args["command_arguments"])
    output_daily_data = output_daily["data"][0]  # [0] selects only the last day

    if send_tweet:
        tweet(
            config=config,
            output_profit=output_profit,
            output_daily_data=output_daily_data,
            starting_capital=starting_capital,
            position_size=position_size,
        )

    if save_to_db:
        db_save(
            config=config,
            output_profit=output_profit,
            output_daily_data=output_daily_data,
            starting_capital=starting_capital,
            position_size=position_size,
        )


if __name__ == "__main__":
    args = add_arguments()

    config = load_config(args["config"])
    url = config.get("api_server", {}).get("server_url")
    port = config.get("api_server", {}).get("listen_port")
    username = config.get("api_server", {}).get("username")
    password = config.get("api_server", {}).get("password")
    save_to_db = config.get("api_server", {}).get("save_to_db")
    send_tweet = config.get("api_server", {}).get("send_tweet")
    starting_capital = config.get("api_server", {}).get("starting_capital")
    position_size = config.get("api_server", {}).get("position_size")
    run_interval = config.get("api_server", {}).get("run_interval")

    print(f"Database saving configured to {save_to_db}")
    print(f"Tweeting configured to {send_tweet}")

    while True:
        try:
            main(args)
            print(f"Sleeping for {run_interval/60} minutes")
        except Exception as e:
            print(f"An error occurred: {e}, skipping run")
        finally:
            time.sleep(run_interval)
