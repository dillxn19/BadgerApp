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
        time.sleep(5)
        
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

def extract_breakfast_items(html_content, location_name):
    """
    Extract breakfast menu items from the HTML content.
    
    Returns:
    list of dict: List of breakfast items with details
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    items = []
    
    # Find all menu items
    menu_items = soup.find_all('ns-menu-item-food')
    
    for item in menu_items:
        # Extract food name
        name_elem = item.find('span', class_='food-name')
        name = name_elem.get_text(strip=True) if name_elem else "Unknown"
        
        # Extract calories
        calories_elem = item.find('li', class_='food-calories')
        calories = calories_elem.get_text(strip=True).split()[0] if calories_elem else "N/A"
        
        # Extract dietary icons/traits
        traits = []
        trait_elems = item.find_all('div', class_='custom-icon')
        for trait in trait_elems:
            # Extract trait name from background image URL
            style = trait.get('style', '')
            trait_match = re.search(r'Food_Trait_Icons_([^-]+)', style)
            if trait_match:
                traits.append(trait_match.group(1))
        
        # Create item dictionary
        item_dict = {
            'location_name': location_name,
            'item_name': name,
            'calories': calories,
            'dietary_traits': ', '.join(traits)
        }
        
        items.append(item_dict)
    
    return items

def get_breakfast_menu_for_locations(locations):
    """
    Get breakfast menu items for each location.
    
    Returns:
    list: List of all breakfast items across locations
    """
    # Get current date in YYYY-MM-DD format
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    all_breakfast_items = []
    
    for location in locations:
        try:
            # Generate breakfast link for current date
            breakfast_link = f"{location['link']}/breakfast/{current_date}"
            
            # Navigate to the breakfast menu page
            driver.get(breakfast_link)
            time.sleep(5)  # Wait for page to load
            
            # Get the page source
            page_source = driver.page_source
            
            # Extract breakfast items
            breakfast_items = extract_breakfast_items(page_source, location['name'])
            
            # Add to all breakfast items
            all_breakfast_items.extend(breakfast_items)
            
            print(f"Added {len(breakfast_items)} breakfast items for {location['name']}")
        
        except Exception as e:
            print(f"Error getting breakfast menu for {location['name']}: {e}")
    
    return all_breakfast_items

# Main function
if __name__ == "__main__":
    try:
        # Get the directory of the current script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Set the CSV file paths
        locations_csv_path = os.path.join(script_dir, "dining_hall_locations.csv")
        breakfast_items_csv_path = os.path.join(script_dir, "dining_hall_breakfast_items.csv")
        
        # First, get and save dining locations
        dining_locations = get_dining_locations()
        
        if dining_locations:
            print(f"\nFound {len(dining_locations)} dining locations:")
            
            # Save dining hall locations
            df = pd.DataFrame(dining_locations)
            df.to_csv(locations_csv_path, index=False, quoting=csv.QUOTE_ALL)
            print(f"Dining hall locations saved to {locations_csv_path}")
            
            # Then get breakfast menus
            all_breakfast_items = get_breakfast_menu_for_locations(dining_locations)
            
            # Save all breakfast items to a single CSV
            items_df = pd.DataFrame(all_breakfast_items)
            items_df.to_csv(breakfast_items_csv_path, index=False, quoting=csv.QUOTE_ALL)
            print(f"All breakfast items saved to {breakfast_items_csv_path}")
        else:
            print("No dining locations found!")
    
    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        driver.quit()