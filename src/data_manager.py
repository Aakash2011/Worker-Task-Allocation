import json
import os
import pandas as pd
from typing import List, Dict, Any
import streamlit as st # Import streamlit to use st.error

DATA_DIR = "data"
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
WORKERS_FILE = os.path.join(DATA_DIR, "workers.json")

# --- New: File paths for the source of initial dummy data ---
SOURCE_DUMMY_TASKS_FILE = os.path.join(DATA_DIR, "dummy_tasks.json")
SOURCE_DUMMY_WORKERS_FILE = os.path.join(DATA_DIR, "dummy_workers.json")

# In-memory storage for tasks and workers
_tasks: List[Dict[str, Any]] = []
_workers: List[Dict[str, Any]] = []

def _ensure_data_directory():
    """Ensures the data directory exists."""
    os.makedirs(DATA_DIR, exist_ok=True)

def save_data(data: List[Dict[str, Any]], filename: str):
    """Saves data to a JSON file."""
    _ensure_data_directory()
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def load_data_from_file(filename: str) -> List[Dict[str, Any]]:
    """Loads data from a JSON file. Returns empty list if file not found or corrupted."""
    _ensure_data_directory()
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                # Handle empty file case
                content = f.read()
                if not content.strip(): # Check if file is empty or just whitespace
                    return []
                return json.loads(content)
        except json.JSONDecodeError:
            print(f"Warning: {filename} is malformed. Initializing as empty list.")
            return []
    return []

def _write_initial_dummy_data_to_files():
    """
    Writes the predefined dummy data (loaded from source dummy JSONs)
    to the main tasks and workers JSON files.
    """
    _ensure_data_directory()
    
    # Load dummy data from source files
    dummy_tasks = load_data_from_file(SOURCE_DUMMY_TASKS_FILE)
    dummy_workers = load_data_from_file(SOURCE_DUMMY_WORKERS_FILE)

    # Save loaded dummy data to the main working files
    save_data(dummy_tasks, TASKS_FILE)
    save_data(dummy_workers, WORKERS_FILE)
    print("Predefined dummy data written to main data files.")

def _load_in_memory_data():
    """Loads tasks and workers data into in-memory variables from files."""
    global _tasks, _workers
    _tasks = load_data_from_file(TASKS_FILE)
    _workers = load_data_from_file(WORKERS_FILE)
    print("In-memory data loaded from files.")

# REVERTED: add_task - no edit functionality for tasks
def add_task(task_name: str, required_skills: List[str]):
    """Adds a new task to in-memory data and saves to file."""
    global _tasks
    # The check for uniqueness is now done in app.py before calling this function,
    # but keeping a redundant check here for robustness in case of direct calls.
    if any(t["name"].lower() == task_name.lower() for t in _tasks):
        # In this specific case, the warning message is handled by app.py
        # but for robustness, if this function were called directly,
        # you might want to raise an error or return a status.
        # For now, we'll assume app.py handles the primary warning.
        return False # Indicate that task was not added due to duplicate
    _tasks.append({"name": task_name, "required_skills": required_skills})
    save_data(_tasks, TASKS_FILE)
    return True # Indicate success

# MODIFIED: add_or_update_worker - allows editing existing workers
def add_or_update_worker(worker_name: str, available_skills: List[str], score: int = 5, original_name: str = None):
    """Adds a new worker or updates an existing worker in-memory and saves to file."""
    global _workers
    
    # When updating, if the name has changed, remove the old entry
    if original_name and original_name != worker_name:
        _workers = [w for w in _workers if w["name"].lower() != original_name.lower()]

    found = False
    for worker in _workers:
        if worker["name"].lower() == worker_name.lower(): # Case-insensitive check
            worker["available_skills"] = available_skills
            worker["score"] = score
            found = True
            break
    
    if not found:
        _workers.append({"name": worker_name, "available_skills": available_skills, "score": score})
    
    save_data(_workers, WORKERS_FILE)


def get_tasks() -> List[Dict[str, Any]]:
    """Returns all tasks currently in memory."""
    return _tasks

def get_workers() -> List[Dict[str, Any]]:
    """Returns all workers currently in memory."""
    return _workers

# REMOVED: delete_task function

# KEPT: delete_worker function
def delete_worker(worker_name: str):
    """Deletes a worker from in-memory data and saves to file."""
    global _workers
    _workers = [w for w in _workers if w["name"].lower() != worker_name.lower()] # Case-insensitive delete
    save_data(_workers, WORKERS_FILE)

def clear_all_data():
    """Clears all task and worker data, both in-memory and by saving empty lists to files.
       Files are NOT deleted."""
    global _tasks, _workers
    _tasks = []
    _workers = []
    save_data(_tasks, TASKS_FILE) # Save empty lists to files
    save_data(_workers, WORKERS_FILE)
    print("All task and worker data cleared (in-memory and files set to empty).")

def reset_data_from_files():
    """Resets in-memory data and the JSON files to the predefined dummy data
       loaded from source dummy files."""
    _write_initial_dummy_data_to_files() # First, write the dummy data from sources to main files
    _load_in_memory_data() # Then, load it into memory
    print("Data has been reset to initial dummy data from source files.")

# --- Initial Setup / Load when the module is imported ---
# Ensure data directory exists and either load existing data or write dummy data from sources
_ensure_data_directory()

# If the main working files (tasks.json, workers.json) don't exist or are empty,
# then populate them with the initial dummy data from the source files.
if not os.path.exists(TASKS_FILE) or not os.path.exists(WORKERS_FILE) or \
   not load_data_from_file(TASKS_FILE) or not load_data_from_file(WORKERS_FILE):
    _write_initial_dummy_data_to_files()

# Load initial data into memory from the main working files
_load_in_memory_data()