"""MongoDB operations for dining hall data - using working pattern."""

import pymongo
import certifi
from datetime import datetime
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
        """Establish connection to MongoDB using the working pattern."""
        try:
            print("Attempting to connect to MongoDB Atlas...")
            
            # Use the exact same pattern that works in your other script
            self.client = pymongo.MongoClient(
                self.uri,
                tlsCAFile=certifi.where(),
                maxPoolSize=50,
                connectTimeoutMS=30000,
                serverSelectionTimeoutMS=30000,
                socketTimeoutMS=45000
            )
            
            # Force a connection to verify it works
            self.client.admin.command('ping')
            print("MongoDB connection successful!")
            
            self.db = self.client[self.db_name]
            self.collection = self.db[self.collection_name]
            return True
            
        except pymongo.errors.ConfigurationError as e:
            print(f"MongoDB configuration error: {e}")
            print("This usually means the connection string is invalid")
            return False
        except pymongo.errors.ConnectionFailure as e:
            print(f"MongoDB connection failure: {e}")
            print("This usually means the MongoDB server is not reachable")
            return False
        except pymongo.errors.ServerSelectionTimeoutError as e:
            print(f"MongoDB server selection timeout: {e}")
            print("This could be due to network issues or incorrect hostname")
            return False
        except Exception as e:
            print(f"Unexpected MongoDB error: {e}")
            return False
    
    def save_dining_data(self, data):
        """Save dining hall data to MongoDB."""
        try:
            if not self.client:
                if not self.connect():
                    return False
            
            # Verify connection is still active
            self.client.admin.command('ping')
            
            # Add timestamp to data
            scrape_timestamp = datetime.now()
            for item in data:
                item['scrape_date'] = scrape_timestamp
                
            # Clear existing data from today to avoid duplicates
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            print("Clearing existing data from today...")
            delete_result = self.collection.delete_many({"scrape_date": {"$gte": today_start}})
            print(f"Deleted {delete_result.deleted_count} existing records")
            
            # Insert the new data
            if data:
                print("Inserting new data...")
                insert_result = self.collection.insert_many(data)
                print(f"Saved {len(insert_result.inserted_ids)} dining locations to MongoDB: {self.db_name}.{self.collection_name}")
            else:
                print("No data to save to MongoDB")
            
            return True
            
        except Exception as e:
            print(f"Error saving to MongoDB: {e}")
            return False
    
    def close(self):
        """Close MongoDB connection."""
        try:
            if self.client:
                self.client.close()
                print("MongoDB connection closed")
        except Exception as e:
            print(f"Error closing MongoDB connection: {e}")


# Alternative: Direct function approach (like your working script)
def create_mongodb_connection():
    """Create MongoDB connection using the exact working pattern."""
    try:
        print("Attempting to connect to MongoDB Atlas...")
        atlas_connection_string = MONGO_URI
        
        # Use the exact same parameters that work
        client = pymongo.MongoClient(
            atlas_connection_string,
            tlsCAFile=certifi.where(),
            maxPoolSize=50,
            connectTimeoutMS=30000,
            serverSelectionTimeoutMS=30000,
            socketTimeoutMS=45000
        )
        
        # Force a connection to verify it works
        client.admin.command('ping')
        print("MongoDB connection successful!")
        
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        
        return client, db, collection
        
    except pymongo.errors.ConfigurationError as e:
        print(f"MongoDB configuration error: {e}")
        print("This usually means the connection string is invalid")
        return None, None, None
    except pymongo.errors.ConnectionFailure as e:
        print(f"MongoDB connection failure: {e}")
        print("This usually means the MongoDB server is not reachable")
        return None, None, None
    except pymongo.errors.ServerSelectionTimeoutError as e:
        print(f"MongoDB server selection timeout: {e}")
        print("This could be due to network issues or incorrect hostname")
        return None, None, None
    except Exception as e:
        print(f"Unexpected MongoDB error: {e}")
        return None, None, None


def save_dining_data_direct(data):
    """Save dining data using direct connection approach."""
    client, db, collection = create_mongodb_connection()
    
    if not client:
        return False
    
    try:
        # Add timestamp to data
        scrape_timestamp = datetime.now()
        for item in data:
            item['scrape_date'] = scrape_timestamp
            
        # Clear existing data from today to avoid duplicates
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        print("Clearing existing data from today...")
        delete_result = collection.delete_many({"scrape_date": {"$gte": today_start}})
        print(f"Deleted {delete_result.deleted_count} existing records")
        
        # Insert the new data
        if data:
            print("Inserting new data...")
            insert_result = collection.insert_many(data)
            print(f"Saved {len(insert_result.inserted_ids)} dining locations to MongoDB: {DB_NAME}.{COLLECTION_NAME}")
        else:
            print("No data to save to MongoDB")
        
        return True
        
    except Exception as e:
        print(f"Error saving to MongoDB: {e}")
        return False
    finally:
        client.close()