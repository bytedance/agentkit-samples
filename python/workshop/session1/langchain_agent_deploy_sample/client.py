import requests
import json


def main():
    # Target URL
    url = "http://localhost:8000/invoke"

    # Payload parameters
    payload = {
        "prompt": "Hello, can you calculate 10 + 20 and tell me the length of the word 'AgentKit'?"
    }

    # Headers
    headers = {"user_id": "test_user_001", "session_id": "session_test_001"}

    print(f"Sending POST request to {url} with payload: {payload}")

    try:
        response = requests.post(url, json=payload, headers=headers, stream=True)

        if response.status_code == 200:
            print("\n--- Streaming Response ---")
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode("utf-8")
                    if decoded_line.startswith("data: "):
                        decoded_line = decoded_line[6:]

                    if decoded_line.strip() == "[DONE]":
                        continue

                    # Expecting SSE or JSON lines depending on implementation
                    # The agent code yields json.dumps(event_data)
                    try:
                        data = json.loads(decoded_line)
                        print(json.dumps(data, indent=2, ensure_ascii=False))
                    except json.JSONDecodeError:
                        print(f"Raw: {decoded_line}")
            print("\n--- End of Stream ---")
        else:
            print(f"Request failed with status code: {response.status_code}")
            print(response.text)

    except requests.exceptions.ConnectionError:
        print(
            "Error: Could not connect to the server. Is the agent running on port 8000?"
        )
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
