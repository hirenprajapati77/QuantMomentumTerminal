import requests
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
import re

def debug_mfsl():
    symbol = "MFSL"
    url = f"https://www.screener.in/company/{symbol}/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    print(f"Requesting MFSL from Screener.in...")
    response = curl_requests.get(url, headers=headers, impersonate="chrome")
    if response.status_code == 200:
        html_text = response.text
        soup = BeautifulSoup(html_text, 'html.parser')
        
        # Look for regex match
        print("\n--- Applying Regex Match ---")
        match = re.search(r'pledged\s+([\d.]+)%\s+of\s+their\s+holding', html_text, re.I)
        if match:
            print("Regex Match:", match.group(0))
            print("Extracted Value:", match.group(1))
        else:
            print("No regex match found!")
            
        # Find all occurrences of "pledged" or "pledge" in the text
        print("\n--- All Occurrences of 'pledge' in Text ---")
        matches = soup.find_all(string=re.compile(r'pledge', re.I))
        for m in matches:
            parent = m.parent
            print(f"[{parent.name}]: {parent.text.strip()}")
            
        # Print the snippet in the raw HTML for each occurrence of "pledge" or "pledged"
        print("\n--- Raw HTML Snippets ---")
        idx = 0
        while True:
            idx = html_text.lower().find("pledge", idx)
            if idx == -1:
                break
            start = max(0, idx - 80)
            end = min(len(html_text), idx + 80)
            snippet = html_text[start:end].replace('\n', ' ').strip()
            print(f"Index {idx}: ... {snippet} ...")
            idx += 6
    else:
        print("Failed to download, status:", response.status_code)

if __name__ == "__main__":
    debug_mfsl()
