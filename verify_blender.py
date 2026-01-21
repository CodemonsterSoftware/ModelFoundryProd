import os
import sys
import time
import requests

def test_blender_service():
    url = "http://localhost:8081/health"
    print(f"Checking Blender service at {url}...")
    
    for i in range(10):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                print("Blender service is UP!")
                print(response.json())
                return True
        except requests.ConnectionError:
            print(f"Attempt {i+1}: Connection failed, retrying in 2s...")
            time.sleep(2)
            
    print("Failed to connect to Blender service after multiple attempts.")
    return False

if __name__ == "__main__":
    if test_blender_service():
        sys.exit(0)
    else:
        sys.exit(1)
