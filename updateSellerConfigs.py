import csv
import requests
import uuid
import json


def get_resource(resource_id, jwt_token):
    url = f'https://seller-configs-ext.cp.api.dp.godaddy.com{resource_id}'
    headers = {'Authorization': jwt_token}
    #print(f"url: {url}\n\n")
    response = requests.get(url, headers=headers)
    return response.json()

def update_resource(resource_id, operations, jwt_token):
    url = f'https://seller-configs-ext.cp.api.dp.godaddy.com{resource_id}'
    
    data = get_resource(resource_id, jwt_token)
    
    if 'supportedGatewayOperations' in data and data['supportedGatewayOperations']:
        existing_operations = data['supportedGatewayOperations'][0].get('operations', [])
        if operations in existing_operations:
            print(f"Skipping update for {resource_id} as 'VERIFY' is already in the list of operations")
            return
        
    eTag = data['version']
    headers = {
        'Authorization': jwt_token,
        'eTag': str(eTag),
        'IdempotentId': str(uuid.uuid4())

    }
    
    data['supportedGatewayOperations'][0]['operations'].append(operations)
    print(f"new request data:\n{json.dumps(data, indent=2)}\n")
    response = requests.put(url, json=data, headers=headers)
    return response.json()

def process_resources_from_csv(csv_file, jwt_token):
    with open(csv_file, 'r') as file:
        print(f"Reading file {csv_file}\n")
        reader = csv.reader(file)
        #next(reader)
        resource_ids = [row[0] for row in reader]
    print(f"resource_ids{resource_ids}\n")
    for resource_id in resource_ids:
        resource_data = get_resource(resource_id, jwt_token)
        #print(f"Original Resource Data for {resource_id}:\n{json.dumps(resource_data, indent=2)}\n")

        if 'name' in resource_data and resource_data['name'].lower().startswith('chase'):
            updated_resource_data = update_resource(resource_id, "VERIFY", jwt_token)
            print(f"Updated Resource Data for {resource_id}:\n{updated_resource_data}\n")
        else:
            print(f"Skipping update for {resource_id} as 'name' doesn't start with 'chase'\n")

csv_file_path = '/Users/mpaudel/Documents/chase_seller_config_test.csv'
jwt_token = 'sso-jwt token'  
process_resources_from_csv(csv_file_path, jwt_token)
