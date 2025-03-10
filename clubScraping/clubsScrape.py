from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import re
import csv  # Import the standard csv module instead

# Set up ChromeDriver with optimized options
options = webdriver.ChromeOptions()
options.add_argument('--disable-gpu')
options.add_argument('--disable-extensions')
options.add_argument('--disable-infobars')
options.add_argument('--start-maximized')
options.add_argument('--disable-dev-shm-usage')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Navigate to the website
url = "https://win.wisc.edu/organizations"
driver.get(url)

# Minimal wait for initial load
time.sleep(1)

# Function to extract organization names, links and image sources
def extract_names_links_and_images(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    organizations = soup.find('ul', class_='MuiList-root MuiList-padding').find_all('a')
    names = []
    links = []
    image_sources = []
    
    for org in organizations:
        name = org.find('div', style=lambda x: x and 'font-size: 1.125rem;' in x).text.strip()
        link = org.get('href')
        
        # Extract image source
        img_tag = org.find('img')
        image_src = img_tag.get('src') if img_tag else 'No image available'
        
        names.append(name)
        links.append(link)
        image_sources.append(image_src)
        
    return names, links, image_sources

# Function to extract description, email, website, and Instagram from the organization's page
def extract_details(driver):
    try:
        # Wait for the description element to load - shorter timeout
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.bodyText-large.userSupplied'))
        )
        description = driver.find_element(By.CSS_SELECTOR, '.bodyText-large.userSupplied').text.strip()
    except:
        description = 'No description available'

    website = 'No website available'
    instagram = 'No Instagram available'
    email = 'No email available'

    try:
        # Get the page source immediately
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Look for the span with class "sr-only" containing "Contact Email"
        email_span = soup.find('span', class_='sr-only', string='Contact Email')
        if email_span:
            # Find the parent div that contains the email
            parent_div = email_span.parent
            if parent_div:
                # Extract email using regex
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', parent_div.text)
                if email_match:
                    email = email_match.group()
        
        # Backup method for email - search for divs containing "E:" 
        if email == 'No email available':
            email_div = soup.find('div', string=lambda text: text and 'E:' in text if text else False)
            if email_div:
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', email_div.text)
                if email_match:
                    email = email_match.group()
        
        # Second backup method - search the entire page
        if email == 'No email available':
            all_email_matches = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', html_content)
            if all_email_matches:
                email = all_email_matches[0]  # Take the first email found
        
        # Find all links with aria-labels
        social_links = soup.find_all('a', attrs={'href': True})
        
        for link in social_links:
            href = link['href']
            aria_label = link.get('aria-label', '').lower()
            
            # Extract website - prioritize links with 'visit our site' or globe icon
            if ('visit our site' in aria_label or 
                'globe' in str(link) or 
                (href.startswith('http') and 
                 not any(social in href for social in ['instagram', 'facebook', 'linkedin', 'youtube', 'twitter', 'calendar.google']))):
                website = href
                
                # If we found a clear website, break to avoid overwriting with less relevant links
                if 'visit our site' in aria_label or 'globe' in str(link):
                    break
            
            # Extract Instagram
            if 'instagram' in aria_label or 'instagram.com' in href:
                instagram = href
                
    except Exception as e:
        print(f"Error extracting contact info: {e}")

    return description, email, website, instagram

# Load all organizations by clicking "Load More" - faster version
while True:
    try:
        # Wait for "Load More" button to be clickable - shorter timeout
        load_more_button = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Load More')]"))
        )
        load_more_button.click()

        # Wait minimally for new content
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".MuiList-root"))
        )
        time.sleep(0.2)  # Very small additional wait

    except Exception as e:
        print("No more 'Load More' button or error:", e)
        break  # Stop when no more "Load More" button is available or an error occurs

# Extract names, links, and image sources after all organizations have loaded
html_content = driver.page_source
names, links, image_sources = extract_names_links_and_images(html_content)

# List to store the extracted data
data = []

# Loop through the links to extract details
for i, (name, link, image_src) in enumerate(zip(names, links, image_sources)):
    if i % 10 == 0:  # Only print progress every 10 organizations to reduce console output
        print(f"Processing {i+1}/{len(names)}: {name}")
    try:
        driver.get(f"https://win.wisc.edu{link}")  # Navigate to the organization page
        description, email, website, instagram = extract_details(driver)
        data.append({
            'Name': name, 
            'Description': description, 
            'Email': email, 
            'Website': website, 
            'Instagram': instagram,
            'Image_Source': image_src
        })
        # No delay between organizations
    except Exception as e:
        print(f"Error processing {name}: {e}")
        data.append({
            'Name': name, 
            'Description': 'Error fetching data', 
            'Email': 'Error', 
            'Website': 'Error', 
            'Instagram': 'Error',
            'Image_Source': image_src  # Still include the image source even if other details fail
        })
        # Try to go back or restart from main page without delay
        try:
            driver.get(url)
        except:
            pass

# Save data to CSV with proper quoting
df = pd.DataFrame(data)
df.to_csv('organization_data.csv', index=False, quoting=csv.QUOTE_ALL)
print(f"Data saved to organization_data.csv. Total organizations processed: {len(data)}")

# Close the browser
driver.quit()