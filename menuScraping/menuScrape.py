import os
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from datetime import datetime
from selenium.webdriver.common.keys import Keys
from pymongo import MongoClient


def clean_for_url(text):
    """Clean text for use in URLs by removing special characters and formatting."""
    text = text.replace("'", "")
    text = re.sub(r'[^a-zA-Z0-9-]', '', text.replace(" ", "-"))
    return text.lower()

# Set up ChromeDriver with headless option
options = webdriver.ChromeOptions()
options.add_argument('--headless')  # Only change made - added this line
options.add_argument('--start-maximized')  # Maximize browser window
options.add_argument('--disable-extensions')
options.add_experimental_option("prefs", {
    "profile.default_content_setting_values.geolocation": 1  # 1 = allow
})

# Initialize the driver (rest of the code remains exactly the same)
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
# Base URL
base_url = "https://wisc-housingdining.nutrislice.com/"

def get_dining_locations():
    """Get all dining locations with cleaned URLs."""
    driver.get(base_url)
    print("Loaded main page")
    
    try:
        # Try multiple selectors for View Menus button
        view_menus_selectors = [
            "button.primary[data-testid='018026bcdb3445168421175d9ae4dd06']",
            "//button[contains(text(), 'View Menus')]",
            "button.primary"
        ]
        
        for selector in view_menus_selectors:
            try:
                if selector.startswith("//"):
                    button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, selector)))
                else:
                    button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                button.click()
                print(f"Clicked 'View Menus' using selector: {selector}")
                break
            except Exception as click_error:
                print(f"Failed to click with selector {selector}: {click_error}")
                continue
        else:
            raise Exception("Could not find 'View Menus' button")
                
        # Handle "Let's do it" button if it appears
        try:
            lets_do_it = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), \"Let's do it\")]")))
            lets_do_it.click()
            print("Clicked 'Let's do it' button")
        except:
            print("'Let's do it' button not found or not needed")
        
        # Wait for content to load
        time.sleep(8)
        
        # Find all location containers
        location_elements = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.content-container")))
        
        locations = []
        for elem in location_elements:
            try:
                # Extract name
                name_elem = elem.find_element(By.CSS_SELECTOR, "div.label")
                name = name_elem.text.strip() if name_elem else "Unknown"
                
                # Extract address
                address_elem = elem.find_element(By.CSS_SELECTOR, "div.address")
                address = address_elem.text.strip() if address_elem else "Address not found"
                
                # Generate cleaned URL
                clean_name = clean_for_url(name)
                link = f"https://wisc-housingdining.nutrislice.com/menu/{clean_name}"
                
                # Extract hours information and create hours object
                hours_data = {}
                date_of_operation = ""
                
                try:
                    hours_container = elem.find_element(By.XPATH, "ancestor::div[contains(@class, 'location')]//ul[contains(@class, 'menu-hours')]")
                    
                    try:
                        dates_elem = hours_container.find_element(By.XPATH, ".//li[contains(.,'Dates of Operation')]")
                        dates = dates_elem.find_element(By.CSS_SELECTOR, "span.time").text.strip()
                        date_of_operation = dates
                    except:
                        pass
                    
                    meal_types = ['Breakfast', 'Lunch', 'Dinner']
                    for meal_type in meal_types:
                        try:
                            meal_elem = hours_container.find_element(By.XPATH, f".//li[contains(.,'{meal_type}')]")
                            time_elem = meal_elem.find_element(By.CSS_SELECTOR, "span.time")
                            hours = time_elem.text.strip()
                            hours = hours.split(' ', 1)[0] if 'chevron' in hours else hours
                            hours_data[meal_type.lower()] = hours
                        except:
                            hours_data[meal_type.lower()] = ""
                
                except:
                    pass
                
                location_data = {
                    'location_name': name,
                    'date_of_operation': date_of_operation,
                    'location': address,
                    'link': link,
                    'hours': hours_data,
                    'breakfast': [],
                    'lunch': [],
                    'dinner': []
                }
                
                if name and name != "Unknown":
                    locations.append(location_data)
                    print(f"Added {name} with URL: {link}")
                
            except Exception as e:
                print(f"Error processing a location element: {e}")
        
        if not locations:
            raise Exception("No locations found")
        
        return locations
    
    except Exception as e:
        print(f"Error in get_dining_locations: {e}")
        raise

def extract_nutrition_facts(driver, item_element):
    """
    Click on an item element and extract detailed nutrition information from the popup
    
    Args:
    driver: Selenium WebDriver instance
    item_element: WebElement representing the menu item
    
    Returns:
    dict: Dictionary containing all nutrition facts
    """
    nutrition_data = {
        'serving_size': 'N/A',
        'calories': 'N/A',
        'total_fat': 'N/A',
        'saturated_fat': 'N/A',
        'trans_fat': 'N/A',
        'cholesterol': 'N/A',
        'sodium': 'N/A',
        'total_carbohydrate': 'N/A',
        'dietary_fiber': 'N/A',
        'total_sugars': 'N/A',
        'protein': 'N/A',
        'calcium': 'N/A',
        'iron': 'N/A',
        'potassium': 'N/A',
    }
    
    try:
        # Click on the menu item to open the nutrition popup
        item_element.click()
        
        # Wait for nutrition facts to appear - looking specifically for the active modal
        # Shorter timeout (3 seconds instead of 10)
        nutrition_header = WebDriverWait(driver, 4).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "li.modal.active div.nutrition-facts-header"))
        )
        
        # Extract all nutrition data at once using JavaScript for better performance
        nutrition_script = """
        function extractNutritionData() {
            const modal = document.querySelector('li.modal.active');
            if (!modal) return {};
            
            const data = {
                'serving_size': 'N/A',
                'calories': 'N/A'
            };
            
            // Extract serving size
            const servingSizeContainer = modal.querySelector('div.serving-size');
            if (servingSizeContainer) {
                const divs = servingSizeContainer.querySelectorAll(':scope > div');
                if (divs.length >= 2) {
                    data['serving_size'] = divs[1].textContent.trim();
                }
            }
            
            // Extract calories
            const caloriesRow = modal.querySelector('div.calories-row');
            if (caloriesRow) {
                const caloriesDiv = caloriesRow.querySelector('div:not(.bold)');
                if (caloriesDiv) {
                    data['calories'] = caloriesDiv.textContent.trim();
                }
            }
            
            // Create a mapping of labels to our data keys
            const labelMapping = {
                'total fat': 'total_fat',
                'saturated fat': 'saturated_fat',
                'trans fat': 'trans_fat',
                'cholesterol': 'cholesterol',
                'sodium': 'sodium',
                'total carbohydrate': 'total_carbohydrate',
                'dietary fiber': 'dietary_fiber',
                'total sugars': 'total_sugars',
                'protein': 'protein',
                'calcium': 'calcium',
                'iron': 'iron',
                'potassium': 'potassium'
            };
            
            // Extract all nutrition values at once
            const nutritionRows = modal.querySelectorAll('div.nutrition-row');
            nutritionRows.forEach(row => {
                const labelDiv = row.querySelector('div.nutrition-label');
                if (!labelDiv) return;
                
                const spans = labelDiv.querySelectorAll('span');
                if (spans.length < 2) return;
                
                const label = spans[0].textContent.trim().toLowerCase();
                const value = spans[1].textContent.trim();
                
                // Match the label to our keys
                for (const [labelText, dataKey] of Object.entries(labelMapping)) {
                    if (label.includes(labelText)) {
                        data[dataKey] = value;
                        break;
                    }
                }
            });
            
            return data;
        }
        return extractNutritionData();
        """
        
        # Execute JS and get data directly
        js_result = driver.execute_script(nutrition_script)
        
        # Update our data dictionary with non-null values from JS
        for key, value in js_result.items():
            if value and value != 'N/A':
                nutrition_data[key] = value
        
        # Close the popup immediately with JavaScript (faster than finding and clicking elements)
        driver.execute_script("""
            const closeButton = document.querySelector('li.modal.active a.modal-carousel.close');
            if (closeButton) closeButton.click();
        """)
        
        return nutrition_data
    
    except Exception as e:
        print(f"Error extracting nutrition facts:")
        # Try to close any open modals with direct JavaScript
        try:
            driver.execute_script("document.querySelector('li.modal.active a.modal-carousel.close').click();")
        except:
            try:
                # Fallback to Escape key
                webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            except:
                pass
        return nutrition_data

def is_duplicate_item(existing_items, new_item):
    """Check if an item already exists in the list with all the same attributes"""
    for item in existing_items:
        if (item['item_name'] == new_item['item_name'] and
            item['serving_size'] == new_item['serving_size'] and
            item['calories'] == new_item['calories']):
            return True
    return False

def extract_menu_items(driver, meal_type, max_retries=3):
    """
    Extract menu items from the page for a specific meal type, including nutrition facts.
    Uses batch processing for better performance. Retries if menu fails to load.
    
    Args:
    driver: Selenium WebDriver instance
    meal_type: Type of meal (breakfast, lunch, dinner)
    max_retries: Maximum number of retry attempts
    
    Returns:
    list: List of menu items with nutrition data
    """
    items = []
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            # First, collect all basic menu item data in one pass using JavaScript
            # This avoids repeated DOM queries and is much faster
            js_collect_items = """
            function collectMenuItems() {
                const items = [];
                const menuElements = document.querySelectorAll('ns-menu-item-food');
                
                menuElements.forEach((item, index) => {
                    // Get basic info
                    const nameElem = item.querySelector('span.food-name');
                    const name = nameElem ? nameElem.textContent.trim() : 'Unknown';
                    
                    // Get traits
                    const traits = [];
                    const traitElems = item.querySelectorAll('div.custom-icon');
                    traitElems.forEach(trait => {
                        const style = trait.getAttribute('style');
                        const traitMatch = style.match(/Food_Trait_Icons_([^-]+)/);
                        if (traitMatch) {
                            traits.push(traitMatch[1]);
                        }
                    });
                    
                    items.push({
                        index: index,
                        name: name,
                        traits: traits.join(', ')
                    });
                });
                
                return items;
            }
            return collectMenuItems();
            """
            
            # Wait for menu items to appear, use a shorter timeout
            WebDriverWait(driver, 12).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ns-menu-item-food"))
            )
            
            # Get basic info for all items at once
            basic_items = driver.execute_script(js_collect_items)
            print(f"Found {len(basic_items)} menu items for {meal_type}")
            
            if not basic_items:
                # If we didn't find any items but didn't get an exception,
                # it could be an empty menu, not a loading error
                print(f"Menu appears to be empty for {meal_type}")
                return items
                
            # Create a list to store fully processed items
            for item_data in basic_items:
                try:
                    # Get item basic data from our JavaScript result
                    name = item_data['name']
                    traits = item_data['traits']
                    index = item_data['index']
                    
                    # Create basic item dictionary
                    item_dict = {
                        'item_name': name,
                        'dietary_traits': traits
                    }
                    
                    print(f"Processing item {index+1}/{len(basic_items)}: {name}")
                    
                    # Get a fresh reference to the menu item element
                    menu_items = driver.find_elements(By.CSS_SELECTOR, "ns-menu-item-food")
                    if index >= len(menu_items):
                        print(f"Item index {index} no longer exists, skipping")
                        continue
                    
                    item_element = menu_items[index]
                    
                    # Scroll item into view with JavaScript (faster than Selenium's scrollIntoView)
                    driver.execute_script("""
                        arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});
                    """, item_element)
                    
                    # Get nutrition facts
                    nutrition_data = extract_nutrition_facts(driver, item_element)
                    item_dict.update(nutrition_data)
                    
                    # Check for duplicates before adding
                    if not is_duplicate_item(items, item_dict):
                        items.append(item_dict)
                        print(f"Added {name}")
                    else:
                        print(f"Skipping duplicate item: {name}")
                    
                except Exception as e:
                    print(f"Error processing menu item {index+1}: {e}")
                    continue
            
            # If we reach here with no exceptions, we're done
            return items
        
        except Exception as e:
            retry_count += 1
            if retry_count <= max_retries:
                print(f"Error extracting menu items: {e}")
                print(f"Retrying... (Attempt {retry_count} of {max_retries})")
                
                # Refresh the page and wait a bit longer each retry
                driver.refresh()
                time.sleep(7 + (retry_count * 3))  # Progressively wait longer
            else:
                print(f"Failed to extract menu items after {max_retries} attempts: {e}")
                return items  # Return empty list after all retries fail
    
    return items

def load_menu_page_with_retries(driver, menu_link, max_retries=3):
    """
    Loads a menu page with retry logic
    
    Args:
    driver: Selenium WebDriver instance
    menu_link: URL to load
    max_retries: Maximum number of retry attempts
    
    Returns:
    bool: True if page loaded successfully, False otherwise
    """
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            driver.get(menu_link)
            
            # Wait for the page to load with progressively longer wait times
            wait_time = 7 + (retry_count * 2)
            print(f"Waiting {wait_time} seconds for page to load...")
            time.sleep(wait_time)
            
            # Check if menu items are present using JavaScript
            has_items = driver.execute_script("""
                return document.querySelectorAll('ns-menu-item-food').length > 0;
            """)
            
            if has_items:
                print("Menu page loaded successfully")
                return True
            else:
                print("Menu page loaded but no items found")
                retry_count += 1
                if retry_count <= max_retries:
                    print(f"Retrying... (Attempt {retry_count} of {max_retries})")
                    driver.refresh()
                else:
                    print(f"Failed to load menu items after {max_retries} attempts")
                    return False
        
        except Exception as e:
            retry_count += 1
            if retry_count <= max_retries:
                print(f"Error loading menu page: {e}")
                print(f"Retrying... (Attempt {retry_count} of {max_retries})")
            else:
                print(f"Failed to load menu page after {max_retries} attempts: {e}")
                return False
    
    return False

def get_menu_for_location(location):
    """
    Get menu items for a specific location for all meal types.
    
    Args:
    location (dict): Dictionary containing location information
    
    Returns:
    dict: Updated location dictionary with menu items
    """
    current_date = datetime.now().strftime('%Y-%m-%d')
    updated_location = location.copy()
    
    meal_types = ['breakfast', 'lunch', 'dinner']
    
    for meal_type in meal_types:
        try:
            # Skip if this location doesn't serve this meal type
            if meal_type not in location.get('hours', {}):
                print(f"Skipping {location['location_name']} for {meal_type} - no hours listed")
                continue
                
            # Skip if this location is closed for this meal type
            hours_value = location['hours'].get(meal_type, "")
            if not hours_value or hours_value.lower() == "closed":
                print(f"Skipping {location['location_name']} for {meal_type} - listed as closed")
                # Keep empty array for this meal type
                updated_location[meal_type] = []
                continue
                
            # Generate menu link for current date and meal type
            menu_link = f"{location['link']}/{meal_type}/{current_date}"
            print(f"Loading menu for {location['location_name']} - {meal_type}")
            
            # Load the menu page with retries
            if load_menu_page_with_retries(driver, menu_link, max_retries=3):
                # Extract menu items with retries
                menu_items = extract_menu_items(driver, meal_type, max_retries=3)
                
                # Add menu items to the location dictionary
                updated_location[meal_type] = menu_items
                
                print(f"Added {len(menu_items)} {meal_type} items for {location['location_name']}")
            else:
                print(f"Could not load menu for {location['location_name']} - {meal_type}")
                updated_location[meal_type] = []  # Empty array for failed scrapes
        
        except Exception as e:
            print(f"Error getting {meal_type} menu for {location['location_name']}: {e}")
            # Keep empty array for this meal type on error
            updated_location[meal_type] = []
    
    return updated_location

def save_to_mongodb(data, db_name="BadgerApp", collection_name="dining_hall"):
    """
    Save data to MongoDB.
    
    Args:
    data: Data to save
    db_name: Name of the database
    collection_name: Name of the collection
    
    Returns:
    bool: True if successful, False otherwise
    """
    try:
        # MongoDB connection string
        # Default is localhost:27017, change this if your MongoDB server is elsewhere
        mongo_uri = "mongodb://localhost:27017/"
        
        # Create a MongoDB client
        client = MongoClient(mongo_uri)
        
        # Get database and collection
        db = client[db_name]
        collection = db[collection_name]
        
        # Add timestamp to data
        scrape_timestamp = datetime.now()
        for item in data:
            item['scrape_date'] = scrape_timestamp
            
        # Clear existing data from today to avoid duplicates
        # We're using the scrape_date field to only delete today's records
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        collection.delete_many({"scrape_date": {"$gte": today_start}})
        
        # Insert the new data
        if data:  # Only attempt insert if we have data
            collection.insert_many(data)
            print(f"Saved {len(data)} dining locations to MongoDB: {db_name}.{collection_name}")
        else:
            print("No data to save to MongoDB")
        
        return True
        
    except Exception as e:
        print(f"Error saving to MongoDB: {e}")
        return False

# Main function
if __name__ == "__main__":
    try:
        # Get dining locations
        dining_locations = get_dining_locations()
        
        if dining_locations:
            print(f"\nFound {len(dining_locations)} dining locations")
            
            # List to store all locations with their menu data
            all_location_data = []
            
            # Process each location
            for location in dining_locations:
                # Get menu items for all meal types
                location_with_menu = get_menu_for_location(location)
                
                # Add to our list
                all_location_data.append(location_with_menu)
            
            # Save all data to MongoDB
            if save_to_mongodb(all_location_data):
                print("All dining hall menus have been saved to MongoDB")
            else:
                print("Failed to save data to MongoDB")
        else:
            print("No dining locations found!")
    
    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        driver.quit()