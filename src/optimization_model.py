import pyomo.environ as pyo
from pyomo.opt import SolverFactory
from typing import List, Dict, Tuple, Optional

def solve_task_allocation(tasks: List[Dict], workers: List[Dict]) -> Optional[Dict]:
    model = pyo.ConcreteModel()

    # --- Sets ---
    model.TASKS = pyo.Set(initialize=[task["name"] for task in tasks])
    model.WORKERS = pyo.Set(initialize=[worker["name"] for worker in workers])

    # Combined set of all unique skills
    all_skills = set()
    for task in tasks:
        all_skills.update(task["required_skills"])
    model.SKILLS = pyo.Set(initialize=list(all_skills))

    # --- Parameters ---
    task_requires_skill_data = {}
    for task in tasks:
        for skill in model.SKILLS:
            task_requires_skill_data[(task["name"], skill)] = 1 if skill in task["required_skills"] else 0
    model.TaskRequiresSkill = pyo.Param(model.TASKS, model.SKILLS, initialize=task_requires_skill_data)

    worker_has_skill_data = {}
    for worker in workers:
        for skill in model.SKILLS:
            worker_has_skill_data[(worker["name"], skill)] = 1 if skill in worker["available_skills"] else 0
    model.WorkerHasSkill = pyo.Param(model.WORKERS, model.SKILLS, initialize=worker_has_skill_data)

    # Worker Score Parameter
    worker_score_data = {worker["name"]: worker.get("score", 5) for worker in workers} # Default to 5 if score is missing
    model.WorkerScore = pyo.Param(model.WORKERS, initialize=worker_score_data, within=pyo.Integers)


    # --- Decision Variables ---
    model.x = pyo.Var(model.TASKS, model.WORKERS, within=pyo.Binary)
    model.y = pyo.Var(model.WORKERS, within=pyo.Binary)

    # --- Objective Function ---
    # The small coefficient (e.g., 0.01)
    # ensures that minimizing the *number* of workers is the primary goal.
    model.objective = pyo.Objective(
        expr=sum(model.y[w] for w in model.WORKERS) - 0.01 * sum(model.y[w] * model.WorkerScore[w] for w in model.WORKERS),
        sense=pyo.minimize
    )

    # --- Constraints ---

    # 1. Each Worker Assigned to At Most One Task
    def one_task_per_worker_rule(model, w):
        return sum(model.x[t, w] for t in model.TASKS) <= 1
    model.OneTaskPerWorker = pyo.Constraint(model.WORKERS, rule=one_task_per_worker_rule)

    # 2. Task Skill Coverage
    def task_skill_coverage_rule(model, t, s):
        if model.TaskRequiresSkill[t, s] == 1:
            # At least one worker assigned to task t must have skill s
            return sum(model.x[t, w] * model.WorkerHasSkill[w, s] for w in model.WORKERS) >= 1
        return pyo.Constraint.Feasible # If skill not required, constraint is trivially satisfied
    model.TaskSkillCoverage = pyo.Constraint(model.TASKS, model.SKILLS, rule=task_skill_coverage_rule)


    # 3. Worker Utilization Link
    def worker_used_link_rule(model, t, w):
        # If worker w is assigned to task t (x[t,w]=1), then worker w must be marked as used (y[w]=1)
        return model.x[t, w] <= model.y[w]
    model.WorkerUsedLink = pyo.Constraint(model.TASKS, model.WORKERS, rule=worker_used_link_rule)


    # --- Solve the model ---
    solver = SolverFactory('appsi_highs')

    try:
        results = solver.solve(model, tee=False)

        if (results.solver.status == pyo.SolverStatus.ok and
                results.solver.termination_condition == pyo.TerminationCondition.optimal):

            allocation_results = {
                "objective_value": pyo.value(model.objective), # This will now be a float due to the score
                "assignments": {},
                "workers_used": []
            }

            # Collect all assignments where x_tw is 1
            for t in model.TASKS:
                assigned_workers_for_task = []
                for w in model.WORKERS:
                    if pyo.value(model.x[t, w]) > 0.5:
                        assigned_workers_for_task.append(w)
                allocation_results["assignments"][t] = assigned_workers_for_task

            for w in model.WORKERS:
                if pyo.value(model.y[w]) > 0.5:
                    allocation_results["workers_used"].append(w)

            # The objective value will be a float, so we extract the integer part for worker count
            allocation_results["minimum_workers_count"] = int(pyo.value(sum(model.y[w] for w in model.WORKERS)))

            return allocation_results
        else:
            print(f"Solver did not find an optimal solution. Status: {results.solver.status}, Termination Condition: {results.solver.termination_condition}")
            return None
    except Exception as e:
        print(f"An error occurred during solving: {e}")
        return None

# Example usage (for testing optimization_model.py independently)
if __name__ == "__main__":
    sample_tasks = [
        {"name": "Task A (S1, S2)", "required_skills": ["S1", "S2"]},
        {"name": "Task B (S2, S3)", "required_skills": ["S2", "S3"]},
        {"name": "Task C (S1)", "required_skills": ["S1"]},
    ]

    sample_workers = [
        {"name": "Alice", "available_skills": ["S1"], "score": 8},
        {"name": "Bob", "available_skills": ["S2"], "score": 6},
        {"name": "Charlie", "available_skills": ["S3"], "score": 4},
        {"name": "David", "available_skills": ["S1", "S2", "S3"], "score": 9},
    ]

    print("Running optimization with sample data (one worker per task, multiple per task completion)...")
    results = solve_task_allocation(sample_tasks, sample_workers)

    if results:
        print("\nOptimization Results:")
        print(f"Overall Objective Value (including score preference): {results['objective_value']:.2f}")
        print(f"Minimum Workers Used: {results['minimum_workers_count']}") # Display integer count
        print("Task Assignments (Team Based):")
        for task, workers_list in results["assignments"].items():
            print(f"  - {task}: {', '.join(workers_list)}")
        print(f"Workers Utilized: {', '.join(results['workers_used'])}")
    else:
        print("Failed to find an optimal solution.")

    print("\n--- Testing an infeasible case ---")
    infeasible_tasks = [
        {"name": "Task X", "required_skills": ["NonExistentSkill"]},
    ]
    infeasible_workers = [
        {"name": "Worker Y", "available_skills": ["SomeSkill"]},
    ]
    infeasible_results = solve_task_allocation(infeasible_tasks, infeasible_workers)
    if not infeasible_results:
        print("\nCorrectly identified infeasible case (Task X requires skill not available).")