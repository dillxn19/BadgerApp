"""MongoDB operations for dining hall data."""

from datetime import datetime
from pymongo import MongoClient
from config import MONGO_URI, DB_NAME, COLLECTION_NAME

class MongoDBHandler:
    def __init__(self, uri=MONGO_URI, db_name=DB_NAME, collection_name=COLLECTION_NAME):
        self.uri = uri
        self.db_name = db_name
        self.collection_name = collection_name
        self.client = None
        self.db = None
        self.collection = None
    
    def connect(self):
        """Establish connection to MongoDB."""
        try:
            self.client = MongoClient(self.uri)
            self.db = self.client[self.db_name]
            self.collection = self.db[self.collection_name]
            return True
        except Exception as e:
            print(f"Error connecting to MongoDB: {e}")
            return False
    
    def save_dining_data(self, data):
        """Save dining hall data to MongoDB."""
        try:
            if not self.client:
                if not self.connect():
                    return False
            
            # Add timestamp to data
            scrape_timestamp = datetime.now()
            for item in data:
                item['scrape_date'] = scrape_timestamp
                
            # Clear existing data from today to avoid duplicates
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            self.collection.delete_many({"scrape_date": {"$gte": today_start}})
            
            # Insert the new data
            if data:
                self.collection.insert_many(data)
                print(f"Saved {len(data)} dining locations to MongoDB: {self.db_name}.{self.collection_name}")
            else:
                print("No data to save to MongoDB")
            
            return True
            
        except Exception as e:
            print(f"Error saving to MongoDB: {e}")
            return False
    
    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()