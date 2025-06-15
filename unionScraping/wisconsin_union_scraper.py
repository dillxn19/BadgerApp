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

    # List of terms to exclude
    exclude_terms = [
        "Menu View", 
        "Map View", 
        "View Menu", 
        "View Map", 
        "Location",
        "Directions"
    ]

    with open("restaurants.csv", mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Restaurant Name"])  # CSV header

        for a_tag in a_tags:
            # Extract the visible text
            restaurant_name = a_tag.get_text(strip=True)
            
            # Skip if the name is in the exclude list or is empty
            if (restaurant_name and 
                not any(term.lower() in restaurant_name.lower() for term in exclude_terms)):
                writer.writerow([restaurant_name])

    print("Scraping complete. The CSV file 'restaurants.csv' has been created.")

if __name__ == "__main__":
    scrape_restaurants_to_csv()