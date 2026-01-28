import pyomo.environ as pyo
from pyomo.opt import SolverFactory
from typing import List, Dict, Tuple, Optional

# Scenario presets for different operational modes
SCENARIO_PRESETS = {
    "Standard Week": {
        "coverage_penalty": 100,
        "worker_weight": 1.0,
        "description": "Balanced optimization"
    },
    "High Production": {
        "coverage_penalty": 1000,
        "worker_weight": 0.5,
        "description": "Must complete all tasks, workers secondary"
    },
    "Maintenance Week": {
        "coverage_penalty": 50,
        "worker_weight": 1.5,
        "description": "Minimize crew size, some tasks can wait"
    },
    "Shutdown Period": {
        "coverage_penalty": 10,
        "worker_weight": 2.0,
        "description": "Skeleton crew, only critical tasks"
    }
}


def get_scenario_params(scenario: str) -> Dict:
    """Get optimization parameters for a given scenario."""
    return SCENARIO_PRESETS.get(scenario, SCENARIO_PRESETS["Standard Week"])


def solve_task_allocation(
    tasks: List[Dict],
    workers: List[Dict],
    scenario: str = "Standard Week",
    minimize_workers_weight: float = 0.7,
    priority_weight: float = 0.5,
    worker_score_weight: float = 0.5
) -> Optional[Dict]:
    """
    Solve the task allocation optimization problem.

    Args:
        tasks: List of task dicts with 'name', 'required_skills', and 'priority'
        workers: List of worker dicts with 'name', 'available_skills', and 'score'
        scenario: Operational scenario (affects base parameters)
        minimize_workers_weight: 0-1, higher = prioritize fewer workers
        priority_weight: 0-1, higher = focus on high-priority tasks
        worker_score_weight: 0-1, higher = prefer high-score workers

    Returns:
        Dict with optimization results or None if infeasible
    """
    model = pyo.ConcreteModel()

    # Get scenario-based parameters
    scenario_params = get_scenario_params(scenario)
    base_coverage_penalty = scenario_params["coverage_penalty"]
    base_worker_weight = scenario_params["worker_weight"]

    # --- Sets ---
    model.TASKS = pyo.Set(initialize=[task["name"] for task in tasks])
    model.WORKERS = pyo.Set(initialize=[worker["name"] for worker in workers])

    # Combined set of all unique skills
    all_skills = set()
    for task in tasks:
        all_skills.update(task["required_skills"])
    model.SKILLS = pyo.Set(initialize=list(all_skills))

    # --- Parameters ---

    # Task requires skill matrix
    task_requires_skill_data = {}
    for task in tasks:
        for skill in model.SKILLS:
            task_requires_skill_data[(task["name"], skill)] = 1 if skill in task["required_skills"] else 0
    model.TaskRequiresSkill = pyo.Param(model.TASKS, model.SKILLS, initialize=task_requires_skill_data)

    # Worker has skill matrix
    worker_has_skill_data = {}
    for worker in workers:
        for skill in model.SKILLS:
            worker_has_skill_data[(worker["name"], skill)] = 1 if skill in worker["available_skills"] else 0
    model.WorkerHasSkill = pyo.Param(model.WORKERS, model.SKILLS, initialize=worker_has_skill_data)

    # Worker Score Parameter
    worker_score_data = {worker["name"]: worker.get("score", 5) for worker in workers}
    model.WorkerScore = pyo.Param(model.WORKERS, initialize=worker_score_data)

    # Task Priority Parameter (1-10 scale, higher = more important)
    task_priority_data = {task["name"]: task.get("priority", 5) for task in tasks}
    model.TaskPriority = pyo.Param(model.TASKS, initialize=task_priority_data)

    # --- Decision Variables ---

    # x[t,w] = 1 if worker w is assigned to task t
    model.x = pyo.Var(model.TASKS, model.WORKERS, within=pyo.Binary)

    # y[w] = 1 if worker w is used (assigned to any task)
    model.y = pyo.Var(model.WORKERS, within=pyo.Binary)

    # uncovered[t,s] = slack variable for uncovered skill s in task t
    model.uncovered = pyo.Var(model.TASKS, model.SKILLS, within=pyo.NonNegativeReals)

    # task_completed[t] = 1 if all skills for task t are covered
    model.task_completed = pyo.Var(model.TASKS, within=pyo.Binary)

    # --- Objective Function ---
    # Multi-objective optimization with configurable weights

    # Effective weights based on sliders and scenario
    eff_worker_weight = base_worker_weight * minimize_workers_weight
    eff_coverage_penalty = base_coverage_penalty * (1 + priority_weight)
    eff_score_weight = 0.01 * worker_score_weight  # Scale down to avoid dominating

    model.objective = pyo.Objective(
        expr=(
            # Term 1: Minimize number of workers used
            eff_worker_weight * sum(model.y[w] for w in model.WORKERS)

            # Term 2: Penalize uncovered skills (weighted by task priority)
            + eff_coverage_penalty * sum(
                model.TaskPriority[t] * model.uncovered[t, s]
                for t in model.TASKS
                for s in model.SKILLS
                if model.TaskRequiresSkill[t, s] == 1
            )

            # Term 3: Reward completing high-priority tasks
            - priority_weight * 10 * sum(
                model.TaskPriority[t] * model.task_completed[t]
                for t in model.TASKS
            )

            # Term 4: Prefer high-score workers (negative = reward)
            - eff_score_weight * sum(
                model.y[w] * model.WorkerScore[w]
                for w in model.WORKERS
            )
        ),
        sense=pyo.minimize
    )

    # --- Constraints ---

    # 1. Each Worker Assigned to At Most One Task
    def one_task_per_worker_rule(model, w):
        return sum(model.x[t, w] for t in model.TASKS) <= 1
    model.OneTaskPerWorker = pyo.Constraint(model.WORKERS, rule=one_task_per_worker_rule)

    # 2. Task Skill Coverage (Soft Constraint with Slack)
    def task_skill_coverage_rule(model, t, s):
        if model.TaskRequiresSkill[t, s] == 1:
            # At least one worker with skill s must be assigned, OR use slack
            return (
                sum(model.x[t, w] * model.WorkerHasSkill[w, s] for w in model.WORKERS)
                + model.uncovered[t, s] >= 1
            )
        return pyo.Constraint.Skip
    model.TaskSkillCoverage = pyo.Constraint(model.TASKS, model.SKILLS, rule=task_skill_coverage_rule)

    # 3. Worker Utilization Link
    def worker_used_link_rule(model, t, w):
        # If worker w is assigned to task t, then y[w] must be 1
        return model.x[t, w] <= model.y[w]
    model.WorkerUsedLink = pyo.Constraint(model.TASKS, model.WORKERS, rule=worker_used_link_rule)

    # 4. Task Completion Definition
    # A task is completed if all its required skills are covered (no slack used)
    def task_completion_rule(model, t):
        num_required_skills = sum(model.TaskRequiresSkill[t, s] for s in model.SKILLS)
        if num_required_skills == 0:
            return model.task_completed[t] == 1
        # Task is complete if total uncovered skills is 0
        # We use a big-M formulation: if any uncovered > 0, task_completed = 0
        return (
            sum(model.uncovered[t, s] for s in model.SKILLS if model.TaskRequiresSkill[t, s] == 1)
            <= num_required_skills * (1 - model.task_completed[t])
        )
    model.TaskCompletion = pyo.Constraint(model.TASKS, rule=task_completion_rule)

    # --- Solve the model ---
    solver = SolverFactory('appsi_highs')

    try:
        results = solver.solve(model, tee=False)

        if (results.solver.status == pyo.SolverStatus.ok and
                results.solver.termination_condition == pyo.TerminationCondition.optimal):

            allocation_results = {
                "objective_value": pyo.value(model.objective),
                "assignments": {},
                "workers_used": [],
                "tasks_completed": [],
                "tasks_partial": [],
                "uncovered_skills": {},
                "minimum_workers_count": 0,
                "scenario": scenario,
                "scenario_params": scenario_params
            }

            # Collect task assignments
            for t in model.TASKS:
                assigned_workers_for_task = []
                for w in model.WORKERS:
                    if pyo.value(model.x[t, w]) > 0.5:
                        assigned_workers_for_task.append(w)
                allocation_results["assignments"][t] = assigned_workers_for_task

            # Collect workers used
            for w in model.WORKERS:
                if pyo.value(model.y[w]) > 0.5:
                    allocation_results["workers_used"].append(w)

            # Collect task completion status
            for t in model.TASKS:
                if pyo.value(model.task_completed[t]) > 0.5:
                    allocation_results["tasks_completed"].append(t)
                else:
                    allocation_results["tasks_partial"].append(t)

                # Track uncovered skills per task
                uncovered_for_task = []
                for s in model.SKILLS:
                    if model.TaskRequiresSkill[t, s] == 1:
                        uncovered_val = pyo.value(model.uncovered[t, s])
                        if uncovered_val > 0.01:  # Threshold for numerical precision
                            uncovered_for_task.append(s)
                if uncovered_for_task:
                    allocation_results["uncovered_skills"][t] = uncovered_for_task

            allocation_results["minimum_workers_count"] = len(allocation_results["workers_used"])

            return allocation_results
        else:
            print(f"Solver did not find an optimal solution. Status: {results.solver.status}, "
                  f"Termination Condition: {results.solver.termination_condition}")
            return None
    except Exception as e:
        print(f"An error occurred during solving: {e}")
        return None


# Example usage (for testing optimization_model.py independently)
if __name__ == "__main__":
    sample_tasks = [
        {"name": "Task A (S1, S2)", "required_skills": ["S1", "S2"], "priority": 8},
        {"name": "Task B (S2, S3)", "required_skills": ["S2", "S3"], "priority": 5},
        {"name": "Task C (S1)", "required_skills": ["S1"], "priority": 10},
    ]

    sample_workers = [
        {"name": "Alice", "available_skills": ["S1"], "score": 8},
        {"name": "Bob", "available_skills": ["S2"], "score": 6},
        {"name": "Charlie", "available_skills": ["S3"], "score": 4},
        {"name": "David", "available_skills": ["S1", "S2", "S3"], "score": 9},
    ]

    print("=" * 60)
    print("Test 1: Standard Week scenario with all sliders at default")
    print("=" * 60)
    results = solve_task_allocation(
        sample_tasks,
        sample_workers,
        scenario="Standard Week",
        minimize_workers_weight=0.7,
        priority_weight=0.5,
        worker_score_weight=0.5
    )

    if results:
        print(f"\nScenario: {results['scenario']}")
        print(f"Objective Value: {results['objective_value']:.2f}")
        print(f"Workers Used: {results['minimum_workers_count']}")
        print(f"Tasks Completed: {len(results['tasks_completed'])}/{len(sample_tasks)}")
        print("\nAssignments:")
        for task, workers_list in results["assignments"].items():
            status = "✓" if task in results["tasks_completed"] else "⚠"
            print(f"  {status} {task}: {', '.join(workers_list) if workers_list else 'UNASSIGNED'}")
        if results["uncovered_skills"]:
            print("\nUncovered Skills:")
            for task, skills in results["uncovered_skills"].items():
                print(f"  {task}: {', '.join(skills)}")
    else:
        print("Failed to find a solution.")

    print("\n" + "=" * 60)
    print("Test 2: High Production scenario (must complete all tasks)")
    print("=" * 60)
    results2 = solve_task_allocation(
        sample_tasks,
        sample_workers,
        scenario="High Production",
        minimize_workers_weight=0.3,
        priority_weight=0.9,
        worker_score_weight=0.5
    )

    if results2:
        print(f"\nScenario: {results2['scenario']}")
        print(f"Workers Used: {results2['minimum_workers_count']}")
        print(f"Tasks Completed: {len(results2['tasks_completed'])}/{len(sample_tasks)}")

    print("\n" + "=" * 60)
    print("Test 3: Infeasible case - task requires unavailable skill")
    print("=" * 60)
    infeasible_tasks = [
        {"name": "Task X", "required_skills": ["NonExistentSkill"], "priority": 10},
    ]
    infeasible_workers = [
        {"name": "Worker Y", "available_skills": ["SomeSkill"], "score": 5},
    ]
    results3 = solve_task_allocation(infeasible_tasks, infeasible_workers)

    if results3:
        print(f"\nWith soft constraints, solver found a solution:")
        print(f"Tasks Completed: {len(results3['tasks_completed'])}")
        print(f"Partial Tasks: {results3['tasks_partial']}")
        print(f"Uncovered Skills: {results3['uncovered_skills']}")
    else:
        print("No solution found (hard failure).")
