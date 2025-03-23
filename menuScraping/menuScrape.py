from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import csv

# Set up ChromeDriver with optimized options
options = webdriver.ChromeOptions()
options.add_argument('--disable-gpu')
options.add_argument('--disable-extensions')
options.add_argument('--disable-infobars')
options.add_argument('--start-maximized')
options.add_argument('--disable-dev-shm-usage')
# Add geolocation preferences to automatically allow location access
options.add_experimental_option("prefs", {
    "profile.default_content_setting_values.geolocation": 1  # 1 = allow, 2 = block
})
# If needed, you can set a specific geolocation
options.add_argument("--use-fake-ui-for-media-stream")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Base URL for the dining hall website
base_url = "https://wisc-housingdining.nutrislice.com/"

# Function to click the "View Menus" button and wait for navigation
def click_view_menus_button():
    try:
        # Wait for the "View Menus" button to be clickable
        view_menus_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.primary[data-testid='018026bcdb3445168421175d9ae4dd06']"))
        )
        view_menus_button.click()
        print("Successfully clicked 'View Menus' button")
        time.sleep(3)  # Wait for navigation
        return True
    except Exception as e:
        # If we can't find the button by data-testid, try other approaches
        try:
            # Try finding by button text
            view_menus_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'View Menus')]"))
            )
            view_menus_button.click()
            print("Successfully clicked 'View Menus' button (by text)")
            time.sleep(3)
            return True
        except Exception as e2:
            print(f"Error clicking 'View Menus' button: {e2}")
            return False

# Function to click the "Let's do it" button
def click_lets_do_it_button():
    try:
        # Wait for the "Let's do it" button to be clickable
        lets_do_it_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), \"Let's do it\")]"))
        )
        lets_do_it_button.click()
        print("Successfully clicked 'Let's do it' button")
        time.sleep(2)  # Wait for location prompt to appear
        return True
    except Exception as e:
        # Try alternative selectors
        try:
            # Try by class name as provided in the HTML
            lets_do_it_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.primary.button-center"))
            )
            lets_do_it_button.click()
            print("Successfully clicked 'Let's do it' button (by class)")
            time.sleep(2)
            return True
        except Exception as e2:
            print(f"Error clicking 'Let's do it' button: {e2}")
            return False

# Function to handle location permission dialog if it appears
def handle_location_prompt():
    try:
        # First try browser's native dialog (this could vary by browser/OS)
        driver.switch_to.alert.accept()
        print("Accepted browser location alert")
        time.sleep(2)
    except:
        print("No browser alert found or couldn't interact with it. Trying webpage dialog...")
    
    try:
        # Check if there's a location permission dialog and click "Allow" if present
        allow_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Allow')]"))
        )
        allow_button.click()
        print("Clicked 'Allow' on location permission dialog")
        time.sleep(2)
        return True
    except Exception as e:
        print("No location dialog found or couldn't interact with it. Continuing...")
        return False

# Function to extract dining hall locations with addresses
def get_dining_locations():
    # Navigate to the main page
    driver.get(base_url)
    print("Loaded main page")
    time.sleep(2)  # Wait for page to load
    
    # Click the "View Menus" button to access the menu page
    if not click_view_menus_button():
        print("Failed to click 'View Menus' button. Trying to continue anyway.")
    
    # Click "Let's do it" button that appears before location prompt
    if not click_lets_do_it_button():
        print("Failed to click 'Let's do it' button. Trying to continue anyway.")
    
    # Handle location permission dialog if it appears
    handle_location_prompt()
    
    # Wait for locations to load after handling location permissions
    time.sleep(5)
    
    # Print the current URL
    print(f"Current URL: {driver.current_url}")
    
    locations = []
    
    # Save the page source to a file for inspection
    with open("page_source.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print("Page source saved to page_source.html")
    
    # Try multiple approaches to find dining locations
    try:
        # Parse with BeautifulSoup for more flexible extraction
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Approach 1: Look for common location list patterns
        print("Trying to find locations...")
        
        # Print some page structure to debug console
        print("\nDEBUG INFO:")
        print("First 10 links:")
        for link in soup.find_all('a', href=True)[:10]:
            print(f"Link: {link.get_text().strip()} -> {link['href']}")
        
        print("\nFirst 10 list items:")
        for item in soup.find_all('li')[:10]:
            print(f"List item: {item.get_text().strip()}")
        
        # Look for location cards/sections that contain both links and addresses
        location_sections = soup.find_all('div', class_='location-card') or \
                            soup.find_all('div', class_='location-item') or \
                            soup.find_all('div', class_='school-card') or \
                            soup.find_all('li')  # Fallback to list items
        
        for section in location_sections:
            link_elem = section.find('a', href=True)
            address_elem = section.find('div', class_='address')
            
            if link_elem and 'menu' in link_elem.get('href', '').lower():
                location_data = {
                    'name': link_elem.get_text().strip(),
                    'link': link_elem['href'] if link_elem['href'].startswith('http') else base_url + link_elem['href'].lstrip('/'),
                    'address': address_elem.get_text().strip() if address_elem else "Address not found"
                }
                locations.append(location_data)
        
        # If we didn't find enough locations with the section approach, try direct element matching
        if len(locations) < 3:
            print("Trying alternative method to find locations...")
            # Get all location links
            location_links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'menu' in href.lower() and not href.endswith('#'):
                    text = link.get_text().strip()
                    if text and len(text) < 50:  # Reasonable name length
                        location_links.append({
                            'name': text,
                            'link': href if href.startswith('http') else base_url + href.lstrip('/'),
                            'element': link
                        })
            
            # For each link, try to find closest address div
            for loc in location_links:
                # Look for address in parent or nearby elements
                parent = loc['element'].parent
                address_elem = None
                
                # Try looking in parent element
                address_elem = parent.find('div', class_='address')
                
                # If not found, try looking in siblings or parent's siblings
                if not address_elem:
                    # Try parent's siblings
                    for sibling in parent.find_next_siblings():
                        address_elem = sibling.find('div', class_='address')
                        if address_elem:
                            break
                    
                    # Try parent's parent's children
                    if not address_elem and parent.parent:
                        address_elem = parent.parent.find('div', class_='address')
                
                # Add location with address if found
                locations.append({
                    'name': loc['name'],
                    'link': loc['link'],
                    'address': address_elem.get_text().strip() if address_elem else "Address not found"
                })
        
        print(f"Found {len(locations)} locations with potential addresses")
        
        # If still not finding addresses, try using Selenium's finding methods directly
        if all(loc['address'] == "Address not found" for loc in locations):
            print("Using Selenium to find addresses...")
            
            # Visit each location page to get the address
            for i, loc in enumerate(locations):
                try:
                    print(f"Visiting {loc['name']} page to get address...")
                    driver.get(loc['link'])
                    time.sleep(3)  # Wait for page to load
                    
                    # Try to find address on the location page
                    try:
                        address_elem = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "div.address"))
                        )
                        locations[i]['address'] = address_elem.text.strip()
                        print(f"Found address: {locations[i]['address']}")
                    except:
                        print(f"Could not find address for {loc['name']} on its page")
                except Exception as e:
                    print(f"Error visiting {loc['name']} page: {e}")
        
    except Exception as e:
        print(f"Error finding dining locations: {e}")
    
    # If we still couldn't find locations automatically, add some hardcoded ones from the site
    if not locations:
        print("No locations found automatically. Adding known dining locations...")
        known_locations = [
            {"name": "Gordon Avenue Market", "link": "https://wisc-housingdining.nutrislice.com/menu/gordon-avenue-market", "address": "770 W. Dayton St., Madison, WI 53706"},
            {"name": "Four Lakes Market", "link": "https://wisc-housingdining.nutrislice.com/menu/four-lakes-market", "address": "640 Elm Dr, Madison, WI, USA"},
            {"name": "Rheta's Market", "link": "https://wisc-housingdining.nutrislice.com/menu/rhetas-market", "address": "420 N. Park St., Madison, WI 53706"},
            {"name": "Carson's Market", "link": "https://wisc-housingdining.nutrislice.com/menu/carsons-market", "address": "1515 Tripp Circle, Madison, WI 53706"},
            {"name": "Liz's Market", "link": "https://wisc-housingdining.nutrislice.com/menu/lizs-market", "address": "1200 Observatory Dr., Madison, WI 53706"},
            {"name": "Lowell Market", "link": "https://wisc-housingdining.nutrislice.com/menu/lowell-market", "address": "610 Langdon St., Madison, WI 53703"}
        ]
        locations.extend(known_locations)
    
    # Create a list of unique locations (remove duplicates by name)
    unique_locations = []
    seen_names = set()
    for loc in locations:
        if loc['name'] not in seen_names:
            unique_locations.append(loc)
            seen_names.add(loc['name'])
    
    return unique_locations

# Main function
if __name__ == "__main__":
    try:
        print("Starting UW-Madison dining hall scraper...")
        
        # Get dining hall locations
        dining_locations = get_dining_locations()
        
        # Create a DataFrame and save to CSV
        if dining_locations:
            print(f"\nFound {len(dining_locations)} dining locations:")
            for i, location in enumerate(dining_locations, 1):
                print(f"{i}. {location['name']} - Address: {location['address']} - {location['link']}")
            
            df = pd.DataFrame(dining_locations)
            output_file = "dining_hall_locations.csv"
            df.to_csv(output_file, index=False, quoting=csv.QUOTE_ALL)
            print(f"\nData saved to {output_file}")
        else:
            print("No dining locations found!")
    
    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        # Close the browser
        driver.quit()
        print("Browser closed.")