#!/usr/bin/env python3
"""
Internal Purchase Tool CLI

A command-line tool for creating shoppers, managing payment profiles, and performing purchases
in various GoDaddy environments. Supports both automatic (default) and manual modes.

Usage:
    python InternalPurchaseTool.py

Author: Manoj Paudel
"""

import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone, tzinfo

import requests
import xml.etree.ElementTree as ET
import html  # For unescaping HTML/XML entities
import pytz


# =============================================================================
# CONFIGURATION CONSTANTS
# =============================================================================

# Environment Configuration
DEFAULT_ENV_SUBDOMAIN = "test"

# API URL Templates
SHOPPER_API_BASE_URL_TEMPLATE = 'https://shopper.api.int.{env}-godaddy.com/v1'
SSO_API_BASE_URL_TEMPLATE = 'https://sso.{env}-godaddy.com/v1/api'
PAYMENT_API_BASE_URL_TEMPLATE = 'https://payment.api.{env}-godaddy.com/v1'
BASKET_API_URL_TEMPLATE = 'https://gdcomm.{env}.glbt1.gdg/WscgdBasket/WscgdBasket.dll'
ENCRYPT_API_BASE_URL = 'http://0.0.0.0:3001/api'  # Local encryption service

# SSL Configuration
VERIFY_SSL_BASKET_API = False  # WARNING: Only use in controlled test environments

# Authentication Defaults
DEFAULT_PASSWORD = "eToolsXML4"
DEFAULT_PIN = "1024"
AUDIT_CLIENT_IP = "localhost"

# Contact Information Defaults
DEFAULT_CONTACT_INFO = {
    "address": {
        "address1": "123 Main St",
        "address2": "Suite 100",
        "city": "Seattle",
        "state": "WA",
        "postalCode": "98101",
        "country": "US"
    },
    "nameFirst": "Manoj",
    "nameLast": "Paudel",
    "organization": "Test",
    "phoneWork": "+15555555555",
    "phoneWorkExtension": "",
    "phoneHome": "",
    "phoneMobile": "",
    "fax": ""
}

# Payment Defaults
DEFAULT_CARD_DETAILS = {
    "pan": "4716885367556942",
    "type": "Visa",
    "expMonth": 12,
    "expYear": 2029,
    "cvv": 737,
    "nameOnCard": "Manoj Paudel"
}

DEFAULT_BILLING_CONTACT_INFO = {
    "taxId": "26394653330",
    "contact": {
        "nameFirst": "Manoj",
        "nameLast": "Paudel",
        "phone": "+15555555555",
        "organization": "Test",
        "addressMailing": {
            "city": "Seattle",
            "country": "US",
            "postalCode": "98101",
            "state": "WA",
            "address1": "123 Main St",
            "address2": "Suite 100"
        }
    }
}

DEFAULT_CURRENCY = "USD"
DEFAULT_BILLING_COUNTRY = "US"

# Cart and Purchase Defaults
DEFAULT_ADD_TO_CART_COUNTRY_CODE = "US"
DEFAULT_ADD_TO_CART_CURRENCY = "USD"
DEFAULT_ADD_TO_CART_PRODUCT_ID = "8007"
DEFAULT_SELLER_CONFIG_URI = "/v1/31430a42-6f4f-4646-9595-305f614957be/seller-configs/4e0ea080-99ab-4973-85c6-391556676f08"
DEFAULT_MARKET_ID = "en-us"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_api_url(template: str, environment: str) -> str:
    """Constructs the full API URL using the provided template and environment subdomain."""
    return template.format(env=environment)


class ArizonaTimezone(tzinfo):
    """Simple fixed offset timezone for Arizona (MST = UTC-7)."""
    
    def utcoffset(self, dt):
        return timedelta(hours=-7)

    def tzname(self, dt):
        return "MST"

    def dst(self, dt):
        return timedelta(0)


def get_current_time_iso_with_tz(offset_seconds: int = 0) -> str:
    """
    Get current time in ISO 8601 format with timezone.
    
    Args:
        offset_seconds: Time offset in seconds (positive or negative)
    
    Returns:
        ISO 8601 formatted string with 'Z' suffix
    """
    local_now = datetime.now() + timedelta(seconds=offset_seconds)
    utc_now = local_now.astimezone(timezone.utc)
    return utc_now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def handle_api_error(error: Exception, operation: str, response_text: str = "") -> None:
    """Centralized error handling for API calls."""
    if isinstance(error, requests.exceptions.HTTPError):
        print(f"HTTP error occurred during {operation}: {error}")
        if response_text:
            print(f"Response content: {response_text}")
    elif isinstance(error, requests.exceptions.ConnectionError):
        print(f"Connection error occurred during {operation}: {error}")
    elif isinstance(error, requests.exceptions.Timeout):
        print(f"Timeout error occurred during {operation}: {error}")
    elif isinstance(error, requests.exceptions.RequestException):
        print(f"An unexpected error occurred during {operation}: {error}")
    elif isinstance(error, json.JSONDecodeError):
        print(f"Failed to decode JSON from {operation} response. Response: {response_text}")


# =============================================================================
# API FUNCTIONS
# =============================================================================

def create_shopper(env_urls: dict, login_name: str, email: str) -> str | None:
    """
    Creates a new shopper via the Shopper API.

    Args:
        env_urls: Dictionary containing API URLs
        login_name: The desired login name for the new shopper
        email: The desired email for the new shopper

    Returns:
        The shopperId of the newly created shopper, or None if creation fails
    """
    print(f"\nAttempting to create a new shopper with login: {login_name} and email: {email}...")
    
    url = f"{env_urls['SHOPPER_API_BASE_URL']}/shoppers?auditClientIp={AUDIT_CLIENT_IP}"
    headers = {'Content-Type': 'application/json'}
    
    payload = {
        "privateLabelId": 1,
        "loginName": login_name,
        "email": email,
        "auth": {
            "password": DEFAULT_PASSWORD,
            "pin": DEFAULT_PIN
        },
        "contact": {
            "nameFirst": "eComm",
            "nameLast": "Automation",
            "organization": "test",
            "address": "",  # Will be patched later
            "phoneWork": "",
            "phoneWorkExtension": "",
            "phoneHome": "",
            "phoneMobile": "",
            "fax": ""
        },
        "preference": {
            "currency": "USD",
            "marketId": "en-US",
            "emailFormat": "",
            "allowedCommunicationTypes": []
        }
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        
        response_json = response.json()
        shopper_id = str(response_json.get('shopperId'))
        
        if shopper_id:
            print(f"Successfully created shopper! Shopper ID: {shopper_id}")
            return shopper_id
        else:
            print("Shopper ID not found in the response.")
            return None
            
    except Exception as e:
        handle_api_error(e, "shopper creation", getattr(response, 'text', ''))
        return None


def get_jwt_token(env_urls: dict, shopper_id: str) -> str | None:
    """
    Retrieves a JWT token for the given shopper ID.

    Args:
        env_urls: Dictionary containing API URLs
        shopper_id: The ID of the shopper to get the token for

    Returns:
        The JWT token string, or None if token retrieval fails
    """
    print(f"\nAttempting to get JWT token for shopper ID: {shopper_id}...")
    
    url = f"{env_urls['SSO_API_BASE_URL']}/token"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "username": shopper_id,
        "password": DEFAULT_PASSWORD
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        
        response_json = response.json()
        
        # Prioritize 'data' field if 'jwtToken' is not found
        jwt_token = response_json.get('jwtToken') or response_json.get('data')

        if jwt_token:
            print("Successfully retrieved JWT token.")
            return jwt_token
        else:
            print("JWT token not found in the response.")
            print(f"Response content: {response.text}")
            return None
            
    except Exception as e:
        handle_api_error(e, "JWT token retrieval", getattr(response, 'text', ''))
        return None


def patch_shopper(env_urls: dict, shopper_id: str, jwt_token: str) -> None:
    """
    Patches the shopper's contact information using the given JWT token.

    Args:
        env_urls: Dictionary containing API URLs
        shopper_id: The ID of the shopper to patch
        jwt_token: The JWT token for authorization
    """
    print(f"\nAttempting to patch shopper ID: {shopper_id}...")
    
    url = f"{env_urls['SHOPPER_API_BASE_URL']}/shoppers/{shopper_id}?auditClientIp={AUDIT_CLIENT_IP}"
    headers = {
        'Authorization': f'sso-jwt {jwt_token}',
        'Content-Type': 'application/json'
    }
    payload = {"contact": DEFAULT_CONTACT_INFO}

    try:
        response = requests.patch(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        print("Shopper patched successfully!")
        print(f"Response status code: {response.status_code}")
        print(f"Response content: {response.text}")
        
    except Exception as e:
        handle_api_error(e, "shopper patching", getattr(response, 'text', ''))


def encrypt_card(card_number: str) -> str | None:
    """
    Encrypts a credit card number using the local encryption service.

    Args:
        card_number: The credit card number (PAN) to encrypt

    Returns:
        The encrypted card number string, or None if encryption fails
    """
    print(f"\nAttempting to encrypt card number...")
    
    url = f"{ENCRYPT_API_BASE_URL}/encrypt"
    headers = {'content-type': 'application/json'}
    payload = {
        "env": "test",  # Assuming the local encryption tool uses "test" env parameter
        "ccnumber": card_number
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        
        response_json = response.json()
        encrypted_number = response_json.get('ccEncrypted')
        
        if encrypted_number:
            print("Card encrypted successfully!")
            return encrypted_number
        else:
            print("Encrypted card number not found in the response.")
            print(f"Response content: {response.text}")
            return None
            
    except Exception as e:
        handle_api_error(e, "card encryption", getattr(response, 'text', ''))
        return None


def create_payment_profile(env_urls: dict, shopper_id: str, jwt_token: str, 
                          encrypted_card_number: str, card_type: str, 
                          billing_country: str, currency: str) -> str | None:
    """
    Creates a payment profile for the shopper.

    Args:
        env_urls: Dictionary containing API URLs
        shopper_id: The ID of the shopper
        jwt_token: The JWT token for authorization
        encrypted_card_number: The encrypted credit card number
        card_type: The type of credit card (e.g., "Visa")
        billing_country: The billing country code (e.g., "US")
        currency: The currency code (e.g., "USD")

    Returns:
        The paymentProfileId of the newly created payment profile, or None if creation fails
    """
    print(f"\nAttempting to create payment profile for shopper ID: {shopper_id}...")
    
    url = f"{env_urls['PAYMENT_API_BASE_URL']}/paymentprofiles"
    headers = {
        'Authorization': f'sso-jwt {jwt_token}',
        'X-Request-Id': str(uuid.uuid4()),
        'idempotentId': str(uuid.uuid4()),
        'Content-Type': 'application/json'
    }

    payload = {
        "creditCard": {
            "number": encrypted_card_number,
            "type": card_type,
            "nameOnCard": DEFAULT_CARD_DETAILS["nameOnCard"],
            "expMonth": DEFAULT_CARD_DETAILS["expMonth"],
            "expYear": DEFAULT_CARD_DETAILS["expYear"],
            "cvv": DEFAULT_CARD_DETAILS["cvv"]
        },
        "status": "CREATE",
        "currency": currency,
        "billTo": DEFAULT_BILLING_CONTACT_INFO,
        "source": "checkout"
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        
        response_json = response.json()
        payment_profile_id = response_json.get('profileID')
        
        if payment_profile_id:
            print(f"Payment profile created successfully! Payment Profile ID: {payment_profile_id}")
            return str(payment_profile_id)
        else:
            print("Payment Profile ID not found in the response.")
            print(f"Response content: {response.text}")
            return None
            
    except Exception as e:
        handle_api_error(e, "payment profile creation", getattr(response, 'text', ''))
        return None


def add_item_to_cart(env_urls: dict, shopper_id: str, country_code: str, 
                    currency: str, product_id: str) -> None:
    """
    Adds an item to the shopper's cart via the WscgdBasket service.

    Args:
        env_urls: Dictionary containing API URLs
        shopper_id: The ID of the shopper
        country_code: The country code (e.g., "US")
        currency: The currency code (e.g., "USD")
        product_id: The product ID to add to cart
    """
    print(f"\nAttempting to add product ID '{product_id}' to cart for shopper ID: {shopper_id}...")
    
    url = env_urls['BASKET_API_URL']
    headers = {
        'SOAPAction': '#AddItem',
        'X-Request-Id': str(uuid.uuid4()),
        'Content-Type': 'text/xml; charset=utf-8'
    }
    
    # Construct the SOAP XML payload
    payload = f"""<SOAP:Envelope xmlns:SOAP="http://schemas.xmlsoap.org/soap/envelope/" xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:tns="urn:WscgdBasketService" xmlns:types="urn:WscgdBasketService/encodedTypes" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <SOAP:Body SOAP:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
        <tns:AddItem>
            <bstrShopperID>{shopper_id}</bstrShopperID>
            <bstrRequestXML>
                <itemRequest transactionCurrency="{currency}" bill_to_country="{country_code}">
                    <item productid="{product_id}" itemTrackingCode="TestNG"></item>
                </itemRequest>
            </bstrRequestXML>
        </tns:AddItem>
    </SOAP:Body>
</SOAP:Envelope>"""

    try:
        # Use the VERIFY_SSL_BASKET_API flag to control SSL verification
        response = requests.post(url, headers=headers, data=payload, verify=VERIFY_SSL_BASKET_API)
        response.raise_for_status()
        
        print(f"Raw Basket API Response Text: {response.text}")  # Debugging: print raw response

        # Parse the outer SOAP XML
        root = ET.fromstring(response.text)
        
        # Find the <return> tag. The namespace for AddItem might be 'tns' or 'snp' depending on server.
        # Let's try to find the return tag regardless of its direct parent namespace in this simple case.
        # A more robust solution might iterate through known namespaces or use a more specific XPath.
        return_node = root.find(".//{urn:WscgdBasketService}return")
        if return_node is None:  # Fallback for different namespaces or structure
            return_node = root.find(".//return")

        if return_node is not None and return_node.text:
            # Unescape the inner XML string
            unescaped_xml_str = html.unescape(return_node.text)
            print(f"Unescaped Basket API Return Content: {unescaped_xml_str}")  # Debugging: print unescaped content

            # Parse the unescaped inner XML
            inner_root = ET.fromstring(unescaped_xml_str)
            message_node = inner_root.find(".//MESSAGE")
            
            if message_node is not None and message_node.text:
                basket_message = message_node.text
                print(f"Basket API Message: {basket_message}")
                if basket_message.lower() == 'success':
                    print("Item added to cart successfully!")
                else:
                    print(f"Item add to cart operation reported '{basket_message}'.")
            else:
                print("Could not find <MESSAGE> in unescaped Basket API response.")
        else:
            print("Could not find <return> tag or its content in Basket API response.")
        
    except Exception as e:
        handle_api_error(e, "add to cart", getattr(response, 'text', ''))


def perform_purchase(env_urls: dict, shopper_id: str, jwt_token: str, 
                    payment_profile_id: str, cvv: str, config_uri: str) -> str | None:
    """
    Performs the purchase step.

    Args:
        env_urls: Dictionary containing API URLs
        shopper_id: The ID of the shopper (context only)
        jwt_token: The JWT token for authorization
        payment_profile_id: The ID of the stored payment method
        cvv: The CVV for the transaction
        config_uri: The seller config URI

    Returns:
        The orderId if the purchase is successful, or None otherwise
    """
    print(f"\nAttempting to perform purchase for shopper ID: {shopper_id}...")
    
    url = f"{env_urls['PAYMENT_API_BASE_URL']}/purchase"
    headers = {
        'Authorization': f'sso-jwt {jwt_token}',
        'X-Request-Id': str(uuid.uuid4()),
        'X-Market-Id': DEFAULT_MARKET_ID,
        'Content-Type': 'application/json'
    }

    payload = {
        "standardBasket": True,
        "paymentDetails": {
            "storedMethods": [{
                "id": int(payment_profile_id),
                "cvv": cvv
            }],
            "sellerConfigUri": config_uri
        }
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        
        response_json = response.json()
        order_id = response_json.get('orderId')
        
        if order_id:
            print(f"Purchase completed successfully! Order ID: {order_id}")
            print(f"Response status code: {response.status_code}")
            print(f"Response content: {json.dumps(response_json, indent=2)}")
            return str(order_id)
        else:
            print("Order ID not found in purchase response.")
            print(f"Response status code: {response.status_code}")
            print(f"Response content: {json.dumps(response_json, indent=2)}")
            return None
            
    except Exception as e:
        handle_api_error(e, "purchase", getattr(response, 'text', ''))
        return None


# =============================================================================
# MAIN CLI LOGIC
# =============================================================================

def run_automatic_mode(env_urls: dict) -> None:
    """Run the tool in automatic mode using all default values."""
    print("Running in AUTOMATIC mode - all steps will use defaults")
    
    # Create new shopper
    print("\n--- Creating New Shopper (Automatic Mode) ---")
    unique_id = uuid.uuid4().hex[:8]
    login_name = f"ecomQA{unique_id}"
    email = f"ecommqatest+{unique_id}@mailinator.com"
    shopper_id = create_shopper(env_urls, login_name, email)
    
    if not shopper_id:
        print("Failed to create shopper. Exiting.")
        sys.exit(1)

    # Get JWT token and patch shopper
    jwt_token = get_jwt_token(env_urls, shopper_id)
    if not jwt_token:
        print("Failed to retrieve JWT token. Exiting.")
        sys.exit(1)
    
    patch_shopper(env_urls, shopper_id, jwt_token)

    # Card and payment profile (using defaults)
    print("\n--- Card and Payment Profile Configuration (Automatic Mode) ---")
    print(f"Using default card details: PAN={DEFAULT_CARD_DETAILS['pan']}, "
          f"Type={DEFAULT_CARD_DETAILS['type']}, Country={DEFAULT_BILLING_COUNTRY}, "
          f"Currency={DEFAULT_CURRENCY}")
    
    encrypted_pan = encrypt_card(DEFAULT_CARD_DETAILS['pan'])
    if not encrypted_pan:
        print("Failed to encrypt card number. Exiting.")
        sys.exit(1)

    payment_profile_id = create_payment_profile(
        env_urls, shopper_id, jwt_token, encrypted_pan, 
        DEFAULT_CARD_DETAILS['type'], DEFAULT_BILLING_COUNTRY, DEFAULT_CURRENCY
    )
    if not payment_profile_id:
        print("Failed to create payment profile. Exiting.")
        sys.exit(1)

    # Add to cart (using defaults)
    print("\n--- Add to Cart Configuration (Automatic Mode) ---")
    print(f"Using default Add to Cart details: Country={DEFAULT_ADD_TO_CART_COUNTRY_CODE}, "
          f"Currency={DEFAULT_ADD_TO_CART_CURRENCY}, Product ID={DEFAULT_ADD_TO_CART_PRODUCT_ID}")
    
    add_item_to_cart(env_urls, shopper_id, DEFAULT_ADD_TO_CART_COUNTRY_CODE, 
                    DEFAULT_ADD_TO_CART_CURRENCY, DEFAULT_ADD_TO_CART_PRODUCT_ID)

    # Purchase (using defaults)
    print("\n--- Purchase Configuration (Automatic Mode) ---")
    print(f"Using default Seller Config URI: {DEFAULT_SELLER_CONFIG_URI}")
    
    order_id = perform_purchase(env_urls, shopper_id, jwt_token, payment_profile_id, 
                               str(DEFAULT_CARD_DETAILS['cvv']), DEFAULT_SELLER_CONFIG_URI)
    
    print("\n--- AUTOMATIC MODE COMPLETE ---")
    print("All steps completed using default values.")
    if order_id:
        print(f"Order ID: {order_id} and Shopper ID: {shopper_id}")
    else:
        print(f"Shopper ID: {shopper_id} (Purchase failed - no Order ID)")


def run_manual_mode(env_urls: dict) -> None:
    """Run the tool in manual mode with user prompts."""
    print("Running in MANUAL mode - you will be prompted for each step")
    
    # Shopper section
    user_input = input("\nEnter an existing Shopper ID or press Enter to create a new shopper: ").strip()
    
    if not user_input:
        unique_id = uuid.uuid4().hex[:8]
        login_name = f"ecomQA{unique_id}"
        email = f"ecommqatest+{unique_id}@mailinator.com"
        shopper_id = create_shopper(env_urls, login_name, email)
    else:
        shopper_id = user_input
        print(f"Using existing shopper ID: {shopper_id}")

    if not shopper_id:
        print("Failed to determine shopper ID. Exiting.")
        sys.exit(1)

    # JWT token and patching
    jwt_token = get_jwt_token(env_urls, shopper_id)
    if not jwt_token:
        print("Failed to retrieve JWT token. Exiting.")
        sys.exit(1)
    
    patch_shopper(env_urls, shopper_id, jwt_token)

    # Card and payment profile section
    print("\n--- Card and Payment Profile Configuration ---")
    card_input = input(
        f"Enter PAN, Card Type, Billing Country, Currency (e.g., 1234... Visa US USD) "
        f"or press Enter to use defaults ({DEFAULT_CARD_DETAILS['pan']}, {DEFAULT_CARD_DETAILS['type']}, "
        f"{DEFAULT_BILLING_COUNTRY}, {DEFAULT_CURRENCY}): "
    ).strip()

    pan = DEFAULT_CARD_DETAILS['pan']
    card_type = DEFAULT_CARD_DETAILS['type']
    billing_country = DEFAULT_BILLING_COUNTRY
    currency = DEFAULT_CURRENCY

    if card_input:
        parts = card_input.split()
        if len(parts) == 4:
            pan, card_type, billing_country, currency = parts
            print(f"Using custom card details: PAN={pan}, Type={card_type}, "
                  f"Country={billing_country}, Currency={currency}")
        else:
            print("Invalid input format for card details. Using default values.")
    else:
        print("Using default card details.")

    encrypted_pan = encrypt_card(pan)
    if not encrypted_pan:
        print("Failed to encrypt card number. Exiting.")
        sys.exit(1)

    payment_profile_id = create_payment_profile(env_urls, shopper_id, jwt_token, 
                                               encrypted_pan, card_type, billing_country, currency)
    if not payment_profile_id:
        print("Failed to create payment profile. Exiting.")
        sys.exit(1)

    # Add to cart section
    print("\n--- Add to Cart Configuration ---")
    add_to_cart_input = input(
        f"Enter Country Code, Currency, Product ID (e.g., US USD 12345) "
        f"or press Enter to use defaults ({DEFAULT_ADD_TO_CART_COUNTRY_CODE}, "
        f"{DEFAULT_ADD_TO_CART_CURRENCY}, {DEFAULT_ADD_TO_CART_PRODUCT_ID}): "
    ).strip()

    cart_country_code = DEFAULT_ADD_TO_CART_COUNTRY_CODE
    cart_currency = DEFAULT_ADD_TO_CART_CURRENCY
    cart_product_id = DEFAULT_ADD_TO_CART_PRODUCT_ID

    if add_to_cart_input:
        parts = add_to_cart_input.split()
        if len(parts) == 3:
            cart_country_code, cart_currency, cart_product_id = parts
            print(f"Using custom Add to Cart details: Country={cart_country_code}, "
                  f"Currency={cart_currency}, Product ID={cart_product_id}")
        else:
            print("Invalid input format for Add to Cart details. Using default values.")
    else:
        print("Using default Add to Cart details.")

    add_item_to_cart(env_urls, shopper_id, cart_country_code, cart_currency, cart_product_id)

    # Purchase section
    print("\n--- Purchase Configuration ---")
    purchase_config_input = input(
        f"Enter Seller Config URI or press Enter to use default ({DEFAULT_SELLER_CONFIG_URI}): "
    ).strip()

    config_uri = purchase_config_input if purchase_config_input else DEFAULT_SELLER_CONFIG_URI
    print(f"Using Seller Config URI: {config_uri}")

    order_id = perform_purchase(env_urls, shopper_id, jwt_token, payment_profile_id, 
                               str(DEFAULT_CARD_DETAILS['cvv']), config_uri)
    
    print("\n--- MANUAL MODE COMPLETE ---")
    print("All steps completed.")
    if order_id:
        print(f"Order ID: {order_id} and Shopper ID: {shopper_id}")
    else:
        print(f"Shopper ID: {shopper_id} (Purchase failed - no Order ID)")


def main():
    """Main function for the Shopper CLI tool."""
    print("=" * 60)
    print("           Shopper Management CLI Tool")
    print("=" * 60)

    # Environment configuration
    env_input = input(
        f"Enter environment subdomain (e.g., 'dev', 'staging', 'prod') "
        f"or press Enter to use default ('{DEFAULT_ENV_SUBDOMAIN}') and run automatically: "
    ).strip()
    
    # Determine mode and environment
    auto_mode = not env_input
    environment = env_input if env_input else DEFAULT_ENV_SUBDOMAIN
    print(f"Using environment: {environment}")

    # Construct API URLs
    env_urls = {
        'SHOPPER_API_BASE_URL': get_api_url(SHOPPER_API_BASE_URL_TEMPLATE, environment),
        'SSO_API_BASE_URL': get_api_url(SSO_API_BASE_URL_TEMPLATE, environment),
        'PAYMENT_API_BASE_URL': get_api_url(PAYMENT_API_BASE_URL_TEMPLATE, environment),
        'BASKET_API_URL': get_api_url(BASKET_API_URL_TEMPLATE, environment)
    }
    
    print("\nAPI Endpoints for this run:")
    for key, value in env_urls.items():
        print(f"  {key}: {value}")

    # Run in appropriate mode
    if auto_mode:
        run_automatic_mode(env_urls)
    else:
        run_manual_mode(env_urls)


if __name__ == "__main__":
    main()
