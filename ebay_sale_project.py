import os
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

DEVID = os.getenv('DEVID')
APPID = os.getenv('APPID')
CERTID = os.getenv('CERTID')
TOKEN = os.getenv('TOKEN')

if not all([DEVID, APPID, CERTID, TOKEN]):
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
    """
    Generates a start and end date range for the given year and month,
    localized to Pacific Time, and converts them to UTC for the API request.
    """
    pacific = pytz.timezone('US/Pacific')

    # Localize the start and end dates to Pacific Time
    start_date = pacific.localize(datetime(year, month, 1))
    if month == 12:
        end_date = pacific.localize(datetime(year + 1, 1, 1)) - timedelta(seconds=1)
    else:
        end_date = pacific.localize(datetime(year, month + 1, 1)) - timedelta(seconds=1)

    # Convert to UTC
    start_date_utc = start_date.astimezone(pytz.utc)
    end_date_utc = end_date.astimezone(pytz.utc)

    # Format the dates in ISO 8601 format with 'Z' to indicate UTC
    return start_date_utc.strftime('%Y-%m-%dT%H:%M:%S.000Z'), end_date_utc.strftime('%Y-%m-%dT%H:%M:%S.000Z')


def extract_decimal(transaction, key_path, default='0'):
    """
    Helper function to extract and convert decimal values from nested dictionaries.
    
    Args:
    transaction (dict): The transaction dictionary to extract the value from.
    key_path (list): A list of keys to navigate through the nested dictionaries.
    default (str): The default value to use if any key is not found.

    Returns:
    Decimal: The extracted and rounded decimal value.
    """
    value = transaction  # Start with the entire transaction dictionary
    for key in key_path:
        value = value.get(key, {})  # Traverse through each level using keys in key_path
    # After traversing, get the final 'value' and convert it to Decimal
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
        logging.warning("No orders to process.")
        return pd.DataFrame()

    order_array = orders.get('OrderArray', {}).get('Order', [])
    items = []
    
    for order in order_array:
        for transaction in order.get('TransactionArray', {}).get('Transaction', []):
            # Use extract_decimal to simplify getting each value
            item_price = extract_decimal(transaction, ['TransactionPrice'])
            shipping_cost = extract_decimal(transaction, ['ActualShippingCost'])
            sales_tax = extract_decimal(transaction, ['Taxes', 'TotalTaxAmount'])
            final_value_fee = extract_decimal(transaction, ['FinalValueFee'])
            handling_cost = extract_decimal(transaction, ['ActualHandlingCost'])
            
            # Calculate ad fee at 2% of total price including handling cost
            sale_price = item_price + shipping_cost + sales_tax + handling_cost
            ad_fee = (sale_price * Decimal('0.02')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            insertion_fee = Decimal(0.30 if sale_price <= Decimal('10.00') else 0.40).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            # Calculate sale price and net sale without ad fee
            net_sale_without_ad_fee = (sale_price - sales_tax - final_value_fee - insertion_fee - shipping_cost).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            # Calculate net sale with ad fee
            net_sale_with_ad_fee = (net_sale_without_ad_fee - ad_fee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            logging.info(f"Title: {transaction['Item']['Title']}")
            logging.info(f"Item Price: {item_price}, Shipping Cost: {shipping_cost}, Sales Tax: {sales_tax}")
            logging.info(f"Final Value Fee: {final_value_fee}, Handling Cost: {handling_cost}, Insertion Fee: {insertion_fee}, Ad Fee: {ad_fee}")
            logging.info(f"Calculation Details:")
            logging.info(f"Sale Price = Item Price ({item_price}) + Shipping Cost ({shipping_cost}) + Sales Tax ({sales_tax}) = {sale_price}")
            logging.info(f"Net Sale without Ad Fee = Sale Price ({sale_price}) - Sales Tax ({sales_tax}) - Final Value Fee ({final_value_fee}) - Insertion Fee ({insertion_fee}) - Shipping Cost ({shipping_cost}) + Handling Cost ({handling_cost}) = {net_sale_without_ad_fee}")
            logging.info(f"Net Sale with Ad Fee = Net Sale without Ad Fee ({net_sale_without_ad_fee}) - Ad Fee ({ad_fee}) = {net_sale_with_ad_fee}")

            # Create the dictionary for each item
            item = {
                'Title': transaction['Item']['Title'],
                'SalePrice': float(sale_price),
                'NetSaleWithoutAdFee': float(net_sale_without_ad_fee),
                'NetSaleWithAdFee': float(net_sale_with_ad_fee),
                'COGS': ''  # Placeholder for COGS
            }
            items.append(item)
    
    return pd.DataFrame(items)

if __name__ == "__main__":
    year, month = prompt_for_year_and_month()
    start_date, end_date = get_date_range(year, month)
    orders = fetch_sold_items(start_date, end_date)

    if orders:
        sales_data_df = process_sales_data(orders)
        sales_data_df.to_csv('sales_data.csv', index=False)
        print("Data exported to sales_data.csv")
    else:
        print("Failed to retrieve orders.")
