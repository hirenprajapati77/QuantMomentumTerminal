import requests
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup

def inspect_shareholding():
    symbol = "MFSL"
    url = f"https://www.screener.in/company/{symbol}/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    print(f"Requesting MFSL shareholding table...")
    response = curl_requests.get(url, headers=headers, impersonate="chrome")
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        sh_section = soup.find('section', id='shareholding')
        if sh_section:
            print("\n--- Shareholding Table Rows ---")
            table = sh_section.find('table')
            if table:
                rows = table.find_all('tr')
                for r in rows:
                    cells = [td.text.strip() for td in r.find_all(['td', 'th'])]
                    # Print the row if it exists
                    if cells:
                        print(cells)
        else:
            print("Shareholding section not found!")
    else:
        print("Failed to download, status:", response.status_code)

if __name__ == "__main__":
    inspect_shareholding()
