import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

from src.data_manager import (
    add_task, get_tasks, add_or_update_worker, get_workers,
    clear_all_data, reset_data_from_files, delete_worker
)
from src.optimization_model import solve_task_allocation

# --- Global Page Configuration ---
st.set_page_config(
    page_title="Heineken Task Allocator",
    page_icon="🍺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Session State Initialization ---
if 'optimization_results' not in st.session_state:
    st.session_state.optimization_results = None
if 'editing_worker' not in st.session_state:
    st.session_state.editing_worker = None
if 'show_add_task_form' not in st.session_state:
    st.session_state.show_add_task_form = False
if 'show_add_worker_form' not in st.session_state:
    st.session_state.show_add_worker_form = False


# --- Helper Functions ---
def get_primary_color():
    """Returns the theme primary color."""
    return st.get_option('theme.primaryColor') or '#00722C'


def generate_machine_state_data():
    """Generate mock machine state data for the week."""
    machines = ["Line A - Bottling", "Line B - Canning", "Line C - Kegging", "Line D - Packaging"]
    states = []
    base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Start from Monday of current week
    days_since_monday = base_date.weekday()
    monday = base_date - timedelta(days=days_since_monday)

    state_colors = {
        "Production": "#28a745",
        "Cleaning": "#ffc107",
        "Maintenance": "#dc3545",
        "Idle": "#6c757d"
    }

    for machine in machines:
        current_time = monday
        for day in range(7):
            day_start = monday + timedelta(days=day)
            # Morning shift - typically production
            states.append({
                "Machine": machine,
                "State": "Production",
                "Start": day_start + timedelta(hours=6),
                "End": day_start + timedelta(hours=12),
                "Color": state_colors["Production"]
            })
            # Afternoon - mix of states
            if day % 3 == 0:  # Maintenance day
                states.append({
                    "Machine": machine,
                    "State": "Maintenance",
                    "Start": day_start + timedelta(hours=12),
                    "End": day_start + timedelta(hours=16),
                    "Color": state_colors["Maintenance"]
                })
            elif day % 2 == 0:  # Cleaning day
                states.append({
                    "Machine": machine,
                    "State": "Cleaning",
                    "Start": day_start + timedelta(hours=12),
                    "End": day_start + timedelta(hours=14),
                    "Color": state_colors["Cleaning"]
                })
                states.append({
                    "Machine": machine,
                    "State": "Production",
                    "Start": day_start + timedelta(hours=14),
                    "End": day_start + timedelta(hours=18),
                    "Color": state_colors["Production"]
                })
            else:
                states.append({
                    "Machine": machine,
                    "State": "Production",
                    "Start": day_start + timedelta(hours=12),
                    "End": day_start + timedelta(hours=18),
                    "Color": state_colors["Production"]
                })

    return pd.DataFrame(states)


def generate_schedule_data(results, tasks):
    """Generate schedule visualization data from optimization results."""
    if not results or not results.get('assignments'):
        return pd.DataFrame()

    schedule_data = []
    base_date = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)

    # Map tasks to machines (for demo purposes)
    task_to_machine = {}
    machines = ["Line A - Bottling", "Line B - Canning", "Line C - Kegging", "Line D - Packaging"]
    for i, task in enumerate(tasks):
        task_to_machine[task['name']] = machines[i % len(machines)]

    time_offset = 0
    for task_name, assigned_workers in results['assignments'].items():
        if assigned_workers:
            # Find task details
            task_info = next((t for t in tasks if t['name'] == task_name), None)
            skills_str = ", ".join(task_info['required_skills']) if task_info else ""

            duration = 2  # Default 2 hours per task
            for worker in assigned_workers:
                schedule_data.append({
                    "Task": task_name,
                    "Person": worker,
                    "Machine": task_to_machine.get(task_name, "Line A - Bottling"),
                    "Start": base_date + timedelta(hours=time_offset),
                    "End": base_date + timedelta(hours=time_offset + duration),
                    "Skills": skills_str,
                    "Type": "Scheduled"
                })
            time_offset += duration + 0.5  # Gap between tasks

    return pd.DataFrame(schedule_data)


def calculate_worker_utilization(results, workers):
    """Calculate utilization percentage for each worker."""
    utilization = {}
    total_capacity = 8  # 8 hour workday

    for worker in workers:
        worker_name = worker['name']
        if results and worker_name in results.get('workers_used', []):
            # Count how many tasks assigned
            tasks_assigned = sum(
                1 for task_workers in results['assignments'].values()
                if worker_name in task_workers
            )
            utilization[worker_name] = min(tasks_assigned * 0.25, 1.0)  # Each task = 25% capacity
        else:
            utilization[worker_name] = 0.0

    return utilization


# --- Sidebar: Control Panel ---
with st.sidebar:
    st.markdown(f"### 🍺 Heineken Optimizer")
    st.markdown("---")

    # Scenario Selector
    st.markdown("#### 📋 Scenario")
    scenario = st.selectbox(
        "Planning Scenario",
        ["Standard Week", "High Production", "Maintenance Week", "Shutdown Period"],
        help="Select the operational scenario for optimization"
    )

    st.markdown("---")

    # Optimization Weights
    st.markdown("#### ⚖️ Optimization Weights")

    minimize_workers_weight = st.slider(
        "Minimize Workers vs Task Coverage",
        min_value=0.0,
        max_value=1.0,
        value=0.7,
        step=0.1,
        help="Higher = prioritize fewer workers. Lower = prioritize task completion."
    )

    priority_weight = st.slider(
        "High Priority Task Preference",
        min_value=0.0,
        max_value=1.0,
        value=0.5,
        step=0.1,
        help="Higher = focus on high-priority tasks first"
    )

    worker_score_weight = st.slider(
        "Prefer High-Score Workers",
        min_value=0.0,
        max_value=1.0,
        value=0.5,
        step=0.1,
        help="Higher = assign tasks to workers with higher scores"
    )

    st.markdown("---")

    # Run Optimization Button
    run_optimization = st.button(
        "⚡ Run Optimization",
        use_container_width=True,
        type="primary"
    )

    st.markdown("---")

    # Data Management
    st.markdown("#### 🔧 Data Management")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Reset", use_container_width=True, help="Reset to dummy data"):
            reset_data_from_files()
            st.session_state.optimization_results = None
            st.session_state.editing_worker = None
            st.rerun()
    with col2:
        if st.button("🗑️ Clear", use_container_width=True, help="Clear all data"):
            clear_all_data()
            st.session_state.optimization_results = None
            st.session_state.editing_worker = None
            st.rerun()


# --- Handle Optimization Run ---
if run_optimization:
    tasks = get_tasks()
    workers = get_workers()

    if not tasks:
        st.sidebar.error("No tasks defined!")
    elif not workers:
        st.sidebar.error("No workers defined!")
    else:
        with st.spinner("Optimizing..."):
            results = solve_task_allocation(tasks, workers)
            st.session_state.optimization_results = results
        if results:
            st.sidebar.success("Optimization complete!")
        else:
            st.sidebar.error("No feasible solution found")


# --- Main Title ---
st.markdown(f"<h1 style='color: {get_primary_color()};'>⚙️ Brewery Task Allocation Optimizer</h1>", unsafe_allow_html=True)
st.markdown(f"*Scenario: **{scenario}** | Demonstrating linear optimization for brewery workforce planning*")
st.markdown("---")

# --- Main Tabs ---
tab1, tab2, tab3 = st.tabs(["📊 Dashboard & Constraints", "📅 The Schedule", "👥 Personnel & Skills"])


# === TAB 1: Dashboard & Constraints ===
with tab1:
    st.subheader("Operational Context")
    st.markdown("Visualize production line states and task backlog to understand weekly constraints.")

    col_gantt, col_backlog = st.columns([2, 1])

    with col_gantt:
        st.markdown("##### 🏭 Machine State Timeline")
        st.caption("Production line availability throughout the week")

        # Machine State Gantt Chart
        machine_data = generate_machine_state_data()

        if not machine_data.empty:
            fig_machine = px.timeline(
                machine_data,
                x_start="Start",
                x_end="End",
                y="Machine",
                color="State",
                color_discrete_map={
                    "Production": "#28a745",
                    "Cleaning": "#ffc107",
                    "Maintenance": "#dc3545",
                    "Idle": "#6c757d"
                },
                title=""
            )
            fig_machine.update_yaxes(autorange="reversed")
            fig_machine.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=10, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02)
            )
            st.plotly_chart(fig_machine, use_container_width=True)

            st.markdown("""
            **Legend:**
            🟢 Production (visual checks only) |
            🟡 Cleaning (cleaning tasks allowed) |
            🔴 Maintenance (repairs allowed) |
            ⚪ Idle
            """)

    with col_backlog:
        st.markdown("##### 📋 Task Backlog")
        st.caption("Workload distribution by required skills")

        tasks = get_tasks()
        if tasks:
            # Create skill demand chart
            skill_counts = {}
            for task in tasks:
                for skill in task.get('required_skills', []):
                    skill_counts[skill] = skill_counts.get(skill, 0) + 1

            if skill_counts:
                df_skills = pd.DataFrame({
                    "Skill": list(skill_counts.keys()),
                    "Demand": list(skill_counts.values())
                }).sort_values("Demand", ascending=True)

                fig_backlog = px.bar(
                    df_skills,
                    x="Demand",
                    y="Skill",
                    orientation='h',
                    color="Demand",
                    color_continuous_scale="Greens"
                )
                fig_backlog.update_layout(
                    height=300,
                    margin=dict(l=0, r=0, t=10, b=0),
                    showlegend=False,
                    coloraxis_showscale=False
                )
                st.plotly_chart(fig_backlog, use_container_width=True)
        else:
            st.info("No tasks defined yet.")

    st.markdown("---")

    # Current Tasks Table
    st.markdown("##### 📝 Current Task Inventory")

    col_tasks_table, col_add_task = st.columns([3, 1])

    with col_tasks_table:
        tasks = get_tasks()
        if tasks:
            df_tasks = pd.DataFrame(tasks)
            df_tasks['required_skills'] = df_tasks['required_skills'].apply(lambda x: ', '.join(x))
            df_tasks = df_tasks.rename(columns={
                'name': 'Task Name',
                'required_skills': 'Required Skills'
            })
            st.dataframe(df_tasks, use_container_width=True, hide_index=True)
        else:
            st.info("No tasks have been added yet.")

    with col_add_task:
        if st.button("➕ Add New Task", use_container_width=True):
            st.session_state.show_add_task_form = not st.session_state.show_add_task_form

        if st.session_state.show_add_task_form:
            with st.form("add_task_form", clear_on_submit=True):
                task_name = st.text_input("Task Name", placeholder="e.g., Fermentation Check")
                skills_input = st.text_area(
                    "Required Skills",
                    placeholder="Chemistry, Quality Control",
                    help="Comma-separated list"
                )

                if st.form_submit_button("Add Task", type="primary"):
                    if task_name and skills_input:
                        existing = [t['name'].lower() for t in get_tasks()]
                        if task_name.lower() in existing:
                            st.error("Task already exists!")
                        else:
                            skills = [s.strip().title() for s in skills_input.split(',') if s.strip()]
                            add_task(task_name, skills)
                            st.success(f"Added '{task_name}'")
                            st.session_state.show_add_task_form = False
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.error("Please fill all fields")


# === TAB 2: The Schedule (Output) ===
with tab2:
    st.subheader("Optimized Schedule")

    results = st.session_state.optimization_results
    tasks = get_tasks()
    workers = get_workers()

    if not results:
        st.info("👆 Click **'⚡ Run Optimization'** in the sidebar to generate the optimized schedule.")

        # Show placeholder visualization
        st.markdown("##### Preview: Schedule will appear here after optimization")

        placeholder_data = pd.DataFrame({
            "Task": ["Example Task 1", "Example Task 2"],
            "Person": ["Worker A", "Worker B"],
            "Machine": ["Line A", "Line B"],
            "Start": [datetime.now(), datetime.now() + timedelta(hours=2)],
            "End": [datetime.now() + timedelta(hours=2), datetime.now() + timedelta(hours=4)]
        })

        fig_placeholder = px.timeline(
            placeholder_data,
            x_start="Start",
            x_end="End",
            y="Machine",
            color="Person",
            text="Task",
            title="Sample Schedule Format"
        )
        fig_placeholder.update_yaxes(autorange="reversed")
        fig_placeholder.update_layout(height=250, margin=dict(l=0, r=0, t=40, b=0))
        fig_placeholder.update_traces(opacity=0.3)
        st.plotly_chart(fig_placeholder, use_container_width=True)

    else:
        # Optimization Summary Metrics
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)

        with col_m1:
            st.metric(
                "Workers Required",
                int(results['minimum_workers_count']),
                delta=f"-{len(workers) - int(results['minimum_workers_count'])} unused",
                delta_color="normal"
            )

        with col_m2:
            tasks_scheduled = sum(1 for w in results['assignments'].values() if w)
            st.metric("Tasks Scheduled", tasks_scheduled, delta=f"of {len(tasks)}")

        with col_m3:
            unscheduled = len(tasks) - tasks_scheduled
            st.metric("Unscheduled", unscheduled, delta="tasks" if unscheduled > 0 else None)

        with col_m4:
            efficiency = (tasks_scheduled / len(tasks) * 100) if tasks else 0
            st.metric("Efficiency", f"{efficiency:.0f}%")

        st.markdown("---")

        # Master Schedule Gantt Chart
        st.markdown("##### 📊 Master Schedule (Gantt Chart)")

        schedule_df = generate_schedule_data(results, tasks)

        if not schedule_df.empty:
            fig_schedule = px.timeline(
                schedule_df,
                x_start="Start",
                x_end="End",
                y="Machine",
                color="Person",
                hover_data=["Task", "Skills"],
                title=""
            )
            fig_schedule.update_yaxes(autorange="reversed")
            fig_schedule.update_layout(
                height=400,
                margin=dict(l=0, r=0, t=10, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02)
            )
            st.plotly_chart(fig_schedule, use_container_width=True)

            st.caption("💡 Hover over tasks to see details. Colors represent assigned workers.")

        # Unscheduled Tasks Alert
        unscheduled_tasks = [
            task for task in tasks
            if not results['assignments'].get(task['name'])
        ]

        if unscheduled_tasks:
            st.warning(f"⚠️ {len(unscheduled_tasks)} task(s) could not be scheduled")
            with st.expander("View unscheduled tasks"):
                for task in unscheduled_tasks:
                    st.write(f"- **{task['name']}**: requires {', '.join(task['required_skills'])}")

        st.markdown("---")

        # Detailed Assignments Table
        st.markdown("##### 📋 Detailed Task Assignments")

        assignments_data = []
        for task_name, assigned_workers in results['assignments'].items():
            task_info = next((t for t in tasks if t['name'] == task_name), None)
            assignments_data.append({
                "Task": task_name,
                "Required Skills": ', '.join(task_info['required_skills']) if task_info else "",
                "Assigned Workers": ', '.join(assigned_workers) if assigned_workers else "❌ Unassigned",
                "Status": "✅ Scheduled" if assigned_workers else "⚠️ Needs Attention"
            })

        st.dataframe(
            pd.DataFrame(assignments_data),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Status": st.column_config.TextColumn(width="small")
            }
        )


# === TAB 3: Personnel & Skills ===
with tab3:
    st.subheader("Staff Availability & Skills")

    workers = get_workers()
    results = st.session_state.optimization_results

    # Calculate utilization
    utilization = calculate_worker_utilization(results, workers)

    if workers:
        # Build personnel dataframe with icons
        personnel_data = []
        for worker in workers:
            worker_name = worker['name']
            personnel_data.append({
                "avatar": "https://img.icons8.com/color/48/worker-male.png",
                "name": worker_name,
                "role": "Brewery Technician",
                "skills": worker.get('available_skills', []),
                "score": worker.get('score', 5),
                "utilization": utilization.get(worker_name, 0.0),
                "status": "🟢 Active" if utilization.get(worker_name, 0) > 0 else "⚪ Available"
            })

        df_personnel = pd.DataFrame(personnel_data)

        st.dataframe(
            df_personnel,
            column_config={
                "avatar": st.column_config.ImageColumn("", width="small"),
                "name": st.column_config.TextColumn("Employee Name", width="medium"),
                "role": st.column_config.TextColumn("Role", width="medium"),
                "skills": st.column_config.ListColumn("Qualified Skills", width="large"),
                "score": st.column_config.NumberColumn(
                    "Score",
                    width="small",
                    format="%d ⭐"
                ),
                "utilization": st.column_config.ProgressColumn(
                    "Weekly Load",
                    format="%.0f%%",
                    min_value=0,
                    max_value=1,
                    help="Percentage of weekly capacity utilized"
                ),
                "status": st.column_config.TextColumn("Status", width="small")
            },
            hide_index=True,
            use_container_width=True
        )

        st.markdown("---")

        # Worker Management Section
        col_manage, col_form = st.columns([1, 2])

        with col_manage:
            st.markdown("##### 🔧 Manage Workers")

            if st.button("➕ Add New Worker", use_container_width=True):
                st.session_state.show_add_worker_form = True
                st.session_state.editing_worker = None

            st.markdown("---")
            st.markdown("**Quick Actions:**")

            worker_to_edit = st.selectbox(
                "Select worker to edit/delete",
                options=[""] + [w['name'] for w in workers],
                format_func=lambda x: "Choose worker..." if x == "" else x
            )

            if worker_to_edit:
                col_edit, col_delete = st.columns(2)
                with col_edit:
                    if st.button("✏️ Edit", use_container_width=True):
                        worker_data = next((w for w in workers if w['name'] == worker_to_edit), None)
                        if worker_data:
                            st.session_state.editing_worker = worker_data
                            st.session_state.show_add_worker_form = True
                            st.rerun()
                with col_delete:
                    if st.button("🗑️ Delete", use_container_width=True, type="secondary"):
                        delete_worker(worker_to_edit)
                        st.success(f"Deleted {worker_to_edit}")
                        time.sleep(1)
                        st.rerun()

        with col_form:
            if st.session_state.show_add_worker_form or st.session_state.editing_worker:
                # Get available skills from tasks
                tasks = get_tasks()
                all_skills = set()
                for task in tasks:
                    all_skills.update(task.get('required_skills', []))
                available_skills = sorted(list(all_skills))

                if not available_skills:
                    st.warning("Please add tasks first to define available skills.")
                else:
                    editing = st.session_state.editing_worker

                    st.markdown(f"##### {'✏️ Edit Worker' if editing else '➕ Add New Worker'}")

                    with st.form("worker_form", clear_on_submit=True):
                        default_name = editing['name'] if editing else ""
                        default_skills = editing.get('available_skills', []) if editing else []
                        default_score = editing.get('score', 5) if editing else 5

                        worker_name = st.text_input("Worker Name", value=default_name)
                        selected_skills = st.multiselect(
                            "Skills",
                            options=available_skills,
                            default=[s for s in default_skills if s in available_skills]
                        )
                        worker_score = st.slider("Worker Score", 0, 10, default_score)

                        col_submit, col_cancel = st.columns(2)
                        with col_submit:
                            submitted = st.form_submit_button(
                                "Update" if editing else "Add Worker",
                                type="primary",
                                use_container_width=True
                            )
                        with col_cancel:
                            cancelled = st.form_submit_button("Cancel", use_container_width=True)

                        if submitted:
                            if worker_name and selected_skills:
                                original_name = editing['name'] if editing else None
                                add_or_update_worker(
                                    worker_name,
                                    selected_skills,
                                    worker_score,
                                    original_name=original_name
                                )
                                st.success(f"{'Updated' if editing else 'Added'} {worker_name}")
                                st.session_state.editing_worker = None
                                st.session_state.show_add_worker_form = False
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Please fill all fields")

                        if cancelled:
                            st.session_state.editing_worker = None
                            st.session_state.show_add_worker_form = False
                            st.rerun()

    else:
        st.info("No workers have been added yet.")

        # Show add worker form if no workers
        tasks = get_tasks()
        all_skills = set()
        for task in tasks:
            all_skills.update(task.get('required_skills', []))
        available_skills = sorted(list(all_skills))

        if available_skills:
            st.markdown("##### ➕ Add Your First Worker")
            with st.form("first_worker_form"):
                worker_name = st.text_input("Worker Name", placeholder="e.g., John Smith")
                selected_skills = st.multiselect("Skills", options=available_skills)
                worker_score = st.slider("Worker Score", 0, 10, 5)

                if st.form_submit_button("Add Worker", type="primary"):
                    if worker_name and selected_skills:
                        add_or_update_worker(worker_name, selected_skills, worker_score)
                        st.success(f"Added {worker_name}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Please fill all fields")
        else:
            st.warning("Please add tasks first (in Dashboard tab) to define available skills for workers.")


# --- Footer ---
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888;'>"
    "🍺 Heineken Brewery Task Allocation Optimizer | "
    "Powered by Linear Programming"
    "</div>",
    unsafe_allow_html=True
)
