import os
import csv
import re
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
import certifi
from threading import Lock

def create_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36')
    
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Base URL
base_url = "https://union.wisc.edu"
target_url = f"{base_url}/dine/find-food-and-drink/"

# MongoDB setup
# MongoDB setup with improved error handling
try:
    print("Attempting to connect to MongoDB Atlas...")
    atlas_connection_string = "mongodb+srv://vedvedere:BadgerApp2025@badgerapp.hyriqxr.mongodb.net/?retryWrites=true&w=majority&appName=BadgerApp"
    
    # Increase the timeout values
    client = pymongo.MongoClient(
        atlas_connection_string,
        tlsCAFile=certifi.where(),
        maxPoolSize=50,
        connectTimeoutMS=30000,  # Increased from 5000 to 30000
        serverSelectionTimeoutMS=30000,  # Increased from 5000 to 30000
        socketTimeoutMS=45000  # Added socket timeout
    )
    
    # Force a connection to verify it works
    client.admin.command('ping')
    print("MongoDB connection successful!")
    
    db = client["BadgerApp"]
    restaurant_collection = db["union_restaurants"]

except pymongo.errors.ConfigurationError as e:
    print(f"MongoDB configuration error: {e}")
    print("This usually means the connection string is invalid")
    exit(1)
except pymongo.errors.ConnectionFailure as e:
    print(f"MongoDB connection failure: {e}")
    print("This usually means the MongoDB server is not reachable")
    exit(1)
except pymongo.errors.ServerSelectionTimeoutError as e:
    print(f"MongoDB server selection timeout: {e}")
    print("This could be due to network issues or incorrect hostname")
    exit(1)
except Exception as e:
    print(f"Unexpected MongoDB error: {e}")
    exit(1)

def get_restaurant_links(driver):
    """Get all restaurant links from the Wisconsin Union dining page."""
    driver.get(target_url)
    print("Loaded Wisconsin Union dining page")
    
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "a"))
    )
    
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')
    
    pattern = re.compile(r"^/dine/find-food-and-drink/[^/]+")
    a_tags = soup.find_all("a", href=pattern)
    
    exclude_terms_lower = {"list view", "menu view", "map view", "view menu", 
                           "view map", "location", "directions", "go to top of page"}
    
    restaurants = []
    processed_urls = set()
    
    for link in a_tags:
        restaurant_name = link.get_text(strip=True)
        href = link.get("href")
        restaurant_url = f"{base_url}{href}"
        
        if restaurant_url in processed_urls:
            continue
            
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
    """Extract address from restaurant page."""
    address = ""
    selectors = [
        ("div", "restaurant-page-location"),
        ("p", "address"),
        ("div", "location-info")
    ]
    
    for tag, class_name in selectors:
        address_section = soup.find(tag, class_=class_name)
        if address_section:
            for tag in address_section.find_all(['svg', 'i']):
                tag.decompose()
            address = address_section.get_text(strip=True)
            break
    
    return address

def extract_hours(soup):
    """Extract operating hours from restaurant page as a structured dictionary."""
    hours = {}
    
    # Try to find hours elements with common class names
    hours_section = soup.find(["div", "section"], class_=["hours", "restaurant-hours", "hours-section"])
    
    if hours_section:
        # Look for day-hour pairs in various formats
        day_hour_pairs = []
        
        # Check for list format
        day_hours_list = hours_section.find_all("li")
        if day_hours_list:
            for item in day_hours_list:
                text = item.get_text(strip=True)
                # Try to split by common separators
                for separator in [':', '-', '–']:
                    if separator in text:
                        day, time = text.split(separator, 1)
                        day_hour_pairs.append((day.strip(), time.strip()))
                        break
        
        # Check for definition list format
        if not day_hour_pairs:
            days = hours_section.find_all(["dt", "h3", "strong", "span"])
            times = hours_section.find_all(["dd", "p", "div"])
            
            if len(days) == len(times) and len(days) > 0:
                for i in range(len(days)):
                    day = days[i].get_text(strip=True).replace(":", "")
                    time = times[i].get_text(strip=True)
                    day_hour_pairs.append((day, time))
        
        # If we found pairs, process them
        for day, time in day_hour_pairs:
            day = day.strip().rstrip(':').title()  # Standardize day format
            hours[day] = time.strip()
    
    return hours

def extract_menu_categories_and_items(soup):
    """Extract menu categories and their items as a structured dictionary."""
    menu_data = {}
    
    # Look for menu sections (accordion buttons)
    menu_sections = soup.find_all(["button", "div", "h3"], 
                                 class_=["accordion-button", "menu-section", "category-heading"])
    
    # If no explicit sections found, create a default "Menu" section
    if not menu_sections:
        menu_data["Menu"] = extract_items_from_section(soup)
        return menu_data
    
    # Process each menu section
    for section in menu_sections:
        section_name = section.get_text(strip=True)
        
        # Skip if empty or too generic
        if not section_name or section_name.lower() in ["menu", "our menu"]:
            section_name = "Main Menu"
        
        # Find the content associated with this section
        # First try next sibling or parent's next sibling
        content_section = section.find_next_sibling(["div", "ul", "section"])
        
        # If not found, look for section with matching ID
        if not content_section and section.get('id'):
            section_id = section.get('id')
            content_section = soup.find("div", {"aria-labelledby": section_id})
        
        # If still not found, use the parent or grandparent container
        if not content_section:
            content_section = section.parent
            if not content_section.find_all(class_="restaurant-menu--menus--category-menu-item"):
                content_section = content_section.parent
        
        # Extract items from this section
        items = extract_items_from_section(content_section)
        
        # Only add sections with items
        if items:
            menu_data[section_name] = items
    
    # If no items found in sections, try extracting from the whole page
    if not menu_data:
        menu_data["Menu"] = extract_items_from_section(soup)
    
    return menu_data

def extract_items_from_section(section):
    """Extract menu items from a specific section."""
    items = []
    
    # First try the specific class mentioned
    menu_items = section.find_all("div", class_="restaurant-menu--menus--category-menu-item")
    
    if menu_items:
        for item in menu_items:
            name_elem = item.find("span", class_="restaurant-menu--menus--category-menu-item--title")
            if name_elem:
                name = name_elem.get_text(strip=True)
                # Check for price in the text
                price = ""
                price_match = re.search(r'\$\d+\.\d+|\$\d+', item.get_text())
                if price_match:
                    price = price_match.group(0)
                
                items.append({"name": name, "price": price})
    
    # If no specific class items found, try generic item formats
    if not items:
        # Look for any elements that might contain menu items
        possible_items = section.find_all(["div", "li", "article"], 
                                        class_=["menu-item", "item", "product", "dish"])
        
        for item in possible_items:
            item_name = ""
            item_price = ""
            
            # Try to find name and price
            name_elem = item.find(["h3", "h4", "span", "strong"], 
                                 class_=["item-name", "name", "title", "dish-name"])
            if name_elem:
                item_name = name_elem.get_text(strip=True)
            
            price_elem = item.find(["span", "div"], 
                                  class_=["item-price", "price", "cost"])
            if price_elem:
                item_price = price_elem.get_text(strip=True)
            else:
                # Try to find price using regex
                item_text = item.get_text()
                price_match = re.search(r'\$\d+\.\d+|\$\d+', item_text)
                if price_match:
                    item_price = price_match.group(0)
            
            if item_name:
                items.append({"name": item_name, "price": item_price})
    
    return items

def process_restaurant(restaurant):
    """Process a single restaurant - for parallel execution"""
    try:
        restaurant_name = restaurant['name']
        restaurant_url = restaurant['url']
        print(f"Processing restaurant: {restaurant_name}")
        
        # Create a new driver for each thread
        driver = create_driver()
        
        try:
            # Navigate to the restaurant page
            driver.get(restaurant_url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Extract address, hours, and menu items
            address = extract_address(soup)
            hours = extract_hours(soup)
            menu_data = extract_menu_categories_and_items(soup)
            
            # If no menu items are found, try following a menu link
            if not any(menu_data.values()):
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
                    menu_data = extract_menu_categories_and_items(menu_soup)
            
            # Calculate total menu items
            total_menu_items = sum(len(items) for items in menu_data.values())
            
            # Prepare the restaurant document
            restaurant_data = {
                "name": restaurant_name,
                "url": restaurant_url,
                "address": address,
                "hours": hours,
                "menu_categories": menu_data,
                "total_menu_items": total_menu_items,
                "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Insert or update the restaurant data in MongoDB
            restaurant_collection.update_one(
                {"name": restaurant_name},
                {"$set": restaurant_data},
                upsert=True
            )
            
            # Example of hours for CSV output
            hours_sample = '; '.join([f"{day}: {time}" for day, time in hours.items()][:2])
            if len(hours) > 2:
                hours_sample += f"; + {len(hours) - 2} more days"
            
            # Append basic info to CSV
            with csv_lock:
                with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        restaurant_name, 
                        address, 
                        hours_sample,
                        total_menu_items,
                        ', '.join(list(menu_data.keys())[:3])
                    ])
            
            print(f"Saved data for {restaurant_name} - Found {total_menu_items} menu items in {len(menu_data)} categories")
            return {
                "name": restaurant_name,
                "status": "success",
                "menu_categories": len(menu_data),
                "menu_items": total_menu_items
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
    #"""Scrape restaurant data and save to MongoDB using parallel processing."""
    global csv_path, csv_lock  # Add csv_lock to the global statement
    
    # Create a lock for CSV writing
    csv_lock = Lock()
    
    try:
        # Verify MongoDB connection
        try:
            db.command('ping')
            print("MongoDB connection successful!")
        except Exception as e:
            print(f"MongoDB connection failed: {e}")
            return
        
        # Create main driver for getting restaurant links
        main_driver = create_driver()
        restaurants = get_restaurant_links(main_driver)
        main_driver.quit()
        
        print(f"\nFound {len(restaurants)} restaurants")
        
        # Create a CSV file with expanded format
        script_dir = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
        csv_path = os.path.join(script_dir, "wisconsin_union_restaurants.csv")
        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Restaurant Name", "Address", "Sample Hours", "Menu Items Count", "Menu Categories"])
        
        # Process restaurants in parallel
        results = []
        max_workers = min(5, len(restaurants))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_restaurant = {executor.submit(process_restaurant, restaurant): restaurant for restaurant in restaurants}
            
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
        client.close()

if __name__ == "__main__":
    try:
        import certifi
    except ImportError:
        print("The certifi package is required but not installed.")
        print("Please install it using: pip install certifi")
        exit(1)
        
    scrape_restaurant_data()