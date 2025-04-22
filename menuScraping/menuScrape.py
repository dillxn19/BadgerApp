import os
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import csv
from datetime import datetime
from bs4 import BeautifulSoup
from selenium.webdriver.common.keys import Keys

def clean_for_url(text):
    """Clean text for use in URLs by removing special characters and formatting."""
    text = text.replace("'", "")
    text = re.sub(r'[^a-zA-Z0-9-]', '', text.replace(" ", "-"))
    return text.lower()

# Set up ChromeDriver with visible browser options
options = webdriver.ChromeOptions()
options.add_argument('--start-maximized')  # Maximize browser window
options.add_argument('--disable-extensions')
options.add_experimental_option("prefs", {
    "profile.default_content_setting_values.geolocation": 1  # 1 = allow
})

# Initialize the driver
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
                
                # Extract hours information
                hours_data = {
                    'dates_of_operation': '',
                    'breakfast_hours': '',
                    'lunch_hours': '',
                    'dinner_hours': ''
                }
                
                try:
                    hours_container = elem.find_element(By.XPATH, "ancestor::div[contains(@class, 'location')]//ul[contains(@class, 'menu-hours')]")
                    
                    try:
                        dates_elem = hours_container.find_element(By.XPATH, ".//li[contains(.,'Dates of Operation')]")
                        dates = dates_elem.find_element(By.CSS_SELECTOR, "span.time").text.strip()
                        hours_data['dates_of_operation'] = dates
                    except:
                        pass
                    
                    meal_types = ['Breakfast', 'Lunch', 'Dinner']
                    for meal_type in meal_types:
                        try:
                            meal_elem = hours_container.find_element(By.XPATH, f".//li[contains(.,'{meal_type}')]")
                            time_elem = meal_elem.find_element(By.CSS_SELECTOR, "span.time")
                            hours = time_elem.text.strip()
                            hours = hours.split(' ', 1)[0] if 'chevron' in hours else hours
                            hours_data[f'{meal_type.lower()}_hours'] = hours
                        except:
                            pass
                
                except:
                    pass
                
                location_data = {
                    'name': name,
                    'link': link,
                    'address': address,
                    **hours_data
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
        nutrition_header = WebDriverWait(driver, 3).until(
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
        if (item['location_name'] == new_item['location_name'] and
            item['meal_type'] == new_item['meal_type'] and
            item['item_name'] == new_item['item_name'] and
            item['serving_size'] == new_item['serving_size'] and
            item['calories'] == new_item['calories']):
            return True
    return False

def extract_menu_items(driver, location_name, meal_type):
    """
    Extract menu items from the page for a specific meal type, including nutrition facts.
    Uses batch processing for better performance.
    """
    items = []
    
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
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ns-menu-item-food"))
        )
        
        # Get basic info for all items at once
        basic_items = driver.execute_script(js_collect_items)
        print(f"Found {len(basic_items)} menu items for {location_name} {meal_type}")
        
        if not basic_items:
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
                    'location_name': location_name,
                    'meal_type': meal_type,
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
        
        return items
    
    except Exception as e:
        print(f"Error extracting menu items: {e}")
        return items
def get_menu_for_locations(locations, meal_type):
    """
    Get menu items for each location for a specific meal type.
    
    Args:
    locations (list): List of dining locations
    meal_type (str): Type of meal (breakfast/lunch/dinner)
    
    Returns:
    list: List of all menu items across locations
    """
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    all_menu_items = []
    
    for location in locations:
        try:
            # Skip if this location doesn't serve this meal type
            hours_key = f'{meal_type.lower()}_hours'
            if hours_key in location and not location[hours_key]:
                print(f"Skipping {location['name']} for {meal_type} - no hours listed")
                continue
                
            # Generate menu link for current date and meal type
            menu_link = f"{location['link']}/{meal_type}/{current_date}"
            
            # Navigate to the menu page
            driver.get(menu_link)
            time.sleep(7)  # Wait for page to load
            
            # Extract menu items including nutrition facts
            menu_items = extract_menu_items(driver, location['name'], meal_type)
            
            # Add to all menu items
            all_menu_items.extend(menu_items)
            
            print(f"Added {len(menu_items)} {meal_type} items for {location['name']}")
        
        except Exception as e:
            print(f"Error getting {meal_type} menu for {location['name']}: {e}")
    
    return all_menu_items
# Main function
if __name__ == "__main__":
    try:
        # Get the directory of the current script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Set the CSV file paths
        locations_csv_path = os.path.join(script_dir, "dining_hall_locations.csv")
        breakfast_items_csv_path = os.path.join(script_dir, "dining_hall_breakfast_items.csv")
        lunch_items_csv_path = os.path.join(script_dir, "dining_hall_lunch_items.csv")
        dinner_items_csv_path = os.path.join(script_dir, "dining_hall_dinner_items.csv")
        
        # First, get and save dining locations
        dining_locations = get_dining_locations()
        
        if dining_locations:
            print(f"\nFound {len(dining_locations)} dining locations:")
            
            # Save dining hall locations
            df = pd.DataFrame(dining_locations)
            df.to_csv(locations_csv_path, index=False, quoting=csv.QUOTE_ALL)
            print(f"Dining hall locations saved to {locations_csv_path}")
            
            # Get and save breakfast items with full nutrition data
            breakfast_items = get_menu_for_locations(dining_locations, 'breakfast')
            breakfast_df = pd.DataFrame(breakfast_items)
            breakfast_df.to_csv(breakfast_items_csv_path, index=False, quoting=csv.QUOTE_ALL)
            print(f"Breakfast items saved to {breakfast_items_csv_path}")
            
            # Get and save lunch items with full nutrition data
            lunch_items = get_menu_for_locations(dining_locations, 'lunch')
            lunch_df = pd.DataFrame(lunch_items)
            lunch_df.to_csv(lunch_items_csv_path, index=False, quoting=csv.QUOTE_ALL)
            print(f"Lunch items saved to {lunch_items_csv_path}")
            
            # Get and save dinner items with full nutrition data
            dinner_items = get_menu_for_locations(dining_locations, 'dinner')
            dinner_df = pd.DataFrame(dinner_items)
            dinner_df.to_csv(dinner_items_csv_path, index=False, quoting=csv.QUOTE_ALL)
            print(f"Dinner items saved to {dinner_items_csv_path}")
        else:
            print("No dining locations found!")
    
    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        driver.quit()