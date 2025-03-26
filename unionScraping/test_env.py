import os
from dotenv import load_dotenv

# Load the .env file in the current directory
load_dotenv()

# Fetch the variable
mongo_uri = os.getenv("MONGO_URI")

if mongo_uri:
    print("✅ .env is working! MONGO_URI loaded:")
    print(mongo_uri)
else:
    print("❌ .env not loaded. MONGO_URI is None.")
