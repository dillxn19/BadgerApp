import re
import csv
import requests
from bs4 import BeautifulSoup

def scrape_restaurants_to_csv():
    base_url = "https://union.wisc.edu"
    target_url = f"{base_url}/dine/find-food-and-drink/"
    response = requests.get(target_url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Regex to match hrefs that begin with "/dine/find-food-and-drink/" 
    # and have some text after that (e.g., "/strada/", "/der-rathskeller/", etc.)
    pattern = re.compile(r"^/dine/find-food-and-drink/[^/]+")

    # Find all <a> tags whose "href" matches the pattern
    a_tags = soup.find_all("a", href=pattern)

    # Define a set of terms to exclude
    blocked_terms = {
        "Restaurant Name",
        "List View",
        "Map View",
        "Go to top of page"
    }

    with open("restaurants.csv", mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Restaurant Name"])  # CSV header

        for a_tag in a_tags:
            # Extract the visible text
            restaurant_name = a_tag.get_text(strip=True)
            
            # Skip any unwanted terms
            if restaurant_name and restaurant_name not in blocked_terms:
                writer.writerow([restaurant_name])

    print("Scraping complete. The CSV file 'restaurants.csv' has been created.")

if __name__ == "__main__":
    scrape_restaurants_to_csv()

