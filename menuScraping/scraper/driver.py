"""WebDriver setup and configuration."""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from config import CHROME_OPTIONS, CHROME_PREFS

def setup_driver():
    """Set up ChromeDriver with predefined options."""
    options = webdriver.ChromeOptions()
    
    # Add all chrome options
    for option in CHROME_OPTIONS:
        options.add_argument(option)
    
    # Add experimental options
    options.add_experimental_option("prefs", CHROME_PREFS)
    
    # Initialize and return driver
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), 
        options=options
    )
    return driver
