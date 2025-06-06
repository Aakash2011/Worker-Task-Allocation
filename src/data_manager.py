import json
import os
import pandas as pd
from typing import List, Dict, Any

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

def add_task(task_name: str, required_skills: List[str]):
    """Adds a new task to in-memory data and saves to file."""
    global _tasks
    _tasks.append({"name": task_name, "required_skills": required_skills})
    save_data(_tasks, TASKS_FILE)

def get_tasks() -> List[Dict[str, Any]]:
    """Returns all tasks currently in memory."""
    return _tasks

def add_worker(worker_name: str, available_skills: List[str], score: int = 5):
    """Adds a new worker to in-memory data and saves to file."""
    global _workers
    _workers.append({"name": worker_name, "available_skills": available_skills, "score": score})
    save_data(_workers, WORKERS_FILE)

def get_workers() -> List[Dict[str, Any]]:
    """Returns all workers currently in memory."""
    return _workers

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


# Example usage (for testing data_manager.py independently)
if __name__ == "__main__":
    print("--- Starting data_manager.py independent test ---")
    
    # Ensure source dummy files exist for testing
    _ensure_data_directory()
    save_data([{"name": "Test Task", "required_skills": ["TestSkill"]}], SOURCE_DUMMY_TASKS_FILE)
    save_data([{"name": "Test Worker", "available_skills": ["TestSkill"], "score": 5}], SOURCE_DUMMY_WORKERS_FILE)

    # Clear and then reset to see full cycle
    print("\nClearing all data...")
    clear_all_data()
    print(f"Tasks after clear: {get_tasks()}")
    print(f"Workers after clear: {get_workers()}")

    print("\nResetting data from files (should load dummy data from source_dummy_*.json)...")
    reset_data_from_files()
    print(f"Tasks after reset: {get_tasks()}")
    print(f"Workers after reset: {get_workers()}")

    print("\nAdding a new task and worker...")
    add_task("New App Task", ["Testing", "Deployment"])
    add_worker("New App Worker", ["Deployment"], 10)
    print(f"Current tasks: {get_tasks()}")
    print(f"Current workers: {get_workers()}")

    print("\nClearing data again to see if files become empty...")
    clear_all_data()
    print(f"Tasks after second clear: {get_tasks()}")
    print(f"Workers after second clear: {get_workers()}")

    print("\nResetting data again (should load dummy data from source_dummy_*.json again)...")
    reset_data_from_files()
    print(f"Tasks after second reset: {get_tasks()}")
    print(f"Workers after second reset: {get_workers()}")

    # Clean up test files
    os.remove(SOURCE_DUMMY_TASKS_FILE)
    os.remove(SOURCE_DUMMY_WORKERS_FILE)

    print("--- data_manager.py independent test complete ---")
