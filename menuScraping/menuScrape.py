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
    "profile.default_content_setting_values.geolocation": 1,  # 1 = allow, 2 = block
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

# Function to extract dining hall locations
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
        
        # Try to find location links in the page
        location_links = []
        
        # Method 1: Look for links with menu in URL
        for link in soup.find_all('a', href=True):
            href = link['href']
            if 'menu' in href.lower() and not href.endswith('#'):
                text = link.get_text().strip()
                if text and len(text) < 50:  # Reasonable name length
                    location_links.append({
                        'name': text,
                        'link': href if href.startswith('http') else base_url + href.lstrip('/')
                    })
        
        # Method 2: Look for elements with location-related classes
        for element in soup.select('[class*="location"], [class*="school"]'):
            link = element.find('a', href=True)
            if link:
                name = link.get_text().strip()
                href = link['href']
                if name and 'menu' in href.lower():
                    location_links.append({
                        'name': name,
                        'link': href if href.startswith('http') else base_url + href.lstrip('/')
                    })
        
        # Add unique locations to our list
        seen_names = set()
        for loc in location_links:
            if loc['name'] not in seen_names:
                locations.append(loc)
                seen_names.add(loc['name'])
        
        print(f"Found {len(locations)} unique locations using BeautifulSoup")
        
        # If we didn't find any locations with BeautifulSoup, try with Selenium directly
        if not locations:
            print("Trying to find locations using Selenium...")
            
            # Try various selectors that might contain dining locations
            selectors = [
                'a[href*="menu"]',
                '.location-list a',
                '.location-item',
                '.dining-location',
                'li a',  # General list items with links
                'ul a'   # Links in unordered lists
            ]
            
            for selector in selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                print(f"Found {len(elements)} elements with selector: {selector}")
                
                if elements:
                    for element in elements:
                        try:
                            name = element.text.strip()
                            link = element.get_attribute('href')
                            
                            # Only consider non-empty names and links that look like menu links
                            if name and link and 'menu' in link.lower():
                                if name not in seen_names:
                                    locations.append({
                                        'name': name,
                                        'link': link
                                    })
                                    seen_names.add(name)
                        except Exception as e:
                            print(f"Error processing element: {e}")
                    
                    # If we found locations with this selector, we can stop trying others
                    if len(locations) > len(seen_names) - 1:
                        break
        
    except Exception as e:
        print(f"Error finding dining locations: {e}")
    
    # If we still couldn't find locations automatically, add some hardcoded ones from the site
    if not locations:
        print("No locations found automatically. Adding known dining locations...")
        known_locations = [
            {"name": "Gordon Avenue Market", "link": "https://wisc-housingdining.nutrislice.com/menu/gordon-avenue-market"},
            {"name": "Four Lakes Market", "link": "https://wisc-housingdining.nutrislice.com/menu/four-lakes-market"},
            {"name": "Rheta's Market", "link": "https://wisc-housingdining.nutrislice.com/menu/rhetas-market"},
            {"name": "Carson's Market", "link": "https://wisc-housingdining.nutrislice.com/menu/carsons-market"},
            {"name": "Liz's Market", "link": "https://wisc-housingdining.nutrislice.com/menu/lizs-market"},
            {"name": "Lowell Market", "link": "https://wisc-housingdining.nutrislice.com/menu/lowell-market"}
        ]
        locations.extend(known_locations)
    
    return locations

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
                print(f"{i}. {location['name']} - {location['link']}")
            
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