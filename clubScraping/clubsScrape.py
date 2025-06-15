from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from clubs_mongodb import MongoDBHandler

import pandas as pd
import time
import re
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Set up ChromeDriver with optimized headless options
def create_driver():
    chrome_options = Options()
    # Enhanced headless configuration
    chrome_options.add_argument('--headless=new')  # Use new headless mode
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-web-security')
    chrome_options.add_argument('--disable-features=VizDisplayCompositor')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-logging')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-plugins')
    chrome_options.add_argument('--disable-background-timer-throttling')
    chrome_options.add_argument('--disable-backgrounding-occluded-windows')
    chrome_options.add_argument('--disable-renderer-backgrounding')
    chrome_options.add_argument('--disable-features=TranslateUI')
    chrome_options.add_argument('--disable-ipc-flooding-protection')
    
    # Disable unnecessary resources for maximum speed
    chrome_options.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheet": 2,
        "profile.managed_default_content_settings.javascript": 1,
        "profile.managed_default_content_settings.fonts": 2,
        "profile.managed_default_content_settings.media_stream": 2,
        "profile.managed_default_content_settings.notifications": 2,
        "profile.managed_default_content_settings.geolocation": 2,
        "profile.managed_default_content_settings.popups": 2,
        "profile.default_content_setting_values.automatic_downloads": 2,
    })
    
    # Set page load strategy to 'none' for faster loading
    chrome_options.add_argument('--page-load-strategy=none')
    
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

# Thread-local storage for drivers
thread_local = threading.local()

def get_driver():
    if not hasattr(thread_local, 'driver'):
        thread_local.driver = create_driver()
    return thread_local.driver

# Function to wait for element with timeout (optimized)
def wait_for_element(driver, selector, by=By.CSS_SELECTOR, timeout=3):
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
    except:
        return None

# Function to extract organization names, links and image sources
def extract_names_links_and_images(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    org_list = soup.find('ul', class_='MuiList-root MuiList-padding')
    if not org_list:
        return [], [], []
    
    organizations = org_list.find_all('a')
    data = []
    
    for org in organizations:
        name_div = org.find('div', style=lambda x: x and 'font-size: 1.125rem;' in x)
        name = name_div.text.strip() if name_div else 'No name available'
        link = org.get('href', 'No link available')
        img_tag = org.find('img')
        image_src = img_tag.get('src') if img_tag else 'No image available'
        
        data.append((name, link, image_src))
        
    return zip(*data) if data else ([], [], [])

# Function to extract description, email, website, and Instagram from the organization's page
def extract_details(driver):
    # Get description
    description_elem = wait_for_element(driver, '.bodyText-large.userSupplied')
    description = description_elem.text.strip() if description_elem else 'No description available'

    # Initialize default values
    website = 'No website available'
    instagram = 'No Instagram available'
    email = 'No email available'

    # Get page source once
    html_content = driver.page_source
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract email
    email_span = soup.find('span', class_='sr-only', string='Contact Email')
    if email_span and email_span.parent:
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', email_span.parent.text)
        if email_match:
            email = email_match.group()
    
    # Backup email extraction methods
    if email == 'No email available':
        email_div = soup.find('div', string=lambda text: text and 'E:' in text if text else False)
        if email_div:
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', email_div.text)
            if email_match:
                email = email_match.group()
    
    if email == 'No email available':
        all_email_matches = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', html_content)
        if all_email_matches:
            email = all_email_matches[0]
    
    # Extract social links
    social_links = soup.find_all('a', attrs={'href': True})
    website_candidates = []
    
    for link in social_links:
        href = link['href']
        aria_label = link.get('aria-label', '').lower()
        
        # Check for website candidates
        if ('visit our site' in aria_label or 
            'globe' in str(link) or 
            (href.startswith('http') and 
             not any(social in href for social in ['instagram', 'facebook', 'linkedin', 'youtube', 'twitter', 'calendar.google']))):
            website_candidates.append((href, 'visit our site' in aria_label or 'globe' in str(link)))
        
        # Check for Instagram
        if ('instagram' in aria_label or 'instagram.com' in href) and instagram == 'No Instagram available':
            instagram = href
    
    # Determine the best website candidate
    if website_candidates:
        # Prioritize links with 'visit our site' or globe icon
        for href, is_priority in website_candidates:
            if is_priority:
                website = href
                break
        else:
            website = website_candidates[0][0]

    return description, email, website, instagram

# Process individual organization with error handling
def process_organization(org_data):
    name, link, image_src = org_data
    driver = get_driver()
    
    try:
        # Navigate directly to the organization page
        driver.get(f"https://win.wisc.edu{link}")
        # Stop loading after a short time to speed up
        time.sleep(0.5)
        driver.execute_script("window.stop();")
        
        description, email, website, instagram = extract_details(driver)
        return {
            'Name': name, 
            'Description': description, 
            'Email': email, 
            'Website': website, 
            'Instagram': instagram,
            'Image_Source': image_src
        }
    except Exception as e:
        print(f"Error processing {name}: {e}")
        return {
            'Name': name, 
            'Description': 'Error fetching data', 
            'Email': 'Error', 
            'Website': 'Error', 
            'Instagram': 'Error',
            'Image_Source': image_src
        }

def main():
    # Create main driver for initial page loading
    driver = create_driver()
    
    try:
        # Navigate to the website
        url = "https://win.wisc.edu/organizations"
        driver.get(url)
        
        # Load all organizations by clicking "Load More" with optimized waiting
        last_count = 0
        current_count = 0
        attempts = 0
        max_attempts = 5
        
        while attempts < max_attempts:
            try:
                load_more_button = wait_for_element(driver, "//span[contains(text(), 'Load More')]", By.XPATH, 2)
                if load_more_button:
                    driver.execute_script("arguments[0].click();", load_more_button)
                    time.sleep(0.3)  # Reduced wait time
                    
                    # Check if new content was loaded
                    org_elements = driver.find_elements(By.CSS_SELECTOR, "ul.MuiList-root a")
                    current_count = len(org_elements)
                    
                    if current_count == last_count:
                        attempts += 1
                    else:
                        attempts = 0
                        last_count = current_count
                else:
                    break
            except Exception as e:
                print("Error clicking 'Load More':", e)
                attempts += 1
        
        # Extract names, links, and image sources after all organizations have loaded
        html_content = driver.page_source
        names, links, image_sources = extract_names_links_and_images(html_content)
        
        # Close main driver
        driver.quit()
        
        # Prepare data for parallel processing
        org_data_list = list(zip(names, links, image_sources))
        total_orgs = len(org_data_list)
        print(f"Total organizations to process: {total_orgs}")
        
        # Process organizations in parallel with ThreadPoolExecutor
        data = []
        max_workers = min(4, total_orgs)  # Limit concurrent threads to avoid overwhelming the server
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_org = {executor.submit(process_organization, org_data): org_data for org_data in org_data_list}
            
            # Process completed tasks
            for i, future in enumerate(as_completed(future_to_org)):
                try:
                    result = future.result()
                    data.append(result)
                    if (i + 1) % 10 == 0 or (i + 1) == total_orgs:
                        print(f"Completed {i + 1}/{total_orgs} organizations")
                except Exception as e:
                    org_data = future_to_org[future]
                    print(f"Error processing organization {org_data[0]}: {e}")
                    data.append({
                        'Name': org_data[0], 
                        'Description': 'Error fetching data', 
                        'Email': 'Error', 
                        'Website': 'Error', 
                        'Instagram': 'Error',
                        'Image_Source': org_data[2]
                    })
        
        # Clean up any remaining drivers
        for future in future_to_org:
            if hasattr(thread_local, 'driver'):
                try:
                    thread_local.driver.quit()
                except:
                    pass
        
        
        # NEW: Save data to MongoDB
        print("\n" + "="*50)
        print("Saving data to MongoDB...")
        print("="*50)
        
        # Option 1: Using the class-based approach
        mongo_handler = MongoDBHandler()
        if mongo_handler.save_organizations_data(data):
            print("✅ Successfully saved organizations data to MongoDB!")
        else:
            print("❌ Failed to save organizations data to MongoDB")
        mongo_handler.close()
        
        # Option 2: Alternative using direct function approach (uncomment if preferred)
        # if save_organizations_data_direct(data):
        #     print("✅ Successfully saved organizations data to MongoDB!")
        # else:
        #     print("❌ Failed to save organizations data to MongoDB")
        
    except Exception as e:
        print(f"Main execution error: {e}")
        driver.quit()

if __name__ == "__main__":
    main()