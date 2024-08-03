import os
from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError
import pandas as pd
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

DEVID = os.getenv('DEVID')
APPID = os.getenv('APPID')
CERTID = os.getenv('CERTID')
TOKEN = os.getenv('TOKEN')

if not all([DEVID, APPID, CERTID, TOKEN]):
    raise ValueError("One or more API credentials are missing.")

def get_date_range(year, month):
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1) - timedelta(seconds=1)
    else:
        end_date = datetime(year, month + 1, 1) - timedelta(seconds=1)
    return start_date.strftime('%Y-%m-%dT%H:%M:%S.000Z'), end_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')

def get_sold_items(start_date, end_date):
    try:
        api = Trading(domain='api.ebay.com', appid=APPID, devid=DEVID, certid=CERTID, token=TOKEN, config_file=None)
        response = api.execute('GetOrders', {
            'DetailLevel': 'ReturnAll',
            'CreateTimeFrom': start_date,
            'CreateTimeTo': end_date,
            'OrderStatus': 'Completed',
            'IncludeFinalValueFee': True
        })
        print("API call successful. Response received.")  # Debugging statement
        return response.dict()
    except ConnectionError as e:
        print("Connection error:", e)
        print("Response:", e.response.dict() if e.response else "No response")
        return None
    except Exception as e:
        print("An unexpected error occurred:", e)
        return None

def process_sales_data(orders):
    if orders is None:
        print("No orders to process.")
        return pd.DataFrame()  # Return an empty DataFrame if orders are None

    order_array = orders.get('OrderArray')
    if order_array is None:
        print("OrderArray is None.")
        return pd.DataFrame()  # Return an empty DataFrame if OrderArray is None

    items = []
    for order in order_array.get('Order', []):
        for transaction in order.get('TransactionArray', {}).get('Transaction', []):
            item_price = Decimal(transaction['TransactionPrice']['value']).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            shipping_cost = Decimal(transaction.get('ActualShippingCost', {}).get('value', 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            sales_tax = Decimal(transaction.get('Taxes', {}).get('TotalTaxAmount', {}).get('value', 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            final_value_fee = Decimal(transaction.get('FinalValueFee', {}).get('value', 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            handling_cost = Decimal(transaction.get('ActualHandlingCost', {}).get('value', 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            # Calculate insertion fee
            insertion_fee = Decimal(0.30 if item_price <= Decimal('10.00') else 0.40).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            # Calculate ad fee at 2% of total price including handling cost
            total_price_with_handling = item_price + shipping_cost + sales_tax + handling_cost
            ad_fee = (total_price_with_handling * Decimal('0.02')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            # Calculate sale price and net sale without ad fee
            sale_price = (item_price + shipping_cost + sales_tax).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            net_sale_without_ad_fee = (sale_price - sales_tax - final_value_fee - insertion_fee - shipping_cost + handling_cost).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            # Calculate net sale with ad fee
            net_sale_with_ad_fee = (net_sale_without_ad_fee - ad_fee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            print(f"Title: {transaction['Item']['Title']}")
            print(f"Item Price: {item_price}, Shipping Cost: {shipping_cost}, Sales Tax: {sales_tax}")
            print(f"Final Value Fee: {final_value_fee}, Handling Cost: {handling_cost}, Insertion Fee: {insertion_fee}, Ad Fee: {ad_fee}")
            print(f"Calculation Details:")
            print(f"Sale Price = Item Price ({item_price}) + Shipping Cost ({shipping_cost}) + Sales Tax ({sales_tax}) = {sale_price}")
            print(f"Net Sale without Ad Fee = Sale Price ({sale_price}) - Sales Tax ({sales_tax}) - Final Value Fee ({final_value_fee}) - Insertion Fee ({insertion_fee}) - Shipping Cost ({shipping_cost}) + Handling Cost ({handling_cost}) = {net_sale_without_ad_fee}")
            print(f"Net Sale with Ad Fee = Net Sale without Ad Fee ({net_sale_without_ad_fee}) - Ad Fee ({ad_fee}) = {net_sale_with_ad_fee}")

            item = {
                'Title': transaction['Item']['Title'],
                'SalePrice': float(sale_price),
                'NetSaleWithoutAdFee': float(net_sale_without_ad_fee),
                'NetSaleWithAdFee': float(net_sale_with_ad_fee),
                'COGS': ''  # Placeholder for COGS
            }
            items.append(item)
    df = pd.DataFrame(items)
    return df

year = 2024
month = 7
start_date, end_date = get_date_range(year, month)
orders = get_sold_items(start_date, end_date)

if orders:
    print("Orders retrieved:", orders)  # Debugging statement
    sales_data_df = process_sales_data(orders)
    print("Sales data processed. DataFrame created.")  # Debugging statement
    sales_data_df.to_csv('sales_data.csv', index=False)
    print("Data exported to sales_data.csv")
else:
    print("Failed to retrieve orders.")
