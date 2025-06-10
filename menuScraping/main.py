"""Main entry point for the dining hall scraper."""

from scraper.driver import setup_driver
from scraper.locationScrape import LocationScraper
from scraper.menu import MenuScraper
from mongoDatabase import MongoDBHandler

def main():
    """Main function to orchestrate the scraping process."""
    driver = None
    db_handler = MongoDBHandler()
    
    try:
        # Set up WebDriver
        driver = setup_driver()
        
        # Initialize scrapers
        location_scraper = LocationScraper(driver)
        menu_scraper = MenuScraper(driver)
        
        # Get dining locations
        dining_locations = location_scraper.get_dining_locations()
        
        if dining_locations:
            print(f"\nFound {len(dining_locations)} dining locations")
            
            # List to store all locations with their menu data
            all_location_data = []
            
            # Process each location
            for location in dining_locations:
                # Get menu items for all meal types
                location_with_menu = menu_scraper.get_menu_for_location(location)
                all_location_data.append(location_with_menu)
            
            # Save all data to MongoDB
            if db_handler.save_dining_data(all_location_data):
                print("All dining hall menus have been saved to MongoDB")
            else:
                print("Failed to save data to MongoDB")
        else:
            print("No dining locations found!")
    
    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        if driver:
            driver.quit()
        db_handler.close()

if __name__ == "__main__":
    main()