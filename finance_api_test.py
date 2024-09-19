import os
import requests
from dotenv import load_dotenv  # Import the dotenv library

# Load environment variables from the .env file
load_dotenv()

# Fetch the OAuth User Token from the environment variable
oauth_user_token = os.getenv('EBAY_OAUTH_USER_TOKEN')

def get_promoted_listings_transactions(oauth_user_token):
    # Updated eBay Finance API endpoint to match API Explorer
    url = 'https://apiz.ebay.com/sell/finances/v1/transaction'
    
    # Set up headers with the OAuth User Token
    headers = {
        'Authorization': f'Bearer {oauth_user_token}',  # Use the OAuth User Token
        'Content-Type': 'application/json',
        'X-EBAY-C-MARKETPLACE-ID': 'EBAY_US',  # Add marketplace header
        'Accept': 'application/json'  # Ensure Accept header matches the API Explorer
    }

    # Define the parameters for the request
    params = {
        'limit': 10,  # Set a limit for how many transactions to return
    }

    # Debugging output to check the request
    print("Making request to eBay API...")
    print("URL:", url)
    print("Headers:", headers)
    print("Parameters:", params)

    # Make the GET request to the eBay Finance API
    response = requests.get(url, headers=headers, params=params)

    # Enhanced error handling to provide more context
    if response.status_code == 200:
        print("API Call Successful!")
        return response.json()
    elif response.status_code == 404:
        print("Error: 404 Not Found - The requested resource could not be found.")
        
    else:
        print(f"Error fetching transactions: {response.status_code} - {response.text}")
    return None

if __name__ == "__main__":
    # Check if the OAuth User Token is available
    if not oauth_user_token:
        print("Error: OAuth User Token is not available. Please check your .env file.")
    else:
        print(f"OAuth User Token: {oauth_user_token}")  # Print the token for debugging

        # Retrieve promoted listings fee transactions
        transactions = get_promoted_listings_transactions(oauth_user_token)
        
        if transactions:
            print("Promoted Listings Transactions:")
            print(transactions)
        else:
            print("Failed to retrieve transactions.")
