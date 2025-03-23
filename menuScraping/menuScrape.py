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
options.add_argument('--headless')  # Run in headless mode
options.add_argument('--disable-gpu')
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
                    button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                else:
                    button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                button.click()
                print(f"Clicked 'View Menus' using selector: {selector}")
                break
            except:
                continue
                
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
        
        return locations
    
    except Exception as e:
        print(f"Error in get_dining_locations: {e}")
        
        # Fallback to hardcoded locations if scraping fails
        return [
            {
                "name": "Gordon Avenue Market",
                "link": "https://wisc-housingdining.nutrislice.com/menu/gordon-avenue-market",
                "address": "770 W. Dayton St., Madison, WI 53706",
                "dates_of_operation": "Jan 12 - May 9",
                "breakfast_hours": "7AM - 11AM",
                "lunch_hours": "11AM - 2PM",
                "dinner_hours": "4PM - 8PM"
            },
            {
                "name": "Four Lakes Market",
                "link": "https://wisc-housingdining.nutrislice.com/menu/four-lakes-market",
                "address": "640 Elm Dr, Madison, WI, USA",
                "dates_of_operation": "Jan 12 - May 9",
                "breakfast_hours": "9AM - 11AM",
                "lunch_hours": "11AM - 2PM",
                "dinner_hours": "4PM - 8PM"
            }
        ]

# Main function
if __name__ == "__main__":
    try:
        dining_locations = get_dining_locations()
        
        if dining_locations:
            print(f"\nFound {len(dining_locations)} dining locations:")
            for i, location in enumerate(dining_locations, 1):
                print(f"{i}. {location['name']} - {location['address']}")
                print(f"   Operating: {location['dates_of_operation']}")
                print(f"   Hours: Breakfast: {location['breakfast_hours']}, Lunch: {location['lunch_hours']}, Dinner: {location['dinner_hours']}")
            
            df = pd.DataFrame(dining_locations)
            df.to_csv("dining_hall_locations.csv", index=False, quoting=csv.QUOTE_ALL)
            print("Data saved to dining_hall_locations.csv")
        else:
            print("No dining locations found!")
    
    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        driver.quit()