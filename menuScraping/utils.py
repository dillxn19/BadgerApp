"""Utility functions for the dining hall scraper."""

import re

def clean_for_url(text):
    """Clean text for use in URLs by removing special characters and formatting."""
    text = text.replace("'", "")
    text = re.sub(r'[^a-zA-Z0-9-]', '', text.replace(" ", "-"))
    return text.lower()

def is_duplicate_item(existing_items, new_item):
    """Check if an item already exists in the list with all the same attributes"""
    for item in existing_items:
        if (item['item_name'] == new_item['item_name'] and
            item['serving_size'] == new_item['serving_size'] and
            item['calories'] == new_item['calories']):
            return True
    return False