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

    return start_date_utc.strftime('%Y-%m-%dT%H:%M:%S.%fZ'), end_date_utc.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

def extract_decimal(data, key_path, default='0'):
    value = data
    for key in key_path:
        value = value.get(key, {})
    return Decimal(value.get('value', default)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

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
        order_id = order['OrderID']
        for transaction in order.get('TransactionArray', {}).get('Transaction', []):
            quantity = int(transaction.get('QuantityPurchased', 1))
            item_price = extract_decimal(transaction, ['TransactionPrice'])

            # Extract total costs and calculate per-unit values
            total_shipping_cost = extract_decimal(transaction, ['ActualShippingCost'])
            total_sales_tax = extract_decimal(transaction, ['Taxes', 'TotalTaxAmount'])
            total_final_value_fee = extract_decimal(transaction, ['FinalValueFee'])
            total_handling_cost = extract_decimal(transaction, ['ActualHandlingCost'])

            per_unit_shipping_cost = (total_shipping_cost / quantity).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if quantity else Decimal('0.00')
            per_unit_sales_tax = (total_sales_tax / quantity).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if quantity else Decimal('0.00')
            per_unit_final_value_fee = (total_final_value_fee / quantity).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if quantity else Decimal('0.00')
            per_unit_handling_cost = (total_handling_cost / quantity).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if quantity else Decimal('0.00')

            # Calculate per-unit sale price and net sale
            per_unit_sale_price = (item_price + per_unit_shipping_cost + per_unit_sales_tax + per_unit_handling_cost).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            insertion_fee = Decimal(0.30 if per_unit_sale_price <= Decimal('10.00') else 0.40).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            net_sale_without_ad_fee = (per_unit_sale_price - per_unit_sales_tax - per_unit_final_value_fee - insertion_fee - per_unit_shipping_cost).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            # Create a separate row for each individual item in the transaction
            for _ in range(quantity):
                items.append({
                    'OrderID': order_id,
                    'Title': transaction['Item']['Title'],
                    'SalePrice': float(per_unit_sale_price),
                    'NetSaleWithoutAdFee': float(net_sale_without_ad_fee),
                    'FinalValueFee': float(per_unit_final_value_fee),
                    'InsertionFee': float(insertion_fee),
                    'ShippingCost': float(per_unit_shipping_cost),
                    'HandlingCost': float(per_unit_handling_cost),
                    'SalesTax': float(per_unit_sales_tax),
                    'COGS': ''  # Placeholder for COGS
                })

    return pd.DataFrame(items)

def get_finance_transactions(oauth_user_token, start_date, end_date, transaction_type, fee_type=None):
    base_url = 'https://apiz.ebay.com/sell/finances/v1/transaction'
    headers = {
        'Authorization': f'Bearer {oauth_user_token}',
        'Accept': 'application/json',
        'X-EBAY-C-MARKETPLACE-ID': 'EBAY_US'
    }
    params = {
        'limit': '1000',
        'transactionDateRangeFrom': start_date,
        'transactionDateRangeTo': end_date,
        'transactionType': transaction_type
    }
    if fee_type:
        params['feeType'] = fee_type

    all_transactions = []
    url = base_url

    while True:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            all_transactions.extend(data.get('transactions', []))
            next_page = None
            for link in data.get('links', []):
                if link.get('rel') == 'next':
                    next_page = link.get('href')
                    break
            if next_page:
                url = next_page
                params = {}
            else:
                break
        else:
            logging.error(f"Error fetching transactions: {response.status_code} - {response.text}")
            break

    return all_transactions

def get_ad_fees_dataframe(transactions):
    ad_fees = []
    for tx in transactions:
        order_id = None
        for ref in tx.get('references', []):
            if ref.get('referenceType') == 'ORDER_ID':
                order_id = ref.get('referenceId')
                break
        if order_id:
            ad_fee = Decimal(tx.get('amount', {}).get('value', '0')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            ad_fees.append({
                'OrderID': order_id,
                'AdFee': float(ad_fee)
            })
    return pd.DataFrame(ad_fees)

if __name__ == "__main__":
    year, month = prompt_for_year_and_month()
    start_date, end_date = get_date_range(year, month)
    
    orders = fetch_sold_items(start_date, end_date)
    if not orders:
        logging.error("No orders retrieved.")
    else:
        sales_data_df = process_sales_data(orders)
        
        ad_transactions = get_finance_transactions(
            oauth_user_token, start_date, end_date,
            transaction_type='NON_SALE_CHARGE',
            fee_type='AD_FEE'
        )
        ad_fees_df = get_ad_fees_dataframe(ad_transactions) if ad_transactions else pd.DataFrame(columns=['OrderID', 'AdFee'])
        
        merged_df = pd.merge(sales_data_df, ad_fees_df, on='OrderID', how='left')
        merged_df['AdFee'] = merged_df['AdFee'].fillna(0)
        
        merged_df['NetSale'] = merged_df.apply(
            lambda row: Decimal(row['NetSaleWithoutAdFee'] - row['AdFee']).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            axis=1
        ).astype(float)
        
        # Drop 'OrderID' from the final output
        merged_df = merged_df[['Title', 'SalePrice', 'NetSale', 'COGS']]
        merged_df.to_csv('proper_net_sale.csv', index=False)
        print("Data written to 'proper_net_sale.csv'")
