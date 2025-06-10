"""Location discovery and basic info extraction."""

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config import BASE_URL
from utils import clean_for_url

class LocationScraper:
    def __init__(self, driver):
        self.driver = driver
    
    def get_dining_locations(self):
        """Get all dining locations with cleaned URLs."""
        self.driver.get(BASE_URL)
        print("Loaded main page")
        
        try:
            self._click_view_menus_button()
            self._handle_lets_do_it_button()
            
            # Wait for content to load
            time.sleep(8)
            
            # Find all location containers
            location_elements = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.content-container")))
            
            locations = []
            for elem in location_elements:
                location_data = self._extract_location_data(elem)
                if location_data and location_data['location_name'] != "Unknown":
                    locations.append(location_data)
                    print(f"Added {location_data['location_name']} with URL: {location_data['link']}")
            
            if not locations:
                raise Exception("No locations found")
            
            return locations
        
        except Exception as e:
            print(f"Error in get_dining_locations: {e}")
            raise
    
    def _click_view_menus_button(self):
        """Try multiple selectors for View Menus button."""
        view_menus_selectors = [
            "button.primary[data-testid='018026bcdb3445168421175d9ae4dd06']",
            "//button[contains(text(), 'View Menus')]",
            "button.primary"
        ]
        
        for selector in view_menus_selectors:
            try:
                if selector.startswith("//"):
                    button = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, selector)))
                else:
                    button = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                button.click()
                print(f"Clicked 'View Menus' using selector: {selector}")
                return
            except Exception as click_error:
                print(f"Failed to click with selector {selector}: {click_error}")
                continue
        
        raise Exception("Could not find 'View Menus' button")
    
    def _handle_lets_do_it_button(self):
        """Handle optional 'Let's do it' button."""
        try:
            lets_do_it = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), \"Let's do it\")]")))
            lets_do_it.click()
            print("Clicked 'Let's do it' button")
        except:
            print("'Let's do it' button not found or not needed")
    
    def _extract_location_data(self, elem):
        """Extract location data from a location element."""
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
            
            return {
                'location_name': name,
                'date_of_operation': date_of_operation,
                'location': address,
                'link': link,
                'hours': hours_data,
                'breakfast': [],
                'lunch': [],
                'dinner': []
            }
            
        except Exception as e:
            print(f"Error processing a location element: {e}")
            return None
