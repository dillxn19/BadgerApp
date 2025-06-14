"""Menu item extraction and nutrition data scraping."""

import time
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config import MAX_RETRIES, MEAL_TYPES
from utils import is_duplicate_item

class MenuScraper:
    def __init__(self, driver):
        self.driver = driver
    
    def get_menu_for_location(self, location):
        """Get menu items for a specific location for all meal types."""
        current_date = datetime.now().strftime('%Y-%m-%d')
        updated_location = location.copy()
        
        for meal_type in MEAL_TYPES:
            try:
                # Skip if location doesn't serve this meal type
                if meal_type not in location.get('hours', {}):
                    print(f"Skipping {location['location_name']} for {meal_type} - no hours listed")
                    continue
                    
                # Skip if location is closed for this meal type
                hours_value = location['hours'].get(meal_type, "")
                if not hours_value or hours_value.lower() == "closed":
                    print(f"Skipping {location['location_name']} for {meal_type} - listed as closed")
                    updated_location[meal_type] = []
                    continue
                    
                # Generate menu link for current date and meal type
                menu_link = f"{location['link']}/{meal_type}/{current_date}"
                print(f"Loading menu for {location['location_name']} - {meal_type}")
                
                # Load the menu page with retries
                if self._load_menu_page_with_retries(menu_link):
                    # Extract menu items with retries
                    menu_items = self._extract_menu_items(meal_type)
                    updated_location[meal_type] = menu_items
                    print(f"Added {len(menu_items)} {meal_type} items for {location['location_name']}")
                else:
                    print(f"Could not load menu for {location['location_name']} - {meal_type}")
                    updated_location[meal_type] = []
            
            except Exception as e:
                print(f"Error getting {meal_type} menu for {location['location_name']}: {e}")
                updated_location[meal_type] = []
        
        return updated_location
    
    def _load_menu_page_with_retries(self, menu_link):
        """Load a menu page with retry logic."""
        retry_count = 0
        
        while retry_count <= MAX_RETRIES:
            try:
                self.driver.get(menu_link)
                
                # Wait for the page to load with progressively longer wait times
                wait_time = 7 + (retry_count * 2)
                print(f"Waiting {wait_time} seconds for page to load...")
                time.sleep(wait_time)
                
                # Check if menu items are present using JavaScript
                has_items = self.driver.execute_script("""
                    return document.querySelectorAll('ns-menu-item-food').length > 0;
                """)
                
                if has_items:
                    print("Menu page loaded successfully")
                    return True
                else:
                    print("Menu page loaded but no items found")
                    retry_count += 1
                    if retry_count <= MAX_RETRIES:
                        print(f"Retrying... (Attempt {retry_count} of {MAX_RETRIES})")
                        self.driver.refresh()
                    else:
                        print(f"Failed to load menu items after {MAX_RETRIES} attempts")
                        return False
            
            except Exception as e:
                retry_count += 1
                if retry_count <= MAX_RETRIES:
                    print(f"Error loading menu page: {e}")
                    print(f"Retrying... (Attempt {retry_count} of {MAX_RETRIES})")
                else:
                    print(f"Failed to load menu page after {MAX_RETRIES} attempts: {e}")
                    return False
        
        return False
    
    def _extract_menu_items(self, meal_type):
        """Extract menu items from the page for a specific meal type."""
        items = []
        retry_count = 0
        
        while retry_count <= MAX_RETRIES:
            try:
                # Wait for menu items to appear
                WebDriverWait(self.driver, 12).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ns-menu-item-food"))
                )
                
                # Get basic info for all items at once using JavaScript
                basic_items = self.driver.execute_script(self._get_js_collect_items_script())
                print(f"Found {len(basic_items)} menu items for {meal_type}")
                
                if not basic_items:
                    print(f"Menu appears to be empty for {meal_type}")
                    return items
                
                # Process each item
                for item_data in basic_items:
                    try:
                        item_dict = self._process_menu_item(item_data, basic_items)
                        if item_dict and not is_duplicate_item(items, item_dict):
                            items.append(item_dict)
                            print(f"Added {item_dict['item_name']}")
                        elif item_dict:
                            print(f"Skipping duplicate item: {item_dict['item_name']}")
                    except Exception as e:
                        print(f"Error processing menu item {item_data['index']+1}: {e}")
                        continue
                
                return items
            
            except Exception as e:
                retry_count += 1
                if retry_count <= MAX_RETRIES:
                    print(f"Error extracting menu items: {e}")
                    print(f"Retrying... (Attempt {retry_count} of {MAX_RETRIES})")
                    self.driver.refresh()
                    time.sleep(7 + (retry_count * 3))
                else:
                    print(f"Failed to extract menu items after {MAX_RETRIES} attempts: {e}")
                    return items
        
        return items
    
    def _get_js_collect_items_script(self):
        """JavaScript code to collect basic menu item information."""
        return """
        function collectMenuItems() {
            const items = [];
            const menuElements = document.querySelectorAll('ns-menu-item-food');
            
            menuElements.forEach((item, index) => {
                const nameElem = item.querySelector('span.food-name');
                const name = nameElem ? nameElem.textContent.trim() : 'Unknown';
                
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
    
    def _process_menu_item(self, item_data, basic_items):
        """Process a single menu item and extract nutrition data."""
        name = item_data['name']
        traits = item_data['traits']
        index = item_data['index']
        
        item_dict = {
            'item_name': name,
            'dietary_traits': traits
        }
        
        print(f"Processing item {index+1}/{len(basic_items)}: {name}")
        
        # Get fresh reference to the menu item element
        menu_items = self.driver.find_elements(By.CSS_SELECTOR, "ns-menu-item-food")
        if index >= len(menu_items):
            print(f"Item index {index} no longer exists, skipping")
            return None
        
        item_element = menu_items[index]
        
        # Scroll item into view
        self.driver.execute_script("""
            arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});
        """, item_element)
        
        # Get nutrition facts
        nutrition_data = self._extract_nutrition_facts(item_element)
        item_dict.update(nutrition_data)
        
        return item_dict
    
    def _extract_nutrition_facts(self, item_element):
        """Extract nutrition facts from menu item popup."""
        nutrition_data = {
            'serving_size': 'N/A', 'calories': 'N/A', 'total_fat': 'N/A',
            'saturated_fat': 'N/A', 'trans_fat': 'N/A', 'cholesterol': 'N/A',
            'sodium': 'N/A', 'total_carbohydrate': 'N/A', 'dietary_fiber': 'N/A',
            'total_sugars': 'N/A', 'protein': 'N/A', 'calcium': 'N/A',
            'iron': 'N/A', 'potassium': 'N/A'
        }
        
        try:
            # Click on the menu item to open the nutrition popup
            item_element.click()
            
            # Wait for nutrition facts to appear
            WebDriverWait(self.driver, 4).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "li.modal.active div.nutrition-facts-header"))
            )
            
            # Extract nutrition data using JavaScript
            js_result = self.driver.execute_script(self._get_nutrition_extraction_script())
            
            # Update nutrition data with non-null values from JS
            for key, value in js_result.items():
                if value and value != 'N/A':
                    nutrition_data[key] = value
            
            # Close the popup
            self.driver.execute_script("""
                const closeButton = document.querySelector('li.modal.active a.modal-carousel.close');
                if (closeButton) closeButton.click();
            """)
            
            return nutrition_data
        
        except Exception:
            # Try to close any open modals
            try:
                self.driver.execute_script("document.querySelector('li.modal.active a.modal-carousel.close').click();")
            except:
                try:
                    webdriver.ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                except:
                    pass
            return nutrition_data
    
    def _get_nutrition_extraction_script(self):
        """JavaScript code to extract nutrition data from popup."""
        return """
        function extractNutritionData() {
            const modal = document.querySelector('li.modal.active');
            if (!modal) return {};
            
            const data = {'serving_size': 'N/A', 'calories': 'N/A'};
            
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
            
            // Nutrition label mapping
            const labelMapping = {
                'total fat': 'total_fat', 'saturated fat': 'saturated_fat',
                'trans fat': 'trans_fat', 'cholesterol': 'cholesterol',
                'sodium': 'sodium', 'total carbohydrate': 'total_carbohydrate',
                'dietary fiber': 'dietary_fiber', 'total sugars': 'total_sugars',
                'protein': 'protein', 'calcium': 'calcium',
                'iron': 'iron', 'potassium': 'potassium'
            };
            
            // Extract all nutrition values
            const nutritionRows = modal.querySelectorAll('div.nutrition-row');
            nutritionRows.forEach(row => {
                const labelDiv = row.querySelector('div.nutrition-label');
                if (!labelDiv) return;
                
                const spans = labelDiv.querySelectorAll('span');
                if (spans.length < 2) return;
                
                const label = spans[0].textContent.trim().toLowerCase();
                const value = spans[1].textContent.trim();
                
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