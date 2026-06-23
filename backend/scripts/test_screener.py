import requests
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup

def test_quarters():
    symbol = "RELIANCE"
    url = f"https://www.screener.in/company/{symbol}/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    response = curl_requests.get(url, headers=headers, impersonate="chrome")
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        quarters_section = soup.find('section', id='quarters')
        if quarters_section:
            print("--- Quarters Table Rows ---")
            table = quarters_section.find('table')
            if table:
                rows = table.find('tbody').find_all('tr')
                for r in rows:
                    cells = [td.text.strip() for td in r.find_all('td')]
                    name = cells[0].replace('+', '').replace('\xa0', ' ').strip()
                    print(f"Row Name: '{name}' | Latest Value: {cells[-1] if len(cells) > 1 else 'N/A'}")
        else:
            print("Quarters section not found!")
            
if __name__ == "__main__":
    test_quarters()
