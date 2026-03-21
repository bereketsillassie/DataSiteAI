import requests
from bs4 import BeautifulSoup
import argparse
import json
import re

# State abbreviation to full name mapping
STATE_MAP = {
    'AL': 'alabama', 'AK': 'alaska', 'AZ': 'arizona', 'AR': 'arkansas',
    'CA': 'california', 'CO': 'colorado', 'CT': 'connecticut', 'DE': 'delaware',
    'FL': 'florida', 'GA': 'georgia', 'HI': 'hawaii', 'ID': 'idaho',
    'IL': 'illinois', 'IN': 'indiana', 'IA': 'iowa', 'KS': 'kansas',
    'KY': 'kentucky', 'LA': 'louisiana', 'ME': 'maine', 'MD': 'maryland',
    'MA': 'massachusetts', 'MI': 'michigan', 'MN': 'minnesota', 'MS': 'mississippi',
    'MO': 'missouri', 'MT': 'montana', 'NE': 'nebraska', 'NV': 'nevada',
    'NH': 'new hampshire', 'NJ': 'new jersey', 'NM': 'new mexico', 'NY': 'new york',
    'NC': 'north carolina', 'ND': 'north dakota', 'OH': 'ohio', 'OK': 'oklahoma',
    'OR': 'oregon', 'PA': 'pennsylvania', 'RI': 'rhode island', 'SC': 'south carolina',
    'SD': 'south dakota', 'TN': 'tennessee', 'TX': 'texas', 'UT': 'utah',
    'VT': 'vermont', 'VA': 'virginia', 'WA': 'washington', 'WV': 'west virginia',
    'WI': 'wisconsin', 'WY': 'wyoming'
}

def scrape_land_listings(location):
    """
    Scrape land listings from LandWatch.com for a given location.
    
    Args:
        location (str): Location like "Nashville, TN" or zip code
    
    Returns:
        list: List of dictionaries with listing details
    """
    # Format location for URL - use city-state format
    if ',' in location:
        city, state = location.split(',', 1)
        state = state.strip().upper()
        state_name = STATE_MAP.get(state, state.lower())
        city_name = city.strip().lower()
        formatted_location = f"{state_name}-land-for-sale/{city_name}"
    else:
        # Assume zip code
        formatted_location = f"zip-{location}"
    
    url = f"https://www.landwatch.com/{formatted_location}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        return []
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    listings = []
    
    # Find all listing links (they contain price and acres in the text)
    listing_links = soup.find_all('a', href=re.compile(r'/pid/\d+'))
    
    for link in listing_links:
        try:
            text = link.get_text().strip()
            
            # Extract price and acres from text like "$49,900,000 4.99 Acres"
            match = re.search(r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)\s+([\d.]+)\s+Acres?', text)
            if match:
                price = match.group(1)
                acreage = match.group(2)
                
                listing_url = link['href']
                if not listing_url.startswith('http'):
                    listing_url = f"https://www.landwatch.com{listing_url}"
                
                # Coordinates are typically not available on search pages
                coordinates = None
                
                listings.append({
                    'price': f"${price}",
                    'acreage': f"{acreage} Acres",
                    'coordinates': coordinates,
                    'listing_url': listing_url
                })
        
        except Exception as e:
            print(f"Error parsing listing: {e}")
            continue
    
    return listings

def main():
    parser = argparse.ArgumentParser(description='Scrape land listings for a given location')
    parser.add_argument('location', help='Location to search (e.g., "Nashville, TN" or zip code)')
    args = parser.parse_args()
    
    listings = scrape_land_listings(args.location)
    
    if listings:
        print(json.dumps(listings, indent=2))
    else:
        print("No listings found or error occurred.")

if __name__ == "__main__":
    main()
