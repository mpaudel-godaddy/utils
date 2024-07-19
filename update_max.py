import csv
import requests
import json
import uuid
from datetime import datetime

CSV_FILE_PATH = 'adyen_configs.csv'
LOG_FILE_PATH = 'script_log.txt'
AUTH_TOKEN = 'sso-jwt '

def read_csv(file_path):
    with open(file_path, mode='r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        rows = [row for row in reader]
    return rows

def get_config(resource_id):
    url = f'https://seller-configs-ext.cp.api.test.godaddy.com/v1/31430a42-6f4f-4646-9595-305f614957be/seller-configs/{resource_id}'
    headers = {
        "Authorization": AUTH_TOKEN
    }

    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        log_message(f"GET request failed for url {url} with status code {response.status_code}")
        return None

def put_config(resource_id, updated_config, version):
    url = f'https://seller-configs-ext.cp.api.test.godaddy.com/v1/31430a42-6f4f-4646-9595-305f614957be/seller-configs/{resource_id}'
    headers = {
        "Authorization": AUTH_TOKEN,
        "idempotentId": str(uuid.uuid4()),
        "eTag": str(version)
    }

    response = requests.put(url, headers=headers, json=updated_config)
    
    if response.status_code == 200:
        log_message(f"PUT request successful for resource_id {resource_id}.")
    else:
        log_message(f"PUT request failed for resource_id {resource_id} with status code {response.status_code}")

def log_message(message):
    with open(LOG_FILE_PATH, mode='a') as log_file:
        log_file.write(f"{datetime.now()} - {message}\n")

def main():
    rows = read_csv(CSV_FILE_PATH)
    
    for row in rows:
        resource_id = row.get('resourceId')
        max_amount = row.get('maxAmount')
        
        if not resource_id:
            log_message("Resource ID missing in CSV row.")
            continue

        config = get_config(resource_id)
        
        if config is not None:
            config_data = config.get("configurationData", {})
            
            if max_amount:
                try:
                    max_amount = int(max_amount)
                    config_data["maxTransactionLimitOverride"] = {"maximum": max_amount}
                    log_message(f"Set 'maxTransactionLimitOverride' to {max_amount} in configurationData for resource_id {resource_id}.")
                except ValueError:
                    log_message(f"Invalid maxAmount value for resource_id {resource_id}. Skipping.")
                    continue
            else:
                if "maxTransactionLimitOverride" in config_data:
                    del config_data["maxTransactionLimitOverride"]
                    log_message(f"Removed 'maxTransactionLimitOverride' from configurationData for resource_id {resource_id}.")
                else:
                    log_message(f"No action needed for resource_id {resource_id}")
                    continue

            config["configurationData"] = config_data

            version = config.get("version", "")
            
            put_config(resource_id, config, version)
        else:
            log_message(f"Failed to get config for resource_id {resource_id}.")



if __name__ == "__main__":
    main()
