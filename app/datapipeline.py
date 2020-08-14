'''
Run this to get html files

This file contains code to obtain html data from oslo bors and yahoo finance
'''
import argparse
import re
import threading
import time
from pprint import pprint
from typing import List
import sys
import pathlib
import os

import numpy as np
import pandas as pd
import pypatconsole as ppc
from bs4 import BeautifulSoup as bs
from pandas import DataFrame, to_numeric
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from tqdm import tqdm

import config as cng
import yfinance_hotfix as yf
import utils

def dump_assert(file: str):
    assert file is not None, 'File parameter must be specified when dump=True'

def get_osebx_htmlfile(url: str, timeout: int=cng.DEFAULT_TIMEOUT, wait_target_class: str=None, 
                       verbose: int=1, dump: bool=True, file: str=None) -> str:
    '''Load OSEBX html files using selenium'''

    if verbose >= 1: print(f'Gathering data from {url}')

    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(options=chrome_options)
    if verbose >= 2: print('Initialized chromedriver')

    driver.get(url)

    if verbose >= 2: print('Waiting for target HTML class to appear')

    # If the webpage dynamically loads the table with the stock information. This code will force the webdriver
    # wait until the wanted element is loaded.
    if not wait_target_class is None:
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CLASS_NAME, wait_target_class))
            )
        except:
            print(f'Timeout: Could not load class {wait_target_class} from {url}')
            driver.quit()
            exit()

    if verbose >= 2: print('Element located')

    page_src = driver.page_source
    driver.quit()

    if dump:
        if verbose >= 1: print(f'Dumping HTML file: {file}')
        dump_assert(file)
        with open(file, 'w+') as file:
            file.write(page_src)

    return page_src

def get_osebx_htmlfiles():
    '''Get OSEBX HTML files'''
    get_osebx_htmlfile(url=cng.BORS_QUOTES_URL,
                       wait_target_class=cng.QUOTES_WAIT_TARGET_CLASS,
                       dump=True,
                       file=cng.QUOTES_HTML_DATE_FILE,
                       verbose=2)

    get_osebx_htmlfile(url=cng.BORS_RETURNS_URL,
                       wait_target_class=cng.RETURNS_WAIT_TARGET_CLASS,
                       dump=True,
                       file=cng.RETURNS_HTML_DATE_FILE,
                       verbose=2)

def scrape_osebx_html(quotes: str=None, returns: str=None, verbose: int=0, dump: bool=True, 
                      file: str=None) -> pd.DataFrame:
    '''
    Scrape stocks from oslo bors HTML files. 
    
    HTML of websites of quotes and returns 
    should be located in same folder this file. 

    quotes: https://www.oslobors.no/ob_eng/markedsaktivitet/#/list/shares/quotelist/ob/all/all/false
    returns: https://www.oslobors.no/ob_eng/markedsaktivitet/#/list/shares/return/ob/all/all/false
    '''
    if quotes is None:
        quotes = cng.QUOTES_HTML_FILE
    
    if returns is None:
        returns = cng.RETURNS_HTML_FILE
    
    with open(quotes) as html_source:
        soup_quotes = bs(html_source, 'html.parser')

    with open(returns) as html_source:
        soup_return = bs(html_source, 'html.parser')

    # Filter out the stock tables 
    html_quotes = soup_quotes.find('div', class_="ng-scope").find('ui-view').find('ui-view').find('tbody').find_all('tr')
    html_return = soup_return.find('div', class_="ng-scope").find('ui-view').find('ui-view').find('tbody').find_all('tr')
    
    tickers = []
    names = []
    lasts = []
    buys = []
    sells = []
    tradecounts = []
    marketcaps = []
    sectors = []
    infos = []
    profits_today = []
    profits_1wk = []
    profits_1month = []
    profits_ytd = []
    profits_1yr = []

    # Create lists with features. Only preprocessing for strings are done (values are all strings). 
    # Further preprocessing will be done later when the values are in a pandas DataFrame. 
    for quotesrow, returnrow in tqdm(zip(html_quotes, html_return), total=len(html_quotes), disable=verbose):
        # Scrape ticker, name, marketcap, sector and info. 
        tickers.append(quotesrow.a.text)
        names.append(quotesrow.find('td', {'data-header':'Navn'}).text)
        lasts.append(quotesrow.find('td', {'data-header':'Last'}).text.replace(',', ''))
        buys.append(quotesrow.find('td', {'data-header':'Buy'}).text.replace(',', ''))
        sells.append(quotesrow.find('td', {'data-header':'Sell'}).text.replace(',', ''))
        tradecounts.append(quotesrow.find('td', {'data-header':'No. of trades'}).text.replace(',', ''))
        marketcaps.append(quotesrow.find('td', {'data-header':'Market cap (MNOK)'}).text.replace(',', ''))
        # Marketcap unit is in millions, multiply by 10e6 to get normal values
        sectors.append(quotesrow.find('td', class_='icons').get('title'))
        # Info is whether instrument is a Liquidit y provider or not
        infos.append('LP' if 'fa-bolt' in quotesrow.find('td', class_='infoIcon').i.get('class') else np.nan)

        # Scrape return values
        # Values are percentages, and are currently in text form. Divide by 100 to get normal values
        profits_today.append(returnrow.find('td', class_='CHANGE_PCT_SLACK').text.replace('%', ''))
        profits_1wk.append(returnrow.find('td', class_='CHANGE_1WEEK_PCT_SLACK').text.replace('%', ''))
        profits_1month.append(returnrow.find('td', class_='CHANGE_1MONTH_PCT_SLACK').text.replace('%', ''))
        profits_ytd.append(returnrow.find('td', class_='CHANGE_YEAR_PCT_SLACK').text.replace('%', ''))
        profits_1yr.append(returnrow.find('td', class_='CHANGE_1YEAR_PCT_SLACK').text.replace('%', ''))

        if verbose >= 1:
            print(f'Ticker: {tickers[-1]}')
            print(f'Name: {names[-1]}')
            print(f'Last: {lasts[-1]}')
            print(f'Buy: {buys[-1]}')
            print(f'Sell: {sells[-1]}')
            print(f'Cap: {marketcaps[-1]}')
            print(f'Sector: {sectors[-1]}')
            print(f'Info: {infos[-1]}')
            print(f'Profit today: {profits_today[-1]}')
            print(f'Profit 1 week: {profits_1wk[-1]}')
            print(f'Profit 1 month: {profits_1month[-1]}')
            print(f'Profit YTD: {profits_ytd[-1]}')
            print(f'Profit 1 year: {profits_1yr[-1]}')
            print()

    df = DataFrame(dict(
        ticker=tickers,
        name=names,
        sector=sectors,
        last_=lasts, # DataFrame.last is a method, hence the underscore
        buy=buys,
        sell=sells,
        tradecount=tradecounts,
        info=infos,
        marketcap=marketcaps,
        profit_today=profits_today,
        profit_1wk=profits_1wk,
        profit_1month=profits_1month,
        profit_ytd=profits_ytd,
        profit_1yr=profits_1yr
    ))

    # Turn returns to floats then divide by 100 to convert from percentages to "numbers"
    columns_to_num = ['profit_today', 'profit_1wk', 'profit_1month', 'profit_ytd', 'profit_1yr']
    df[columns_to_num] = df[columns_to_num].apply(to_numeric, errors='coerce') / 100

    # Turn other things to numeric as well 
    # coerce turns missing or invalid values to nan
    df.last_ = to_numeric(df.last_, errors='coerce')
    df.buy = to_numeric(df.buy, errors='coerce')
    df.sell = to_numeric(df.sell, errors='coerce')
    df.tradecount = to_numeric(df.tradecount, errors='coerce')

    if dump:
        dump_assert(file)
        df.to_csv(file, index=False)

    return df

def yahoo_querier_(ticker: str, featdict: dict) -> None:
    '''
    Adds ticker information to dictionary inplace

    At the time of writing this code, Yahoo is acting retarded.
    For some reason MOWI, NEL etc and whatnot not properly indexed on Yahoo Finance.
    The Python scraper should work fine. 
    '''
    ticker_string = ticker.strip()+'.OL'
    ticker_string = re.sub('\s+','-',ticker_string)
    t = yf.Ticker(ticker_string)
    featdict[ticker] = t.info

    sys.stdout.write(f'{ticker_string} ')
    sys.stdout.flush()
    return

def get_yahoo_stats(tickers=None, verbose: int=1, dump: bool=True, file: str=None) -> pd.DataFrame:
    '''
    Get Yahoo stuff
    '''
    if tickers is None:
        tickers = pd.read_csv(cng.BORS_CSV_DATE_FILE).ticker

    featdict = dict()

    threads = [threading.Thread(target=yahoo_querier_, args=(ticker, featdict)) for ticker in tickers]

    if verbose >= 2: print('Starting threads\n')

    utils.run_threads(
        threads=threads,
        chunksize=20,
        start_interval=0.01,
        chunk_interval=1)

    if verbose >= 2: print('Creating dataframe')
    df = pd.DataFrame(featdict).T
    df.index.name = 'ticker'
    df.reset_index(inplace=True)

    if dump:
        if verbose >= 2: print('Dumping DataFrame')
        dump_assert(file)
        df.to_csv(file, index=False)

    if verbose >= 2: print('Returning dataframe')
    return df

def combine_osebx_yahoo(df_osebx: pd.DataFrame=None, df_yahoo: pd.DataFrame=None):
    '''
    Combine OSEBX and Yahoo datasets
    '''
    if df_osebx is None:
        df_osebx = pd.read_csv(cng.BORS_CSV_DATE_FILE)

    if df_yahoo is None:
        df_yahoo = pd.read_csv(cng.YAHOO_CSV_DATE_FILE)

    df_combined = pd.merge(df_osebx, df_yahoo, on=cng.MERGE_DFS_ON, suffixes=('_osebx', '_yahoo'))
    df_combined.set_index(cng.MERGE_DFS_ON, inplace=True)
    df_combined.to_csv(cng.DATASET_DATE_FILE)

def make_dirs():
    pathlib.Path(cng.DATA_DATE_DIR).mkdir(parents=True, exist_ok=True)

def run_datapipeline():
    '''
    Run whole datapipeline
    '''
    make_dirs()

    get_osebx_htmlfiles()

    df_osebx = scrape_osebx_html(quotes=cng.QUOTES_HTML_DATE_FILE, 
                                 returns=cng.RETURNS_HTML_DATE_FILE, 
                                 verbose=2, 
                                 dump=True, 
                                 file=cng.BORS_CSV_DATE_FILE)
    tickers = df_osebx.ticker

    df_yahoo = get_yahoo_stats(tickers=tickers, 
                               verbose=2, 
                               dump=True,
                               file=cng.YAHOO_CSV_DATE_FILE)

    combine_osebx_yahoo()
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--interactive', help='Run in interactive mode', action='store_true')
    args = parser.parse_args()

    if args.interactive:
        ppc.menu([
            get_osebx_htmlfiles,
            scrape_osebx_html,
            get_yahoo_stats,
            run_datapipeline,
        ], main=True, blank_proceedure='pass')
    else:
        run_datapipeline()
