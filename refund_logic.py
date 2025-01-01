import os
import requests
from dotenv import load_dotenv
import logging
import pandas as pd

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Load environment variables
load_dotenv()

# eBay Finance API token
oauth_user_token = os.getenv('EBAY_OAUTH_USER_TOKEN')
if not oauth_user_token:
    raise ValueError("eBay Finance API token is missing.")

def get_finance_transactions(oauth_user_token, start_date, end_date):
    """
    Fetches financial transactions using eBay Finance API.
    """
    base_url = 'https://apiz.ebay.com/sell/finances/v1/transaction'
    headers = {
        'Authorization': f'Bearer {oauth_user_token}',
        'Accept': 'application/json',
        'X-EBAY-C-MARKETPLACE-ID': 'EBAY_US'
    }
    params = {
        'limit': '1000',
        'transactionDateRangeFrom': start_date,
        'transactionDateRangeTo': end_date
    }
    all_transactions = []
    while True:
        response = requests.get(base_url, headers=headers, params=params)
        if response.status_code != 200:
            logging.error(f"Failed to fetch transactions: {response.status_code}, {response.text}")
            break

        data = response.json()
        transactions = data.get('transactions', [])
        all_transactions.extend(transactions)

        # Check if there's another page
        if 'next' in data.get('href', ''):
            params['offset'] = params.get('offset', 0) + int(params['limit'])
        else:
            break

    return pd.DataFrame(all_transactions)

def process_refund_transactions(df):
    """
    Filter and process only transactions that are related to refunds.
    """
    # Filter for REFUND transactions only
    refund_df = df[df['transactionType'] == 'REFUND']
    if refund_df.empty:
        logging.info("No refund transactions found for the specified period.")
        return None

    # Extract and format relevant fields
    refund_data = []
    for _, row in refund_df.iterrows():
        order_id = row.get('orderId', 'None')
        refund_amount = float(row['amount']['value'])
        refund_date = row['transactionDate']
        refund_type = row['transactionType']

        # Retrieve additional details if available
        fee_basis_amount = row.get('totalFeeBasisAmount', {}).get('value', 'None')
        total_fee = row.get('totalFeeAmount', {}).get('value', 'None')
        line_items = row.get('orderLineItems', [])
        references = row.get('references', [])

        # Collect refund details for output
        refund_data.append({
            'OrderID': order_id,
            'RefundAmount': refund_amount,
            'RefundDate': refund_date,
            'RefundType': refund_type,
            'TotalFeeBasis': fee_basis_amount,
            'TotalFee': total_fee,
            'LineItems': line_items,
            'References': references
        })

    # Convert to DataFrame for better display
    return pd.DataFrame(refund_data)

def display_refunds(refund_df):
    """
    Display refunds with detailed information for each.
    """
    if refund_df is None or refund_df.empty:
        logging.info("No refund data to display.")
        return

    # Group by OrderID to show only relevant refund transactions
    grouped_refunds = refund_df.groupby('OrderID')
    
    for order_id, group in grouped_refunds:
        logging.info(f"OrderID: {order_id}")
        for _, refund in group.iterrows():
            logging.info(f"  - Amount: {refund['RefundAmount']}, Date: {refund['RefundDate']}, Type: {refund['RefundType']}")
            logging.info(f"  - Total Fee Basis: {refund['TotalFeeBasis']}, Total Fee: {refund['TotalFee']}")
            logging.info(f"  - Line Items: {refund['LineItems']}")
            logging.info(f"  - References: {refund['References']}")
            logging.info("-" * 80)

if __name__ == "__main__":
    # Request the year and month from the user
    year = input("Enter the year (e.g., 2024): ").strip()
    month = input("Enter the month (1-12): ").strip()

    # Format the start and end dates based on user input
    start_date = f"{year}-{month.zfill(2)}-01T00:00:00.000Z"
    end_date = f"{year}-{month.zfill(2)}-31T23:59:59.999Z"

    logging.info(f"Fetching `REFUND` transactions from {start_date} to {end_date}...")

    # Retrieve finance transactions
    finance_df = get_finance_transactions(oauth_user_token, start_date, end_date)

    # If no data is returned, stop the script
    if finance_df.empty:
        logging.info("No transactions found for the specified period.")
    else:
        # Filter and process refund transactions
        refund_transactions_df = process_refund_transactions(finance_df)

        # Display only refund-related transactions
        display_refunds(refund_transactions_df)
