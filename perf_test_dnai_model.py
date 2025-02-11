import requests
import time
import statistics
import numpy as np
import concurrent.futures

def measure_dnai_performance(endpoint, num_requests, headers=None, payload=None, delay=0.1, max_workers=10):
    response_times = []
    success_count = 0
    error_count = 0

    print(f"Perf testing for {num_requests} POST requests to {endpoint}...\n")

    def post_dnai(i):
        start_time = time.time()
        try:
            response = requests.post(endpoint, headers=headers, json=payload)
            end_time = time.time()
            response_time = (end_time - start_time) * 1000

            if response.status_code == 200:
                #print(f"Request {i+1}: Status Code = {response.status_code}, Response Time = {response_time:.2f} ms , Response = {response.text.strip()}")
                return response_time, True, None
            else:
                #print(f"Request {i+1}: Status Code = {response.status_code}, Response Time = {response_time:.2f} ms, Response = {response.text.strip()}")
                return response_time, False, response.text.strip()

        except requests.exceptions.RequestException as e:
            #print(f"Request {i+1}: Failed with error: {e}")
            return None, False, str(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(post_dnai, i) for i in range(num_requests)]

        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            response_time, success, error_message = future.result()
            if response_time is not None:
                response_times.append(response_time)
            if success:
                success_count += 1
            else:
                error_count += 1
                print(f"Request {i+1} Failed: {error_message}")
            time.sleep(delay)

    total_requests = success_count + error_count
    avg_response_time = statistics.mean(response_times) if response_times else 0
    max_response_time = max(response_times) if response_times else 0
    min_response_time = min(response_times) if response_times else 0
    success_rate = (success_count / total_requests) * 100 if total_requests > 0 else 0
    error_rate = (error_count / total_requests) * 100 if total_requests > 0 else 0
    p95_response_time = np.percentile(response_times, 95) if response_times else 0
    p90_response_time = np.percentile(response_times, 90) if response_times else 0

    print("\n--- Performance Metrics ---")
    print(f"Total Requests: {total_requests}")
    print(f"Successful Requests: {success_count}")
    print(f"Failed Requests: {error_count}")
    print(f"Success Rate: {success_rate:.2f}%")
    print(f"Error Rate: {error_rate:.2f}%")
    print(f"Average Response Time: {avg_response_time:.2f} ms")
    print(f"Max Response Time: {max_response_time:.2f} ms")
    print(f"Min Response Time: {min_response_time:.2f} ms")
    print(f"P95 Response Time: {p95_response_time:.2f} ms")
    print(f"P90 Response Time: {p90_response_time:.2f} ms")
    print("---------------------------")

api_endpoint = "https://models.gdml.test-gdcorp.tools/v1/payment-routing/predict"
number_of_requests = 1000
headers = {
    "Authorization": "sso-jwt ",
    "Content-Type": "application/json"
}
payload = {
    "features": {
        "key1": "value1",
        "key2": "value2",
        "key3": "value3"
    },
    "identifier": "test"
}
delay_between_requests = 0.1  # 100ms
max_concurrent_requests = 10

measure_dnai_performance(api_endpoint, number_of_requests, headers, payload, delay=delay_between_requests, max_workers=max_concurrent_requests)