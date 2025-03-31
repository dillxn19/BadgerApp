import os
import time
import csv
import re
import json
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pymongo
import certifi  # Import certifi to fix the SSL certificate issue
from threading import Lock

# Set up ChromeDriver with headless browser for faster operation
def create_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run headless for speed
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    
    # Set user agent (no need for fake_useragent library)
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36')
    
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Base URL
base_url = "https://union.wisc.edu"
target_url = f"{base_url}/dine/find-food-and-drink/"

# MongoDB setup with SSL certificate path to fix the verification issue
atlas_connection_string = "mongodb+srv://vedvedere:BadgerApp2025@badgerapp.hyriqxr.mongodb.net/?retryWrites=true&w=majority&appName=BadgerApp"
client = pymongo.MongoClient(
    atlas_connection_string,
    tlsCAFile=certifi.where(),  # Use certifi to provide the certificate
    maxPoolSize=50,
    connectTimeoutMS=5000,
    serverSelectionTimeoutMS=5000
)
db = client["BadgerApp"]
restaurant_collection = db["union_restaurants"]

# Global variables for file locking
csv_path = None
csv_lock = Lock()

def get_restaurant_links(driver):
    """
    Get all restaurant links from the Wisconsin Union dining page.
    
    Returns:
    list: List of dictionaries containing restaurant name and URL
    """
    # Navigate to the main page
    driver.get(target_url)
    print("Loaded Wisconsin Union dining page")
    
    # Use WebDriverWait instead of sleep
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "a"))
    )
    
    # Get the page source and parse with BeautifulSoup
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')
    
    # Compile regex pattern once for efficiency
    pattern = re.compile(r"^/dine/find-food-and-drink/[^/]+")
    a_tags = soup.find_all("a", href=pattern)
    
    # List of terms to exclude from the restaurant name
    exclude_terms = [
        "List View", "Menu View", "Map View", "View Menu", 
        "View Map", "Location", "Directions", "Go to top of page"
    ]
    
    # Use set for faster lookups
    exclude_terms_lower = {term.lower() for term in exclude_terms}
    
    restaurants = []
    # Use a set to track already processed restaurants and avoid duplicates
    processed_urls = set()
    
    for link in a_tags:
        restaurant_name = link.get_text(strip=True)
        href = link.get("href")
        restaurant_url = f"{base_url}{href}"
        
        # Skip if the URL has already been processed
        if restaurant_url in processed_urls:
            continue
            
        # Skip if the name is empty or contains an excluded term
        if not restaurant_name or any(term in restaurant_name.lower() for term in exclude_terms_lower):
            continue
        
        restaurants.append({
            'name': restaurant_name,
            'url': restaurant_url
        })
        processed_urls.add(restaurant_url)
        
        print(f"Found restaurant: {restaurant_name}")
    
    return restaurants

def extract_address(soup):
    """
    Extract address from restaurant page.
    """
    address = ""
    # Targeted approach to find address
    selectors = [
        ("div", "restaurant-page-location"),
        ("p", "address"),
        ("div", "location-info")
    ]
    
    for tag, class_name in selectors:
        address_section = soup.find(tag, class_=class_name)
        if address_section:
            # Remove any SVG or icon tags
            for tag in address_section.find_all(['svg', 'i']):
                tag.decompose()
            address = address_section.get_text(strip=True)
            break
    
    return address

def extract_hours(soup):
    """
    Extract operating hours from restaurant page.
    """
    hours = {}
    
    # More efficient selectors
    selectors = [
        ("ul", "hourset--list", lambda elem: extract_hours_from_list(elem)),
        (["section", "div"], ["hours", "hours-section"], lambda elem: extract_hours_from_section(elem))
    ]
    
    for tags, classes, extractor in selectors:
        if isinstance(tags, list):
            section = soup.find(tags, class_=classes)
        else:
            section = soup.find(tags, class_=classes)
        
        if section:
            result = extractor(section)
            if result:
                hours = result
                break
    
    return hours

def extract_hours_from_list(ul_hours):
    """Helper function to extract hours from list format"""
    hours = {}
    li_items = ul_hours.find_all("li", class_="hourset--list-item")
    for li in li_items:
        day_elem = li.find("span", class_="hourset--day")
        hours_elem = li.find("span", class_="hourset--hours")
        if day_elem and hours_elem:
            day = day_elem.get_text(strip=True).replace(":", "")
            time_text = hours_elem.get_text(strip=True)
            hours[day] = time_text
    return hours

def extract_hours_from_section(hours_section):
    """Helper function to extract hours from section format"""
    hours = {}
    # Attempt to pair days and times
    days = hours_section.find_all(["dt", "h3", "strong"])
    times = hours_section.find_all(["dd", "p", "span"])
    if len(days) == len(times) and len(days) > 0:
        for i in range(len(days)):
            day = days[i].get_text(strip=True).replace(":", "")
            time_text = times[i].get_text(strip=True)
            hours[day] = time_text
    else:
        # Alternate approach if the structure is different
        hour_items = hours_section.find_all(["li", "div"], class_=["hour-item", "day"])
        for item in hour_items:
            day_elem = item.find(["strong", "span", "h4"], class_=["day", "day-name"])
            time_elem = item.find(["span", "div"], class_=["time", "hours"])
            if day_elem and time_elem:
                day = day_elem.get_text(strip=True).replace(":", "")
                time_text = time_elem.get_text(strip=True)
                hours[day] = time_text
    return hours

def extract_menu_items(soup, restaurant_name):
    """
    Extract menu items from restaurant page.
    """
    menu_items = []
    
    # Pre-compile regex for price matching
    price_pattern = re.compile(r'\$\d+\.\d+|\$\d+')
    
    # Keywords for filtering - precompute lowercase versions
    menu_keywords = {"menu", "section", "category"}
    
    # Try to find menu sections
    menu_sections = soup.find_all(["section", "div"], class_=["menu", "menu-section", "category"])
    if not menu_sections:
        menu_sections = [soup]
    
    for section in menu_sections:
        # Look for menu items with specific classes
        items = section.find_all(["div", "li", "article"], class_=["menu-item", "item", "product"])
        if not items:
            # Try generic headings that might represent items
            possible_items = section.find_all(["h3", "h4", "strong"])
            for item in possible_items:
                item_name = item.get_text(strip=True)
                if not item_name or any(keyword in item_name.lower() for keyword in menu_keywords):
                    continue
                
                price = ""
                price_elem = item.find_next(["span", "div"], class_=["price", "cost"])
                if price_elem:
                    price = price_elem.get_text(strip=True)
                else:
                    next_text = item.next_sibling
                    if next_text and "$" in str(next_text):
                        price_match = price_pattern.search(str(next_text))
                        if price_match:
                            price = price_match.group(0)
                menu_items.append({
                    "name": item_name,
                    "price": price
                })
        else:
            # Process standard menu items
            for item in items:
                item_name = ""
                item_price = ""
                name_elem = item.find(["h3", "h4", "strong", "span"], class_=["item-name", "name", "title"])
                if name_elem:
                    item_name = name_elem.get_text(strip=True)
                else:
                    possible_name = item.find(["h3", "h4", "strong"])
                    if possible_name:
                        item_name = possible_name.get_text(strip=True)
                
                if not item_name:
                    continue
                    
                price_elem = item.find(["span", "div"], class_=["item-price", "price", "cost"])
                if price_elem:
                    item_price = price_elem.get_text(strip=True)
                else:
                    item_text = item.get_text()
                    price_match = price_pattern.search(item_text)
                    if price_match:
                        item_price = price_match.group(0)
                
                menu_items.append({
                    "name": item_name,
                    "price": item_price
                })
    
    return menu_items

def process_restaurant(restaurant):
    """
    Process a single restaurant - for parallel execution
    """
    try:
        restaurant_name = restaurant['name']
        restaurant_url = restaurant['url']
        print(f"Processing restaurant: {restaurant_name}")
        
        # Create a new driver for each thread
        driver = create_driver()
        
        try:
            # Navigate to the restaurant page
            driver.get(restaurant_url)
            # Wait for page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Extract address, hours, and menu items
            address = extract_address(soup)
            hours = extract_hours(soup)
            menu_items = extract_menu_items(soup, restaurant_name)
            
            # If no menu items are found, try following a menu link
            if not menu_items:
                menu_link = None
                for a in soup.find_all("a", href=True):
                    link_text = a.get_text().lower()
                    if "menu" in link_text or "food" in link_text or "order" in link_text:
                        menu_link = a.get("href")
                        if not menu_link.startswith("http"):
                            menu_link = f"{base_url}{menu_link}"
                        break
                        
                if menu_link:
                    print(f"Following menu link: {menu_link}")
                    driver.get(menu_link)
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    menu_page_source = driver.page_source
                    menu_soup = BeautifulSoup(menu_page_source, 'html.parser')
                    menu_items = extract_menu_items(menu_soup, restaurant_name)
            
            # Prepare the restaurant document
            restaurant_data = {
                "name": restaurant_name,
                "url": restaurant_url,
                "address": address,
                "hours": hours,
                "menu_items": menu_items,
                "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Insert or update the restaurant data in MongoDB
            restaurant_collection.update_one(
                {"name": restaurant_name},
                {"$set": restaurant_data},
                upsert=True
            )
            
            # Append basic info to CSV (using global lock to avoid race conditions)
            with csv_lock:
                with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        restaurant_name, 
                        address, 
                        len(hours.keys()),
                        len(menu_items)
                    ])
            
            print(f"Saved data for {restaurant_name} - Found {len(menu_items)} menu items")
            return {
                "name": restaurant_name,
                "status": "success",
                "menu_items": len(menu_items)
            }
                
        except Exception as e:
            print(f"Error processing {restaurant_name}: {e}")
            return {
                "name": restaurant_name,
                "status": "error",
                "error": str(e)
            }
        finally:
            driver.quit()
                
    except Exception as e:
        print(f"Error in process_restaurant for {restaurant.get('name', 'unknown')}: {e}")
        return {
            "name": restaurant.get('name', 'unknown'),
            "status": "error",
            "error": str(e)
        }

def scrape_restaurant_data():
    """
    Scrape restaurant data and save to MongoDB using parallel processing.
    """
    global csv_path
    
    try:
        # Verify MongoDB connection before proceeding
        try:
            # Test MongoDB connection
            db.command('ping')
            print("MongoDB connection successful!")
        except Exception as e:
            print(f"MongoDB connection failed: {e}")
            print("Please check your MongoDB Atlas connection string and network connectivity.")
            return
        
        # Create main driver for getting restaurant links
        main_driver = create_driver()
        
        # Get all restaurant links from the main dining page
        restaurants = get_restaurant_links(main_driver)
        main_driver.quit()
        
        print(f"\nFound {len(restaurants)} restaurants")
        
        # Create a CSV file to log basic restaurant data
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if not script_dir:  # If running from a terminal without file path
            script_dir = os.getcwd()
        csv_path = os.path.join(script_dir, "wisconsin_union_restaurants.csv")
        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Restaurant Name", "Address", "Days Open", "Menu Items Count"])
        
        # Use ThreadPoolExecutor for parallel processing
        results = []
        max_workers = min(5, len(restaurants))  # Don't create more workers than restaurants
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all restaurants for processing
            future_to_restaurant = {executor.submit(process_restaurant, restaurant): restaurant for restaurant in restaurants}
            
            # Process results as they complete
            for future in future_to_restaurant:
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    restaurant = future_to_restaurant[future]
                    print(f'{restaurant.get("name", "Unknown")} generated an exception: {exc}')
        
        # Summarize results
        success_count = sum(1 for r in results if r.get("status") == "success")
        print(f"\nScraping complete. Successfully processed {success_count} out of {len(restaurants)} restaurants.")
        print(f"Data has been saved to MongoDB and CSV ({csv_path}).")
                
    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        # Close the MongoDB connection properly
        client.close()

if __name__ == "__main__":
    # First, make sure the certifi package is installed
    try:
        import certifi
    except ImportError:
        print("The certifi package is required but not installed.")
        print("Please install it using: pip install certifi")
        exit(1)
        
    scrape_restaurant_data()