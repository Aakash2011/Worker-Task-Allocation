import json
import os
import pandas as pd
from typing import List, Dict, Any

DATA_DIR = "data"
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
WORKERS_FILE = os.path.join(DATA_DIR, "workers.json")

def _ensure_data_directory():
    """Ensures the data directory exists."""
    os.makedirs(DATA_DIR, exist_ok=True)

def save_data(data: List[Dict[str, Any]], filename: str):
    """Saves data to a JSON file."""
    _ensure_data_directory()
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def load_data(filename: str) -> List[Dict[str, Any]]:
    """Loads data from a JSON file."""
    _ensure_data_directory()
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return []

def add_task(task_name: str, required_skills: List[str]):
    """Adds a new task."""
    tasks = load_data(TASKS_FILE)
    tasks.append({"name": task_name, "required_skills": required_skills})
    save_data(tasks, TASKS_FILE)

def get_tasks() -> List[Dict[str, Any]]:
    """Returns all tasks."""
    return load_data(TASKS_FILE)

# MODIFIED: Add 'score' parameter with a default value
def add_worker(worker_name: str, available_skills: List[str], score: int = 5):
    """Adds a new worker with an optional score."""
    workers = load_data(WORKERS_FILE)
    workers.append({"name": worker_name, "available_skills": available_skills, "score": score})
    save_data(workers, WORKERS_FILE)

def get_workers() -> List[Dict[str, Any]]:
    """Returns all workers."""
    return load_data(WORKERS_FILE)

def clear_all_data():
    """Clears all task and worker data."""
    _ensure_data_directory()
    if os.path.exists(TASKS_FILE):
        os.remove(TASKS_FILE)
    if os.path.exists(WORKERS_FILE):
        os.remove(WORKERS_FILE)
    print("All task and worker data cleared.")

# Example usage (for testing data_manager.py independently)
if __name__ == "__main__":
    clear_all_data() # Start fresh for demonstration

    print("Adding sample tasks...")
    add_task("Bottling Line Setup", ["Mechanical", "Safety", "Calibration"])
    add_task("Fermentation Monitoring", ["Chemistry", "Quality Control", "Data Analysis"])
    add_task("Packaging Inspection", ["Quality Control", "Attention to Detail"])
    add_task("Brewing Kettle Operation", ["Brewing", "Process Control"])
    print(f"Current tasks: {get_tasks()}")

    print("\nAdding sample workers...")
    add_worker("Alice", ["Mechanical", "Safety", "Brewing"], 8) # Worker with score 8
    add_worker("Bob", ["Chemistry", "Quality Control", "Data Analysis"], 6) # Worker with score 6
    add_worker("Charlie", ["Mechanical", "Attention to Detail", "Safety"]) # Worker with default score 5
    add_worker("David", ["Brewing", "Process Control", "Quality Control"], 9) # Worker with score 9
    add_worker("Eve", ["Quality Control", "Attention to Detail", "Mechanical"], 7) # Worker with score 7
    print(f"Current workers: {get_workers()}")