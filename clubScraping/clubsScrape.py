from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time

# Set up ChromeDriver
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

# Navigate to the website
url = "https://win.wisc.edu/organizations"
driver.get(url)

# Wait for the content to load
time.sleep(3)  # Adjust as needed

# Function to extract organization names and links
def extract_names_and_links(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    organizations = soup.find('ul', class_='MuiList-root MuiList-padding').find_all('a')
    names = []
    links = []
    for org in organizations:
        name = org.find('div', style=lambda x: x and 'font-size: 1.125rem;' in x).text.strip()
        link = org.get('href')
        names.append(name)
        links.append(link)
    return names, links

# Function to extract description from the organization's page
def extract_description(driver):
    try:
        # Wait for the description element to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.bodyText-large.userSupplied'))
        )
        description = driver.find_element(By.CSS_SELECTOR, '.bodyText-large.userSupplied').text
        return description.strip()
    except:
        return 'No description available'

# Load all organizations by clicking "Load More"
while True:
    try:
        # Wait for "Load More" button to be clickable
        load_more_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Load More')]"))
        )
        load_more_button.click()

        # Wait for new content to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".MuiList-root"))
        )
        time.sleep(1)  # Small additional wait to ensure content is rendered

    except Exception as e:
        print("No more 'Load More' button or error:", e)
        break  # Stop when no more "Load More" button is available or an error occurs

# Extract names and links after all organizations have loaded
html_content = driver.page_source
names, links = extract_names_and_links(html_content)

# List to store the extracted data
data = []

# Loop through the links to extract descriptions
for name, link in zip(names, links):
    driver.get(f"https://win.wisc.edu{link}")  # Navigate to the organization page
    description = extract_description(driver)
    data.append({'Name': name, 'Description': description})
    driver.back()  # Go back to the main page

# Save names and descriptions to CSV with proper quoting
df = pd.DataFrame(data)
df.to_csv('organization_names_and_descriptions.csv', index=False, quoting=pd.io.common.csv.QUOTE_ALL)

# Close the browser
driver.quit()
