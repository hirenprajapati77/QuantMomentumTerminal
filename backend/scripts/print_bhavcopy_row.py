import requests
import sys

def main():
    url = "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_22062026.csv"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Referer': 'https://www.nseindia.com/'
    }
    
    print(f"Downloading official NSE Bhavcopy from: {url}")
    session = requests.Session()
    session.get("https://www.nseindia.com/", headers=headers)
    
    response = session.get(url, headers=headers)
    if response.status_code == 200:
        lines = response.content.decode('utf-8').split('\n')
        header = lines[0].strip()
        print("\n--- Headers ---")
        print(header)
        
        print("\n--- Raw Row for RELIANCE ---")
        found = False
        for line in lines[1:]:
            if line.startswith("RELIANCE,"):
                print(line.strip())
                found = True
                break
        if not found:
            print("RELIANCE row not found in Bhavcopy!")
    else:
        print(f"Error downloading: HTTP {response.status_code}")

if __name__ == "__main__":
    main()
