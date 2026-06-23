import sys
import hashlib
import requests
import urllib.parse
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from backend.app.config.settings import settings

def generate_fyers_login_url(app_id: str, redirect_uri: str) -> str:
    base_url = "https://api-t1.fyers.in/api/v3/generate-authcode"
    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": "nse_scanner_login"
    }
    query_str = urllib.parse.urlencode(params)
    return f"{base_url}?{query_str}"

def exchange_code_for_token(app_id: str, secret_id: str, auth_code: str) -> str:
    url = "https://api-t1.fyers.in/api/v3/validate-authcode"
    
    # Calculate appIdHash = sha256(app_id + ":" + secret_id)
    hash_input = f"{app_id}:{secret_id}"
    app_id_hash = hashlib.sha256(hash_input.encode()).hexdigest()
    
    payload = {
        "grant_type": "authorization_code",
        "appIdHash": app_id_hash,
        "code": auth_code
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    print(f"Exchanging authorization code for access token...")
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if data.get("s") == "ok":
            return data.get("access_token")
        else:
            raise Exception(f"Fyers authentication error: {data.get('message', 'Unknown error')}")
    else:
        raise Exception(f"HTTP error {response.status_code} during token exchange: {response.text}")

def main():
    print("=" * 60)
    print(" Fyers API Token Generation Helper ")
    print("=" * 60)
    
    app_id = settings.FYERS_APP_ID
    secret_id = settings.FYERS_SECRET_ID
    redirect_uri = settings.FYERS_REDIRECT_URI
    
    if not app_id or not secret_id or not redirect_uri:
        print("ERROR: Fyers credentials missing in .env file!")
        print("Please configure FYERS_APP_ID, FYERS_SECRET_ID, and FYERS_REDIRECT_URI first.")
        sys.exit(1)
        
    login_url = generate_fyers_login_url(app_id, redirect_uri)
    
    print("\nStep 1: Open the login URL below in your web browser:")
    print("-" * 60)
    print(login_url)
    print("-" * 60)
    print("\nTip: Log in with your Fyers credentials, verify OTP, and wait for redirect.")
    
    print("\nStep 2: After redirect, paste the redirect URL or the 'auth_code' from the page here:")
    input_str = input("Redirect URL or Code: ").strip()
    
    if not input_str:
        print("ERROR: Input cannot be empty!")
        sys.exit(1)
        
    # Extract auth_code from URL if user pasted the full URL
    auth_code = input_str
    if "auth_code=" in input_str or "code=" in input_str:
        parsed = urllib.parse.urlparse(input_str)
        params = urllib.parse.parse_qs(parsed.query)
        # Check both query parameters: Fyers redirect uses 'auth_code'
        auth_code = params.get("auth_code", params.get("code", [None]))[0]
        
    if not auth_code:
        print(f"ERROR: Could not parse authorization code from: {input_str}")
        sys.exit(1)
        
    try:
        access_token = exchange_code_for_token(app_id, secret_id, auth_code)
        
        # Save token to file
        token_file = settings.token_path
        token_file.write_text(access_token)
        print(f"\nSUCCESS: Access token successfully retrieved and saved to: {token_file}")
        
    except Exception as e:
        print(f"\nERROR: Failed to retrieve token: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
