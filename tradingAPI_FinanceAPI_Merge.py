import os
import requests
from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError
import pandas as pd
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from dotenv import load_dotenv
import logging
import pytz

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Load environment variables
load_dotenv()

# eBay Trading API credentials
DEVID = os.getenv('DEVID')
APPID = os.getenv('APPID')
CERTID = os.getenv('CERTID')
TOKEN = os.getenv('TOKEN')

# eBay Finance API token
oauth_user_token = os.getenv('EBAY_OAUTH_USER_TOKEN')

if not all([DEVID, APPID, CERTID, TOKEN, oauth_user_token]):
    raise ValueError("One or more API credentials are missing.")

def prompt_for_year_and_month():
    current_year = datetime.now().year
    while True:
        try:
            year = int(input("Enter the year (e.g., 2024): "))
            if not (2020 <= year <= current_year):
                print(f"Invalid year. Please enter a year between 2020 and {current_year}.")
                continue

            month = int(input("Enter the month (1-12): "))
            if 1 <= month <= 12:
                return year, month
            else:
                print("Invalid month. Please enter a number between 1 and 12.")
        except ValueError:
            print("Invalid input. Please enter numeric values for year and month.")

def get_date_range(year, month):
    pacific = pytz.timezone('US/Pacific')
    start_date = pacific.localize(datetime(year, month, 1))
    if month == 12:
        end_date = pacific.localize(datetime(year + 1, 1, 1)) - timedelta(seconds=1)
    else:
        end_date = pacific.localize(datetime(year, month + 1, 1)) - timedelta(seconds=1)

    start_date_utc = start_date.astimezone(pytz.utc)
    end_date_utc = end_date.astimezone(pytz.utc)

    return start_date_utc.strftime('%Y-%m-%dT%H:%M:%S.000Z'), end_date_utc.strftime('%Y-%m-%dT%H:%M:%S.000Z')

def extract_decimal(transaction, key_path, default='0'):
    value = transaction
    for key in key_path:
        value = value.get(key, {})
    return Decimal(value.get('value', default)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)

def fetch_sold_items(start_date, end_date):
    try:
        api = Trading(domain='api.ebay.com', appid=APPID, devid=DEVID, certid=CERTID, token=TOKEN, config_file=None)
        response = api.execute('GetOrders', {
            'DetailLevel': 'ReturnAll',
            'CreateTimeFrom': start_date,
            'CreateTimeTo': end_date,
            'OrderStatus': 'Completed',
            'IncludeFinalValueFee': True
        })
        logging.info("API call successful. Response received.")
        return response.dict()
    except ConnectionError as e:
        logging.error(f"Connection error occurred: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return None

def process_sales_data(orders):
    if not orders:
        logging.info("No orders to process.")
        return pd.DataFrame()

    order_array = orders.get('OrderArray', {}).get('Order', [])
    items = []
    
    for order in order_array:
        for transaction in order.get('TransactionArray', {}).get('Transaction', []):
            item_price = extract_decimal(transaction, ['TransactionPrice'])
            shipping_cost = extract_decimal(transaction, ['ActualShippingCost'])
            sales_tax = extract_decimal(transaction, ['Taxes', 'TotalTaxAmount'])
            final_value_fee = extract_decimal(transaction, ['FinalValueFee'])
            handling_cost = extract_decimal(transaction, ['ActualHandlingCost'])

            sale_price = item_price + shipping_cost + sales_tax + handling_cost
            ad_fee = (sale_price * Decimal('0.02')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            insertion_fee = Decimal(0.30 if sale_price <= Decimal('10.00') else 0.40).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            # Calculate single net sale value considering all fees
            net_sale = (sale_price - sales_tax - final_value_fee - insertion_fee - shipping_cost - ad_fee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            item = {
                'OrderID': order['OrderID'],  # Include OrderID for matching
                'Title': transaction['Item']['Title'],
                'SalePrice': float(sale_price),
                'NetSale': float(net_sale),
                'COGS': ''  # Placeholder for COGS
            }
            items.append(item)
    
    return pd.DataFrame(items)

def get_promoted_listings_transactions(oauth_user_token, start_date, end_date):
    url = 'https://apiz.ebay.com/sell/finances/v1/transaction'
    headers = {
        'Authorization': f'Bearer {oauth_user_token}',
        'Content-Type': 'application/json',
        'X-EBAY-C-MARKETPLACE-ID': 'EBAY_US',
        'Accept': 'application/json'
    }
    params = {
        'limit': 100,
        'transactionDateRange': {
            'from': start_date,
            'to': end_date
        }
    }
    all_transactions = []

    while url:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            all_transactions.extend(data.get('transactions', []))
            url = data.get('next')
        else:
            print(f"Error fetching transactions: {response.status_code} - {response.text}")
            break

    return all_transactions

def filter_promoted_listing_fees(transactions):
    return [
        tx for tx in transactions 
        if tx.get('feeType') == 'AD_FEE' and tx.get('transactionType') == 'NON_SALE_CHARGE'
    ]

def match_orders_with_fees(trading_orders, promoted_listing_fees):
    order_fees = {}

    for index, order in trading_orders.iterrows():
        order_id = order.get('OrderID')
        order_fees[order_id] = {'order': order, 'fees': []}

        for fee in promoted_listing_fees:
            references = fee.get('references', [])
            for ref in references:
                if ref.get('referenceType') == 'ORDER_ID' and ref.get('referenceId') == order_id:
                    order_fees[order_id]['fees'].append(fee)

    return order_fees

def calculate_net_profit(order_fees):
    # Prepare a list to store the final data
    final_data = []

    for order_id, data in order_fees.items():
        order = data['order']
        fees = data['fees']

        total_fee_amount = sum(float(fee['amount']['value']) for fee in fees)
        order_total = float(order['SalePrice'])

        net_profit = order_total - total_fee_amount
        data['net_profit'] = net_profit

        # Append the needed fields to the final data list
        final_data.append({
            'Title': order['Title'],
            'SalePrice': order_total,
            'NetSale': net_profit,
            'COGS': ''  # Empty COGS as required
        })

    return final_data

if __name__ == "__main__":
    year, month = prompt_for_year_and_month()
    start_date, end_date = get_date_range(year, month)
    
    orders = fetch_sold_items(start_date, end_date)
    if not orders:
        logging.error("No orders retrieved.")
    else:
        sales_data_df = process_sales_data(orders)
        
        transactions = get_promoted_listings_transactions(oauth_user_token, start_date, end_date)
        if transactions:
            promoted_listing_fees = filter_promoted_listing_fees(transactions)
            order_fees = match_orders_with_fees(sales_data_df, promoted_listing_fees)
            results = calculate_net_profit(order_fees)
            
            # Convert the final data to a DataFrame and write it to CSV
            results_df = pd.DataFrame(results)
            results_df.to_csv('proper_net_sale.csv', index=False)
            print("Data written to 'proper_net_sale.csv'")
        else:
            print("Failed to retrieve promoted listings transactions.")
