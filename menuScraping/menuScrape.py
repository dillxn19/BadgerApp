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

def extract_breakfast_items(html_content):
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
            'name': name,
            'calories': calories,
            'dietary_traits': traits
        }
        
        items.append(item_dict)
    
    return items

def get_dining_locations_with_breakfast_menu():
    # Get current date in YYYY-MM-DD format
    current_date = datetime.now().strftime('%Y-%m-%d')
    
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
                
                # Find the link to the specific location's menu
                try:
                    location_link_elem = elem.find_element(By.XPATH, "ancestor::a")
                    location_menu_url = location_link_elem.get_attribute("href")
                except:
                    # Fallback link generation if direct link not found
                    location_menu_url = f"https://wisc-housingdining.nutrislice.com/menu/{name.lower().replace(' ', '-')}"
                
                # Generate breakfast link for current date
                breakfast_link = f"{location_menu_url}/breakfast/{current_date}"
                
                # Navigate to the breakfast menu page
                driver.get(breakfast_link)
                time.sleep(3)  # Wait for page to load
                
                # Get the page source
                page_source = driver.page_source
                
                # Extract breakfast items
                breakfast_items = extract_breakfast_items(page_source)
                
                # Create location with all info
                location_data = {
                    'name': name,
                    'menu_url': location_menu_url,
                    'breakfast_link': breakfast_link,
                    'breakfast_items': breakfast_items
                }
                
                if name and name != "Unknown":
                    locations.append(location_data)
                    print(f"Added {name} - Breakfast Items: {len(breakfast_items)}")
                
            except Exception as e:
                print(f"Error processing {name}: {e}")
        
        return locations
    
    except Exception as e:
        print(f"Error in get_dining_locations: {e}")
        raise  # Re-raise the exception to be handled in the main block

# Main function
if __name__ == "__main__":
    try:
        # Get the directory of the current script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Set the CSV file paths
        locations_csv_path = os.path.join(script_dir, "dining_hall_breakfast_locations.csv")
        items_csv_path = os.path.join(script_dir, "dining_hall_breakfast_items.csv")
        
        dining_locations = get_dining_locations_with_breakfast_menu()
        
        if dining_locations:
            print(f"\nFound {len(dining_locations)} dining locations:")
            
            # Prepare location data for CSV
            location_data = []
            all_items_data = []
            
            for location in dining_locations:
                # Location data
                location_data.append({
                    'name': location['name'],
                    'menu_url': location['menu_url'],
                    'breakfast_link': location['breakfast_link']
                })
                
                # Breakfast items data
                for item in location['breakfast_items']:
                    item_entry = {
                        'location_name': location['name'],
                        'item_name': item['name'],
                        'calories': item['calories'],
                        'dietary_traits': ', '.join(item['dietary_traits'])
                    }
                    all_items_data.append(item_entry)
                
                # Print items for each location
                print(f"\n{location['name']} Breakfast Items:")
                for item in location['breakfast_items']:
                    print(f"  - {item['name']} ({item['calories']} Cal)")
                    print(f"    Traits: {', '.join(item['dietary_traits'])}")
            
            # Save to CSVs
            locations_df = pd.DataFrame(location_data)
            locations_df.to_csv(locations_csv_path, index=False, quoting=csv.QUOTE_ALL)
            print(f"\nLocation data saved to {locations_csv_path}")
            
            items_df = pd.DataFrame(all_items_data)
            items_df.to_csv(items_csv_path, index=False, quoting=csv.QUOTE_ALL)
            print(f"Breakfast items data saved to {items_csv_path}")
        else:
            print("No dining locations found!")
    
    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        driver.quit()