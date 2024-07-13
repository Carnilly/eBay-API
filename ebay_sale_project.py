import os
from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError
import pandas as pd
from datetime import datetime, timedelta

# Set connections to API
DEVID = '83320155-a15e-431e-94f9-2976795835ed'
APPID = 'BrendanC-Consignm-SBX-1961b5846-58ea4a9e'
CERTID = 'SBX-961b58464da0-5445-44fc-bf32-c6b7'
TOKEN = 'v^1.1#i^1#f^0#p^3#r^1#I^3#t^Ul4xMF8xMTpCMzIwQzFDMDlEOUYyMENDNDMyOTM2RDc3RjQ0NjdEQ18wXzEjRV4xMjg0'

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
        api = Trading(domain='api.sandbox.ebay.com', appid=APPID, devid=DEVID, certid=CERTID, token=TOKEN, config_file=None)
        response = api.execute('GetOrders', {
            'DetailLevel': 'ReturnAll',
            'ModTimeFrom': start_date,
            'ModTimeTo': end_date,
            'OrderStatus': 'Completed'
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
            item = {
                'Title': transaction['Item']['Title'],
                'SalePrice': float(transaction['TransactionPrice']['value']),
                'NetSale': float(transaction.get('ActualShippingCost', {}).get('value', 0)) + float(transaction.get('TransactionPrice', {}).get('value', 0)) - float(order.get('TotalTransactionFee', {}).get('value', 0))
            }
            items.append(item)
    df = pd.DataFrame(items)
    return df

# Example usage
year = 2024
month = 6
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
