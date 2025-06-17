import streamlit as st
import pandas as pd
import time # Import the time module

# Import the new functions from data_manager
from src.data_manager import add_task, get_tasks, add_or_update_worker, get_workers, clear_all_data, reset_data_from_files, save_data, delete_worker
from src.optimization_model import solve_task_allocation

# --- Global Page Configuration (needs to be at the very top) ---
st.set_page_config(
    page_title="Heineken Task Allocator",
    page_icon="🍺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Helper Functions for UI elements ---
def render_main_title(title, description=None):
    """Renders the main page title in a large, green, bold style."""
    st.markdown(f"<h1 style='color: {st.get_option('theme.primaryColor')}; font-size: 3.5em; font-weight: bold; margin-bottom: 0px;'>{title}</h1>", unsafe_allow_html=True)
    if description:
        st.markdown(f"<p style='font-size: 1.2em; color: #555555; margin-top: 0px;'>{description}</p>", unsafe_allow_html=True)
    st.markdown("---")

def render_section_title(title):
    """Renders a section title (smaller than main title, but still prominent)."""
    st.markdown(f"<h2 style='color: {st.get_option('theme.primaryColor')}; font-size: 2em; font-weight: bold;'>{title}</h2>", unsafe_allow_html=True)
    st.markdown("---")


def home_page():
    render_main_title(
        "Brewery Task Allocation Optimizer",
    )

    st.markdown("""
    <div style='font-size: 1.1em;'>
    Welcome to the Heineken Brewery Task Allocation Optimizer. This application helps you
    streamline your production line by intelligently assigning tasks based on worker skills,
    aiming to achieve maximum output with the most efficient use of your workforce.
    </div>
    <br>
    """, unsafe_allow_html=True)

    st.info("Use the navigation in the sidebar to define tasks and workers, then run the allocation model")
    st.markdown("---")
    st.write("### Key Features:")
    st.markdown("""
    - **Define Tasks:** Specify production tasks and their required skill sets.
    - **Manage Workers:** Create worker profiles with their available skills.
    - **Optimal Allocation:** Leverage mathematical optimization to find the best task-to-worker assignments.
    - **Resource Minimization:** Minimize the total number of workers required for all tasks.
    - **Skill Matching:** Ensure every task is covered by workers possessing the necessary skills (even by teams!).
    - **Worker Prioritization:** Assign scores to workers to influence task allocation (e.g., prefer high-scoring workers).
    """)


def add_task_page():
    render_main_title("Define Production Tasks", "Specify each task and the unique skills essential for its completion")

    # Message container for temporary messages related to form submission
    form_message_container = st.empty()

    with st.form("add_task_form", clear_on_submit=True): # Keep clear_on_submit=True
        render_section_title("New Task Details")
        col1, col2 = st.columns(2)
        with col1:
            task_name = st.text_input(
                "Task Name",
                key="task_name_input",
                placeholder="e.g., Fermentation Monitoring",
                help="Enter a unique name for the production task."
            )
        with col2:
            skills_input = st.text_area(
                "Required Skills (comma-separated)",
                key="task_skills_input",
                placeholder="e.g., Chemistry, Quality Control, Data Analysis",
                help="List all skills required for this task, separated by commas."
            )

        st.markdown("---")
        submit_button = st.form_submit_button("Add Task to Inventory", type="primary")

        if submit_button:
            if task_name and skills_input:
                tasks = get_tasks()
                existing_task_names = [task['name'].lower() for task in tasks] # Case-insensitive check

                if task_name.lower() in existing_task_names:
                    form_message_container.warning(f"Task '{task_name}' already exists. Please choose a different name.")
                    time.sleep(2)
                else:
                    required_skills = [s.strip().title() for s in skills_input.split(',') if s.strip()]
                    add_task(task_name, required_skills)
                    form_message_container.success(f"Task '{task_name}' added successfully to the system!")
                    time.sleep(2) # Keep for message visibility
                    st.rerun() # Rerun to refresh the displayed data
            else:
                form_message_container.error("Please ensure both 'Task Name' and 'Required Skills' are filled.")
                time.sleep(2) # Keep for message visibility


    st.markdown("---")
    render_section_title("Current Task Inventory")
    tasks = get_tasks()
    if tasks:
        df_tasks = pd.DataFrame(tasks)
        df_tasks.rename(columns={'name': 'Task Name', 'required_skills': 'Required Skills'}, inplace=True)
        df_tasks['Required Skills'] = df_tasks['Required Skills'].apply(lambda x: ', '.join(x))

        st.dataframe(df_tasks[['Task Name', 'Required Skills']], use_container_width=True, hide_index=True)
        st.markdown("---")
    else:
        st.info("No tasks have been added yet. Use the form above to begin building your task inventory.")


def add_worker_page():
    render_main_title("Manage Worker Profiles", "Assign skills to workers. For consistency and accuracy, worker skills can only be chosen from the set of skills required by existing tasks")

    # Message container for temporary messages related to form submission
    form_message_container = st.empty()

    # Placeholder for the worker form
    worker_form_placeholder = st.empty()


    # Initialize session state for editing if not already present
    if 'editing_worker' not in st.session_state:
        st.session_state.editing_worker = None
    # Remove scroll_to_top as we are changing the approach
    # if 'scroll_to_top' not in st.session_state:
    #     st.session_state.scroll_to_top = False


    tasks = get_tasks()
    all_required_skills = set()
    for task in tasks:
        all_required_skills.update(task.get("required_skills", []))

    available_skills_for_selection = sorted(list(all_required_skills))

    if not available_skills_for_selection:
        st.warning("No tasks or required skills defined yet. Please add tasks first using the 'Add Task' section to populate the pool of available skills for workers.")
        st.info("Worker skills must be selected from the skills demanded by existing tasks to ensure practical applicability.")
        return

    # Set initial values for form inputs based on editing_worker or clear state
    current_worker_name = ""
    current_selected_skills = []
    current_worker_score = 5
    original_worker_name = None

    if st.session_state.editing_worker:
        current_worker_name = st.session_state.editing_worker['name']
        current_selected_skills = st.session_state.editing_worker['available_skills']
        current_worker_score = st.session_state.editing_worker['score']
        original_worker_name = st.session_state.editing_worker['name']
    # If not editing, and no error on previous submission, ensure inputs are blank for new entry
    elif not st.session_state.get('worker_form_error', False):
        current_worker_name = ""
        current_selected_skills = []
        current_worker_score = 5


    # Reset error flag for current rerun
    if 'worker_form_error' in st.session_state:
        del st.session_state.worker_form_error


    # Render the form inside the placeholder
    with worker_form_placeholder.container():
        with st.form("add_worker_form", clear_on_submit=not st.session_state.editing_worker):
            render_section_title(
                "Edit Worker Details" if st.session_state.editing_worker else "New Worker Details"
            )
            col1, col2 = st.columns(2)
            with col1:
                worker_name = st.text_input(
                    "Worker Name",
                    value=current_worker_name,
                    key="worker_name_input",
                    placeholder="e.g., John Doe",
                    help="Enter the name of the worker."
                )
            with col2:
                selected_skills = st.multiselect(
                    "Available Skills (Select all that apply)",
                    options=available_skills_for_selection,
                    default=current_selected_skills,
                    key="worker_skills_multiselect",
                    help="Select skills this worker possesses from the list generated from existing tasks."
                )

            with st.expander("Advanced Settings"):
                worker_score = st.slider(
                    "Worker Score (0 - 10)",
                    min_value=0,
                    max_value=10,
                    value=current_worker_score,
                    step=1,
                    key="worker_score_slider",
                    help="An optional score to indicate a worker's overall proficiency or preference. Higher scores might lead to tasks being assigned to them first."
                )

            st.markdown("---")
            col_buttons = st.columns([0.2, 0.2, 0.6])
            with col_buttons[0]:
                submit_button = st.form_submit_button(
                    "Update Worker" if st.session_state.editing_worker else "Add Worker to Team",
                    type="primary"
                )
            with col_buttons[1]:
                if st.session_state.editing_worker:
                    cancel_edit_button = st.form_submit_button("Cancel Edit")
                    if cancel_edit_button:
                        st.session_state.editing_worker = None
                        form_message_container.empty()
                        st.rerun() # Rerun to switch back to "Add New" form with cleared values

            if submit_button:
                form_message_container.empty()
                if worker_name and selected_skills:
                    workers = get_workers()
                    existing_worker_names = [worker['name'].lower() for worker in workers]

                    if st.session_state.editing_worker:
                        if worker_name.lower() != original_worker_name.lower() and worker_name.lower() in existing_worker_names:
                            form_message_container.warning(f"Worker '{worker_name}' already exists. Please choose a different name.")
                            st.session_state.worker_form_error = True
                            time.sleep(2)
                        else:
                            add_or_update_worker(worker_name, selected_skills, worker_score, original_name=original_worker_name)
                            form_message_container.success(f"Worker '{worker_name}' updated successfully!")
                            st.session_state.editing_worker = None # Exit edit mode after update
                            time.sleep(2)
                            st.rerun()
                    else: # Adding a new worker
                        if worker_name.lower() in existing_worker_names:
                            form_message_container.warning(f"Worker '{worker_name}' already exists. Please choose a different name.")
                            st.session_state.worker_form_error = True
                            time.sleep(2)
                        else:
                            add_or_update_worker(worker_name, selected_skills, worker_score)
                            form_message_container.success(f"Worker '{worker_name}' added with skills: {', '.join(selected_skills)} and score: {worker_score}.")
                            time.sleep(2) # Show message for 2 seconds
                            st.rerun() # Rerun to refresh the displayed data and clear form (if clear_on_submit=True for new)
                else:
                    form_message_container.error("Please enter a worker name and select at least one skill.")
                    st.session_state.worker_form_error = True
                    time.sleep(2)


    st.markdown("---")
    render_section_title("Current Workforce")
    workers = get_workers()
    if workers:
        df_workers = pd.DataFrame(workers)
        df_workers.rename(columns={'name': 'Worker Name', 'available_skills': 'Available Skills', 'score': 'Score'}, inplace=True)
        df_workers['Available Skills'] = df_workers['Available Skills'].apply(lambda x: ', '.join(x))

        for i, row in df_workers.iterrows():
            cols = st.columns([0.6, 0.2, 0.2])
            cols[0].write(f"**{row['Worker Name']}**")
            cols[0].markdown(f"<small>Skills: {row['Available Skills']} | Score: {row['Score']}</small>", unsafe_allow_html=True)

            with cols[1]:
                if st.button("✏️ Edit", key=f"edit_worker_{i}"):
                    st.session_state.editing_worker = {
                        "name": row['Worker Name'],
                        "available_skills": row['Available Skills'].split(', '),
                        "score": row['Score']
                    }
                    form_message_container.empty()
                    # No explicit scroll, but the form will now be at the top of the placeholder
                    st.rerun()
            with cols[2]:
                if st.button("🗑️ Delete", key=f"delete_worker_{i}"):
                    delete_worker(row['Worker Name'])
                    form_message_container.success(f"Worker '{row['Worker Name']}' deleted.")
                    time.sleep(2)
                    if st.session_state.editing_worker and st.session_state.editing_worker['name'] == row['Worker Name']:
                        st.session_state.editing_worker = None
                    st.rerun()
        st.markdown("---")
    else:
        st.info("No worker profiles have been added yet. Use the form above to start building your workforce.")


def run_optimization_page():
    render_main_title("Run Optimization & Review Results", "Analyze optimal task assignments for your brewery")

    tasks = get_tasks()
    workers = get_workers()

    st.markdown("---")

    col_tasks, col_workers = st.columns(2)

    with col_tasks:
        render_section_title("Current Tasks")
        if tasks:
            df_tasks = pd.DataFrame(tasks)
            df_tasks.rename(columns={'name': 'Task Name', 'required_skills': 'Required Skills'}, inplace=True)
            df_tasks['Required Skills'] = df_tasks['Required Skills'].apply(lambda x: ', '.join(x))
            st.dataframe(df_tasks[['Task Name', 'Required Skills']], use_container_width=True, hide_index=True)
        else:
            st.warning("No tasks defined. Please add tasks from the sidebar.")

    with col_workers:
        render_section_title("Current Workers")
        if workers:
            df_workers = pd.DataFrame(workers)
            df_workers.rename(columns={'name': 'Worker Name', 'available_skills': 'Available Skills', 'score': 'Score'}, inplace=True)
            df_workers['Available Skills'] = df_workers['Available Skills'].apply(lambda x: ', '.join(x))
            display_columns = ['Worker Name', 'Available Skills']
            if 'Score' in df_workers.columns:
                display_columns.append('Score')
            st.dataframe(df_workers[display_columns], use_container_width=True, hide_index=True)
        else:
            st.warning("No workers defined. Please add workers from the sidebar.")

    st.markdown("---")

    st.info("Click the button below to run the optimization model. It will determine the minimum number of workers required and their optimal task assignments based on skill matching, preferring high-score workers.")

    opt_message_placeholder = st.empty()

    if st.button("Run Optimization", use_container_width=True, type="primary"):
        opt_message_placeholder.empty()

        if not tasks:
            opt_message_placeholder.error("Optimization cannot run: No tasks have been defined. Please add tasks first.")
            time.sleep(2)
            opt_message_placeholder.empty()
            return
        if not workers:
            opt_message_placeholder.error("Optimization cannot run: No workers have been defined. Please add workers first.")
            time.sleep(2)
            opt_message_placeholder.empty()
            return

        with st.spinner("Optimizing task assignments... This might take a moment."):
            results = solve_task_allocation(tasks, workers)

        if results:
            opt_message_placeholder.success("Optimization Complete! See results below.")
            time.sleep(2)
            opt_message_placeholder.empty()
            st.markdown("---")
            render_section_title("Optimization Summary")

            col_obj, col_unused = st.columns(2)
            with col_obj:
                st.metric(label="Minimum Workers Required", value=int(results['minimum_workers_count']), delta_color="off")
            with col_unused:
                total_workers_available = len(get_workers())
                workers_utilized = len(results['workers_used'])
                workers_unused = total_workers_available - workers_utilized
                st.metric(label="Workers Not Utilized", value=workers_unused, delta_color="off")

            st.markdown("---")
            render_section_title("Detailed Task Assignments")

            assignments_data = []
            for task, workers_list in results['assignments'].items():
                assignments_data.append({
                    "Task": task,
                    "Assigned Workers": ", ".join(workers_list) if workers_list else "No Worker Assigned (Problem with Solver/Data)"
                })

            with st.expander("Click to view individual task assignments", expanded=True):
                st.dataframe(pd.DataFrame(assignments_data), use_container_width=True, hide_index=True)

            st.markdown("---")
            render_section_title("Workers Utilized")
            if results['workers_used']:
                st.write(f"The following workers are part of the optimal solution: **{', '.join(results['workers_used'])}**")
            else:
                st.warning("No workers were utilized. This might indicate an empty task list or an issue with the solution.")

        else:
            opt_message_placeholder.error("Could not find an optimal solution. Please check your tasks and workers for feasibility. Ensure all required skills can be met by your available workforce.")
            time.sleep(2)
            opt_message_placeholder.empty()

    st.markdown("---")
    st.info("🔄 **Reset Data:** Click the button below to revert to the dummy data'. This will overwrite any unsaved changes.")
    if st.button("🔵 Reset Data", use_container_width=True, type="secondary", help="This will clear current in-memory data and reload dummy data."):
        reset_data_from_files()
        st.success("Data has been reset!")
        time.sleep(2)
        st.session_state.editing_worker = None
        st.rerun()

    st.warning("⚠️ **Danger Zone:** Use the button below to clear all stored task and worker data.")
    if st.button("🔴 Clear All Data", use_container_width=True, type="secondary" ,help="This will permanently delete all saved tasks and workers."):
        clear_all_data()
        st.success("All task and worker data has been cleared.")
        time.sleep(2)
        st.session_state.editing_worker = None
        st.rerun()

# --- Streamlit App Layout (Main Logic) ---
if 'page' not in st.session_state:
    st.session_state.page = "Run Optimization" # Changed initial page to "Run Optimization"

with st.sidebar:

    if st.button("Home", use_container_width=True, type="secondary"):
        if st.session_state.page != "Home":
            st.session_state.page = "Home"
            st.session_state.editing_worker = None
            st.rerun()

    st.markdown("---")

    navigation_options = ["Add Task", "Add Worker", "Run Optimization"]

    current_radio_index = None
    if st.session_state.page in navigation_options:
        current_radio_index = navigation_options.index(st.session_state.page)

    selected_page_from_radio = st.radio(
        "Navigation",
        options=navigation_options,
        index=current_radio_index,
        key="main_navigation_radio",
        label_visibility="hidden"
    )

    if selected_page_from_radio and selected_page_from_radio != st.session_state.page:
        st.session_state.page = selected_page_from_radio
        st.session_state.editing_worker = None
        st.rerun()

if st.session_state.page == "Home":
    home_page()
elif st.session_state.page == "Add Task":
    add_task_page()
elif st.session_state.page == "Add Worker":
    add_worker_page()
elif st.session_state.page == "Run Optimization":
    run_optimization_page()