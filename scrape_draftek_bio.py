import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from tqdm import tqdm

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
}

base_url = "https://www.drafttek.com/2026-NFL-Draft-Big-Board/Top-NFL-Draft-Prospects-2026-Page-{}.asp"

all_players = []

print("🚀 Starting DraftTek 2026 scrape using BeautifulSoup (HTML parsing)...\n")

for page in tqdm(range(1, 7), desc="Scraping pages"):
    url = base_url.format(page)
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Look for any table on the page
    tables = soup.find_all('table')
    table_found = False
    
    for table in tables:
        rows = table.find_all('tr')
        if len(rows) < 5:
            continue
        
        # Check if this table has the right headers
        header_row = rows[0]
        headers_text = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
        
        if any("Rank" in h for h in headers_text) and any("Prospect" in h for h in headers_text):
            print(f"✅ Found prospects table on page {page}")
            table_found = True
            
            # Extract data
            data = []
            for row in rows[1:]:  # skip header
                cells = [cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])]
                if len(cells) >= 8:
                    # Try to extract BIO link if present
                    bio_link = None
                    bio_cell = row.find_all(['td', 'th'])[-1] if len(row.find_all(['td', 'th'])) > 0 else None
                    if bio_cell and bio_cell.find('a'):
                        bio_link = bio_cell.find('a')['href']
                    
                    player = {
                        'Rank': cells[0] if len(cells) > 0 else '',
                        'CNG': cells[1] if len(cells) > 1 else '',
                        'Prospect': cells[2] if len(cells) > 2 else '',
                        'College': cells[3] if len(cells) > 3 else '',
                        'POS': cells[4] if len(cells) > 4 else '',
                        'Ht': cells[5] if len(cells) > 5 else '',
                        'Wt': cells[6] if len(cells) > 6 else '',
                        'CLS': cells[7] if len(cells) > 7 else '',
                        'Bio_URL': bio_link
                    }
                    data.append(player)
            
            if data:
                df = pd.DataFrame(data)
                all_players.append(df)
                print(f"   → Parsed {len(df)} players")
            break
    
    if not table_found:
        print(f"⚠️  No suitable table found on page {page}")
    
    time.sleep(1.5)

# Combine and save
if all_players:
    final_df = pd.concat(all_players, ignore_index=True)
    
    print(f"\n🎉 SUCCESS! Total players scraped: {len(final_df)}")
    
    preview_cols = ['Rank', 'Prospect', 'College', 'POS', 'Ht', 'Wt', 'CLS', 'Bio_URL']
    available = [c for c in preview_cols if c in final_df.columns]
    print("\nFirst 5 players:")
    print(final_df.head()[available])
    
    final_df.to_csv("drafttek_2026_top600_with_bio.csv", index=False)
    final_df.to_json("drafttek_2026_top600_with_bio.json", orient="records", indent=2)
    
    print("\n✅ Files saved:")
    print("   • drafttek_2026_top600_with_bio.csv")
    print("   • drafttek_2026_top600_with_bio.json")
else:
    print("\n❌ No tables were parsed. The site structure may have changed again.")
