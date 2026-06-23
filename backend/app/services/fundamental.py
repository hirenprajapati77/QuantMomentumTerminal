import re
import logging
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests
from sqlalchemy.orm import Session
from backend.app.config.settings import settings
from backend.app.core.exceptions import IngestionException
from backend.app.models.fundamental import CompanyFundamental

logger = logging.getLogger("nse_scanner.fundamental")

class FundamentalService:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        }

    def scrape_company_fundamentals(self, symbol: str) -> dict:
        """Scrapes Screener.in for fundamentals and returns a normalized dict"""
        url = f"https://www.screener.in/company/{symbol}/"
        logger.info(f"Scraping fundamentals for {symbol} from Screener.in...")
        
        try:
            response = curl_requests.get(url, headers=self.headers, impersonate="chrome", timeout=20)
            
            if response.status_code == 404:
                raise IngestionException(f"Symbol {symbol} not found on Screener.in (404).")
            if response.status_code != 200:
                raise IngestionException(f"HTTP error {response.status_code} while scraping {symbol}.")
                
            soup = BeautifulSoup(response.text, 'html.parser')
            html_text = response.text
            
            # Check if stock is under surveillance (ASM/GSM)
            has_surveillance = bool(re.search(r'\b(ASM|GSM)\s+Stage|surveillance\s+framework|additional\s+surveillance\s+measure', html_text, re.I))
            
            data = {
                "symbol": symbol,
                "sector": None,
                "industry": None,
                "market_cap": None,
                "sales_growth_qoq": None,
                "sales_growth_yoy": None,
                "profit_growth_yoy": None,
                "roce": None,
                "roe": None,
                "debt_to_equity": None,
                "institutional_holding": None,
                "institutional_holding_qoq_change": None,
                "promoter_pledge": 0.0,  # Default to 0.0 if not found
                "under_surveillance": has_surveillance
            }
            
            # 1. Parse Sector and Industry
            sector_a = soup.find('a', title='Sector')
            if sector_a:
                data["sector"] = sector_a.text.strip()
            
            industry_a = soup.find('a', title='Industry')
            if industry_a:
                data["industry"] = industry_a.text.strip()
                
            # 2. Parse Top Ratios (Market Cap, ROCE, ROE)
            ratios_ul = soup.find('ul', id='top-ratios')
            if ratios_ul:
                for li in ratios_ul.find_all('li'):
                    name_span = li.find('span', class_='name')
                    value_span = li.find('span', class_='number')
                    if name_span and value_span:
                        name = name_span.text.strip().lower()
                        val_str = value_span.text.replace(',', '').strip()
                        
                        try:
                            val = float(val_str)
                            if "market cap" in name:
                                data["market_cap"] = val
                            elif "roce" in name:
                                data["roce"] = val
                            elif "roe" in name:
                                data["roe"] = val
                        except ValueError:
                            pass

            # 3. Parse Promoter Pledge from bullet points
            # NOTE/TODO: This regex is tightly coupled to Screener's exact sentence template.
            # If Screener changes the phrasing, this might fail to match and return a false 0.0% pledge.
            # Example: "Promoters have pledged 27.6% of their holding."
            pledge_match = re.search(r'pledged\s+([\d.]+)%\s+of\s+their\s+holding', html_text, re.I)
            if pledge_match:
                try:
                    data["promoter_pledge"] = float(pledge_match.group(1))
                except ValueError:
                    pass

            # Helper function to parse numeric values from Screener table row cells
            def parse_cells(cells):
                parsed = []
                for cell in cells:
                    val_str = cell.replace(',', '').replace('%', '').strip()
                    try:
                        parsed.append(float(val_str))
                    except ValueError:
                        parsed.append(None)
                return parsed

            # 4. Parse Quarters Table (Sales growth QoQ/YoY, Profit growth YoY)
            quarters_section = soup.find('section', id='quarters')
            if quarters_section:
                table = quarters_section.find('table')
                if table:
                    rows = table.find('tbody').find_all('tr')
                    sales_vals = []
                    profit_vals = []
                    
                    for r in rows:
                        cells = [td.text.strip() for td in r.find_all('td')]
                        name = cells[0].replace('+', '').replace('\xa0', ' ').strip().lower()
                        if name == "sales":
                            sales_vals = parse_cells(cells[1:])
                        elif name == "net profit":
                            profit_vals = parse_cells(cells[1:])
                            
                    # Calculate growth rates (if values available)
                    # Latest value is index -1. Previous value is index -2. 4-quarters-ago is index -5.
                    if len(sales_vals) >= 2 and sales_vals[-1] is not None and sales_vals[-2] is not None:
                        prev_sales = sales_vals[-2]
                        if prev_sales > 0:
                            data["sales_growth_qoq"] = round(((sales_vals[-1] - prev_sales) / prev_sales) * 100, 2)
                            
                    if len(sales_vals) >= 5 and sales_vals[-1] is not None and sales_vals[-5] is not None:
                        yoy_sales = sales_vals[-5]
                        if yoy_sales > 0:
                            data["sales_growth_yoy"] = round(((sales_vals[-1] - yoy_sales) / yoy_sales) * 100, 2)
                            
                    if len(profit_vals) >= 5 and profit_vals[-1] is not None and profit_vals[-5] is not None:
                        yoy_profit = profit_vals[-5]
                        if yoy_profit > 0:
                            data["profit_growth_yoy"] = round(((profit_vals[-1] - yoy_profit) / yoy_profit) * 100, 2)

            # 5. Parse Balance Sheet Table (Debt to Equity)
            # D/E = Borrowings / (Equity Capital + Reserves)
            bs_section = soup.find('section', id='balance-sheet')
            if bs_section:
                table = bs_section.find('table')
                if table:
                    rows = table.find('tbody').find_all('tr')
                    equity_cap_vals = []
                    reserves_vals = []
                    borrowings_vals = []
                    
                    for r in rows:
                        cells = [td.text.strip() for td in r.find_all('td')]
                        name = cells[0].replace('+', '').replace('\xa0', ' ').strip().lower()
                        if name in ["equity capital", "share capital"]:
                            equity_cap_vals = parse_cells(cells[1:])
                        elif name == "reserves":
                            reserves_vals = parse_cells(cells[1:])
                        elif name == "borrowings":
                            borrowings_vals = parse_cells(cells[1:])
                            
                    # Calculate Debt to Equity for the latest period
                    # Ensure we have values at index -1 (or index -2 if index -1 is empty)
                    latest_idx = -1
                    if len(equity_cap_vals) > 0:
                        # Find the last non-None value index
                        for idx in range(len(equity_cap_vals) - 1, -1, -1):
                            if equity_cap_vals[idx] is not None:
                                latest_idx = idx
                                break
                                
                        try:
                            eq_cap = equity_cap_vals[latest_idx] or 0.0
                            reserves = reserves_vals[latest_idx] or 0.0
                            borrow = borrowings_vals[latest_idx] or 0.0
                            
                            total_equity = eq_cap + reserves
                            if total_equity > 0:
                                data["debt_to_equity"] = round(borrow / total_equity, 2)
                            else:
                                data["debt_to_equity"] = 0.0
                        except IndexError:
                            pass

            # 6. Parse Shareholding Table (Institutional Holdings & Trend)
            # Inst. Holding = FIIs% + DIIs%
            shareholding_section = soup.find('section', id='shareholding')
            if shareholding_section:
                table = shareholding_section.find('table')
                if table:
                    rows = table.find('tbody').find_all('tr')
                    fii_vals = []
                    dii_vals = []
                    
                    for r in rows:
                        cells = [td.text.strip() for td in r.find_all('td')]
                        name = cells[0].replace('+', '').replace('\xa0', ' ').strip().lower()
                        if name == "fiis":
                            fii_vals = parse_cells(cells[1:])
                        elif name == "diis":
                            dii_vals = parse_cells(cells[1:])
                            
                    if len(fii_vals) > 0 and len(dii_vals) > 0:
                        # Align by index
                        latest_idx = -1
                        for idx in range(len(fii_vals) - 1, -1, -1):
                            if fii_vals[idx] is not None:
                                latest_idx = idx
                                break
                                
                        try:
                            fii_latest = fii_vals[latest_idx] or 0.0
                            dii_latest = dii_vals[latest_idx] or 0.0
                            data["institutional_holding"] = round(fii_latest + dii_latest, 2)
                            
                            # Check QoQ change (if previous value exists)
                            if latest_idx >= 1:
                                fii_prev = fii_vals[latest_idx - 1] or 0.0
                                dii_prev = dii_vals[latest_idx - 1] or 0.0
                                prev_total = fii_prev + dii_prev
                                data["institutional_holding_qoq_change"] = round((fii_latest + dii_latest) - prev_total, 2)
                        except IndexError:
                            pass
                            
            return data
            
        except Exception as e:
            logger.error(f"Error scraping fundamentals for {symbol}: {e}", exc_info=True)
            raise IngestionException(f"Failed to scrape fundamentals for {symbol}: {e}")

    def ingest_company_fundamentals(self, db: Session, symbol: str) -> CompanyFundamental:
        """Scrapes company fundamentals and stores them in the database"""
        try:
            data = self.scrape_company_fundamentals(symbol)
            
            db_fund = db.query(CompanyFundamental).filter(
                CompanyFundamental.symbol == symbol
            ).first()
            
            if not db_fund:
                db_fund = CompanyFundamental(**data)
                db.add(db_fund)
            else:
                for key, val in data.items():
                    setattr(db_fund, key, val)
                    
            db.commit()
            return db_fund
        except Exception as e:
            db.rollback()
            logger.error(f"Error saving fundamentals for {symbol}: {e}", exc_info=True)
            raise
