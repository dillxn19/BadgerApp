import os
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
import re

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
    # Navigate to the main page
    driver.get(base_url)
    print("Loaded main page")
    
    # Click the "View Menus" button
    try:
        # Try with data-testid first, then fallback to text content
        view_menus_selectors = [
            "button.primary[data-testid='018026bcdb3445168421175d9ae4dd06']",
            "//button[contains(text(), 'View Menus')]",
            "button.primary"
        ]
        
        for selector in view_menus_selectors:
            try:
                if selector.startswith("//"):
                    button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                else:
                    button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
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
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), \"Let's do it\")]"))
            )
            lets_do_it.click()
            print("Clicked 'Let's do it' button")
        except:
            print("'Let's do it' button not found or not needed")
        
        # Wait for content to load after location permissions
        time.sleep(10)
        
        # Find all location containers
        location_elements = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.content-container"))
        )
        
        locations = []
        for elem in location_elements:
            try:
                # Extract name from the label div
                name_elem = elem.find_element(By.CSS_SELECTOR, "div.label")
                name = name_elem.text.strip() if name_elem else "Unknown"
                
                # Extract address from the address div
                address_elem = elem.find_element(By.CSS_SELECTOR, "div.address")
                address = address_elem.text.strip() if address_elem else "Address not found"
                
                # Find the link - look for an ancestor that's an <a> tag
                link = ""
                current = elem
                for _ in range(5):  # Check up to 5 levels up
                    try:
                        parent = current.find_element(By.XPATH, "..")
                        if parent.tag_name == "a":
                            link = parent.get_attribute("href")
                            break
                        current = parent
                    except:
                        break
                
                if not link:
                    link = f"https://wisc-housingdining.nutrislice.com/menu/{name.lower().replace(' ', '-')}"
                
                # Extract hours information directly from the main page
                hours_data = {
                    'dates_of_operation': '',
                    'breakfast_hours': '',
                    'lunch_hours': '',
                    'dinner_hours': ''
                }
                
                try:
                    # Find the hours container for this location
                    hours_container = elem.find_element(By.XPATH, "ancestor::div[contains(@class, 'location')]//ul[contains(@class, 'menu-hours')]")
                    
                    # Extract dates of operation
                    try:
                        dates_elem = hours_container.find_element(By.XPATH, ".//li[contains(.,'Dates of Operation')]")
                        dates = dates_elem.find_element(By.CSS_SELECTOR, "span.time").text.strip()
                        hours_data['dates_of_operation'] = dates
                    except Exception as e:
                        print(f"Could not find dates of operation for {name}: {e}")
                    
                    # Extract meal hours
                    meal_types = ['Breakfast', 'Lunch', 'Dinner']
                    for meal_type in meal_types:
                        try:
                            meal_elem = hours_container.find_element(By.XPATH, f".//li[contains(.,'{meal_type}')]")
                            time_elem = meal_elem.find_element(By.CSS_SELECTOR, "span.time")
                            hours = time_elem.text.strip()
                            # Remove the chevron icon character if present
                            hours = hours.split(' ', 1)[0] if 'chevron' in hours else hours
                            hours_data[f'{meal_type.lower()}_hours'] = hours
                        except Exception as e:
                            print(f"Could not find {meal_type} hours for {name}: {e}")
                
                except Exception as e:
                    print(f"Could not find hours container for {name}: {e}")
                
                # Create location with all info
                location_data = {
                    'name': name,
                    'link': link,
                    'address': address,
                    'dates_of_operation': hours_data['dates_of_operation'],
                    'breakfast_hours': hours_data['breakfast_hours'],
                    'lunch_hours': hours_data['lunch_hours'],
                    'dinner_hours': hours_data['dinner_hours']
                }
                
                if name and name != "Unknown":
                    locations.append(location_data)
                    print(f"Added {name} with hours: {hours_data}")
                
            except Exception as e:
                print(f"Error processing a location element: {e}")
        
        if not locations:
            raise Exception("No locations found")
        
        return locations
    
    except Exception as e:
        print(f"Error in get_dining_locations: {e}")
        raise  # Re-raise the exception to be handled in the main block

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
        
        # Wait for nutrition facts to appear - now looking specifically for the active modal
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "li.modal.active div.nutrition-facts-header"))
        )
        
        # Get the complete HTML of the popup
        nutrition_html = driver.page_source
        soup = BeautifulSoup(nutrition_html, 'html.parser')
        
        # Find the active modal
        active_modal = soup.select_one("li.modal.active")
        if not active_modal:
            print("No active modal found")
            return nutrition_data
        
        # Extract serving size
        serving_size_container = active_modal.select_one("div.serving-size")
        if serving_size_container:
            # Get all divs within the container
            divs = serving_size_container.find_all("div", recursive=False)
            if len(divs) >= 2:
                serving_size = divs[1].get_text(strip=True)
                nutrition_data['serving_size'] = serving_size
        
        # Extract calories
        calories_row = active_modal.select_one("div.calories-row")
        if calories_row:
            calories_div = calories_row.find("div", class_=lambda x: x is None or "bold" not in x)
            if calories_div:
                nutrition_data['calories'] = calories_div.get_text(strip=True)
        
        # Extract nutrition information from all rows
        nutrition_lists = active_modal.find_all("ul", class_="nutrition-facts-values")
        
        for nutrition_list in nutrition_lists:
            list_items = nutrition_list.find_all("li")
            for item in list_items:
                # Find the nutrition-row div
                nutrition_row = item.select_one("div.nutrition-row")
                if not nutrition_row:
                    continue
                
                # Get the nutrition-label div
                label_div = nutrition_row.select_one("div.nutrition-label")
                if not label_div:
                    continue
                
                # Get all spans in the label div
                spans = label_div.find_all("span")
                if len(spans) < 2:
                    continue
                
                # First span is the label, second is the value
                label = spans[0].get_text(strip=True).lower()
                value = spans[1].get_text(strip=True)
                
                # Map to the correct field in our dictionary
                if "total fat" in label:
                    nutrition_data['total_fat'] = value
                elif "saturated fat" in label:
                    nutrition_data['saturated_fat'] = value
                elif "trans fat" in label:
                    nutrition_data['trans_fat'] = value
                elif "cholesterol" in label:
                    nutrition_data['cholesterol'] = value
                elif "sodium" in label:
                    nutrition_data['sodium'] = value
                elif "total carbohydrate" in label:
                    nutrition_data['total_carbohydrate'] = value
                elif "dietary fiber" in label:
                    nutrition_data['dietary_fiber'] = value
                elif "total sugars" in label:
                    nutrition_data['total_sugars'] = value
                elif "protein" in label:
                    nutrition_data['protein'] = value
                elif "calcium" in label:
                    nutrition_data['calcium'] = value
                elif "iron" in label:
                    nutrition_data['iron'] = value
                elif "potassium" in label:
                    nutrition_data['potassium'] = value
        
        # Close the popup
        try:
            # Try to find the close button within the active modal
            close_button = driver.find_element(By.CSS_SELECTOR, "li.modal.active a.modal-carousel.close")
            close_button.click()
            print("Closed nutrition modal with modal-carousel.close")
        except:
            try:
                # Try pressing Escape key if close button not found
                from selenium.webdriver.common.keys import Keys
                webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                print("Closed nutrition modal with Escape key")
            except:
                print("Failed to close nutrition modal, continuing anyway")
        
        # Wait for modal to close
        time.sleep(1)
        
        return nutrition_data
    
    except Exception as e:
        print(f"Error extracting nutrition facts: {e}")
        # Try to close any open modals
        try:
            driver.execute_script("document.querySelector('li.modal.active a.modal-carousel.close').click();")
        except:
            pass
        return nutrition_data
def extract_menu_items(driver, location_name, meal_type):
    """
    Extract menu items from the page for a specific meal type, including nutrition facts.
    """
    items = []
    
    try:
        # Find all menu items on the page
        menu_items = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ns-menu-item-food"))
        )
        
        print(f"Found {len(menu_items)} menu items for {location_name} {meal_type}")
        
        for i in range(len(menu_items)):
            try:
                # Get fresh reference to avoid stale elements
                current_items = driver.find_elements(By.CSS_SELECTOR, "ns-menu-item-food")
                if i >= len(current_items):
                    continue
                    
                item_element = current_items[i]
                
                # Scroll item into view
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", item_element)
                time.sleep(0.5)
                
                # Extract basic info
                name_elem = item_element.find_element(By.CSS_SELECTOR, "span.food-name")
                name = name_elem.text.strip() if name_elem else "Unknown"
                
                traits = []
                trait_elems = item_element.find_elements(By.CSS_SELECTOR, "div.custom-icon")
                for trait in trait_elems:
                    style = trait.get_attribute("style")
                    trait_match = re.search(r'Food_Trait_Icons_([^-]+)', style)
                    if trait_match:
                        traits.append(trait_match.group(1))
                
                item_dict = {
                    'location_name': location_name,
                    'meal_type': meal_type,
                    'item_name': name,
                    'dietary_traits': ', '.join(traits) if traits else ''
                }
                
                print(f"Processing item {i+1}/{len(menu_items)}: {name}")
                
                # Get nutrition facts
                nutrition_data = extract_nutrition_facts(driver, item_element)
                item_dict.update(nutrition_data)
                
                items.append(item_dict)
                print(f"Successfully added {name} with nutrition data")
                
                # Wait before processing next item
                time.sleep(1)
                
            except Exception as e:
                print(f"Error processing menu item {i+1}: {e}")
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
            # Generate menu link for current date and meal type
            menu_link = f"{location['link']}/{meal_type}/{current_date}"
            
            # Navigate to the menu page
            driver.get(menu_link)
            time.sleep(5)  # Wait for page to load
            
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