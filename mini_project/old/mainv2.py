import math
import random
from dataclasses import dataclass, field
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


TIME_STEP = 1.0
MONTE_CARLO_RUNS = 20
SCB_SAFETY_MARGIN = 1.60
SCB_RESERVE_FLOOR = 0.35


@dataclass(frozen=True)
class VmSpec:
    name: str
    family: str
    speed: float
    cost_per_hour: float
    interrupt_prob: float = 0.0
    burst_speed: float = 0.0
    baseline_speed: float = 0.0
    max_credits: float = 0.0
    initial_credits: float = 0.0
    credit_gain: float = 0.0
    credit_cost: float = 0.0


@dataclass(frozen=True)
class Scenario:
    name: str
    num_tasks: int
    work_low: int
    work_high: int
    deadline_factor: float
    deadline_jitter: int
    spot_risk_multiplier: float
    initial_credits: float
    description: str


@dataclass
class Task:
    task_id: int
    total_work: float
    deadline: float
    remaining_work: float
    completed: bool = False
    completion_time: float | None = None
    interrupted_count: int = 0
    origin: str = "spot"

    @property
    def slack(self) -> float:
        return self.deadline - self.remaining_work


@dataclass
class VmState:
    spec: VmSpec
    task: Task | None = None
    credits: float = 0.0
    active_time: float = 0.0
    mode_history: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.spec.family == "burst":
            self.credits = self.spec.initial_credits


SPOT_SPECS = [
    VmSpec(name="c5.large", family="spot", speed=1.00, cost_per_hour=0.034, interrupt_prob=0.09),
    VmSpec(name="c4.large", family="spot", speed=0.92, cost_per_hour=0.032, interrupt_prob=0.10),
    VmSpec(name="c5.xlarge", family="spot", speed=1.85, cost_per_hour=0.068, interrupt_prob=0.07),
]

BURST_SPEC = VmSpec(
    name="t3.large",
    family="burst",
    speed=1.0,
    cost_per_hour=0.083,
    burst_speed=1.80,
    baseline_speed=0.40,
    max_credits=144.0,
    initial_credits=180.0,
    credit_gain=1.2,
    credit_cost=4.2,
)

ON_DEMAND_SPEC = VmSpec(
    name="m5.xlarge",
    family="on_demand",
    speed=2.10,
    cost_per_hour=0.40,
)


SCENARIOS = [
    Scenario(
        name="Balanced",
        num_tasks=120,
        work_low=35,
        work_high=120,
        deadline_factor=1.0,
        deadline_jitter=35,
        spot_risk_multiplier=2.5,
        initial_credits=40.0,
        description="Moderate workload, moderate deadlines, moderate interruption pressure.",
    ),
    Scenario(
        name="Spot Volatility",
        num_tasks=120,
        work_low=35,
        work_high=120,
        deadline_factor=1.0,
        deadline_jitter=25,
        spot_risk_multiplier=2.5,
        initial_credits=40.0,
        description="Same workload but with much more aggressive spot interruptions.",
    ),
    Scenario(
        name="Credit Crunch",
        num_tasks=130,
        work_low=40,
        work_high=125,
        deadline_factor=1.0,
        deadline_jitter=25,
        spot_risk_multiplier=2.5,
        initial_credits=40.0,
        description="Burst VM starts with low credit reserve and must budget carefully.",
    ),
    Scenario(
        name="Tight Deadlines",
        num_tasks=110,
        work_low=45,
        work_high=135,
        deadline_factor=1.0,
        deadline_jitter=15,
        spot_risk_multiplier=2.5,
        initial_credits=40.0,
        description="Heavier tasks under tight deadlines where backup decisions matter.",
    ),
    Scenario(
        name="Extreme Stress",
        num_tasks=150,
        work_low=50,
        work_high=150,
        deadline_factor=0.95,
        deadline_jitter=10,
        spot_risk_multiplier=3.0,
        initial_credits=40.0,
        description="Extreme workload with high interruption and tight deadlines.",
    ),
]


def generate_tasks(scenario: Scenario, seed: int) -> list[Task]:
    rng = random.Random(seed)
    tasks: list[Task] = []
    for task_id in range(scenario.num_tasks):
        total_work = rng.randint(scenario.work_low, scenario.work_high)
        tasks.append(
            Task(
                task_id=task_id,
                total_work=float(total_work),
                deadline=0.0,
                remaining_work=float(total_work),
            )
        )
    aggregate_work = sum(task.total_work for task in tasks)
    aggregate_capacity = sum(spec.speed for spec in SPOT_SPECS) + BURST_SPEC.baseline_speed
    app_deadline = (aggregate_work / aggregate_capacity) * scenario.deadline_factor + scenario.deadline_jitter
    for task in tasks:
        if rng.random() < 0.35:
            task.deadline = float(app_deadline * rng.uniform(0.78, 0.94))
        else:
            task.deadline = float(app_deadline * rng.uniform(1.02, 1.24))
    return tasks


def clone_tasks(tasks: list[Task]) -> list[Task]:
    return [
        Task(
            task_id=task.task_id,
            total_work=task.total_work,
            deadline=task.deadline,
            remaining_work=task.total_work,
        )
        for task in tasks
    ]


def interruption_happens(vm_spec: VmSpec, time_now: int, seed: int, scenario: Scenario) -> bool:
    risk = min(0.95, vm_spec.interrupt_prob * scenario.spot_risk_multiplier)
    draw = random.Random(f"{seed}-{vm_spec.name}-{time_now}").random()
    return draw < risk


def sort_by_deadline(tasks: list[Task], time_now: float) -> None:
    tasks.sort(key=lambda task: (task.deadline - time_now, task.remaining_work, task.task_id))


def sort_by_slack(tasks: list[Task], time_now: float) -> None:
    tasks.sort(
        key=lambda task: (
            (task.deadline - time_now - task.remaining_work),
            task.deadline,
            task.task_id,
        )
    )


def remaining_credit_time(vm: VmState) -> float:
    if vm.spec.credit_cost <= 0:
        return math.inf
    return vm.credits / vm.spec.credit_cost


def finish_task(task: Task, time_now: float, metrics: dict[str, float]) -> None:
    if task.completed:
        return
    task.completed = True
    task.completion_time = time_now
    metrics["completed_tasks"] += 1
    if time_now > task.deadline:
        metrics["deadline_misses"] += 1


def use_burst_hads_policy(
    task: Task,
    time_now: float,
    burst_vm: VmState,
) -> tuple[str, float]:
    if burst_vm.credits >= burst_vm.spec.credit_cost:
        return "burst", burst_vm.spec.burst_speed

    slack = task.deadline - time_now - (task.remaining_work / burst_vm.spec.baseline_speed)
    if slack < 20:
        return "fallback", 0.0
    return "baseline", burst_vm.spec.baseline_speed


def compute_credit_budget(backlog: list[Task], time_now: float, burst_vm: VmState) -> float:
    if not backlog:
        return 0.0

    urgent_tasks = [
        task
        for task in backlog
        if (task.deadline - time_now) < 50
    ]
    projected_need = sum(
        min(task.remaining_work / burst_vm.spec.burst_speed, 15.0) * burst_vm.spec.credit_cost
        for task in urgent_tasks[:5]
    )
    reserve_floor = burst_vm.spec.max_credits * SCB_RESERVE_FLOOR
    return min(burst_vm.spec.max_credits, max(reserve_floor, projected_need * SCB_SAFETY_MARGIN))


def use_scb_policy(
    task: Task,
    backlog: list[Task],
    time_now: float,
    burst_vm: VmState,
) -> tuple[str, float]:
    deadline_slack = task.deadline - time_now
    burst_finish_time = task.remaining_work / burst_vm.spec.burst_speed
    baseline_finish_time = task.remaining_work / burst_vm.spec.baseline_speed
    risk_factor = 1 + (len(backlog) * 0.15)

    reserve_target = compute_credit_budget(backlog, time_now, burst_vm)

    if deadline_slack <= burst_finish_time * risk_factor:
        if burst_vm.credits >= burst_vm.spec.credit_cost:
            return "burst", burst_vm.spec.burst_speed
        return "fallback", 0.0

    if deadline_slack <= baseline_finish_time * risk_factor:
        if burst_vm.credits >= burst_vm.spec.credit_cost:
            return "burst", burst_vm.spec.burst_speed
        return "fallback", 0.0

    if burst_vm.credits > reserve_target:
        return "burst", burst_vm.spec.burst_speed

    return "baseline", burst_vm.spec.baseline_speed


def assign_tasks(
    policy_name: str,
    spot_vms: list[VmState],
    burst_vm: VmState,
    ondemand_vm: VmState,
    pending_tasks: list[Task],
    recovery_tasks: list[Task],
    time_now: float,
) -> None:
    if policy_name == "SCB Burst HADS":
        sort_by_slack(pending_tasks, time_now)
        sort_by_slack(recovery_tasks, time_now)
    else:
        sort_by_deadline(pending_tasks, time_now)
        sort_by_deadline(recovery_tasks, time_now)

    if policy_name == "SCB Burst HADS" and ondemand_vm.task is None and recovery_tasks:
        reserve_target = compute_credit_budget(recovery_tasks, time_now, burst_vm)
        urgent_task = recovery_tasks[0]
        baseline_slack = urgent_task.deadline - time_now - (urgent_task.remaining_work / burst_vm.spec.baseline_speed)
        burst_slack = urgent_task.deadline - time_now - (urgent_task.remaining_work / burst_vm.spec.burst_speed)
        if baseline_slack < 30 and (burst_vm.credits < reserve_target or burst_slack < 10 or len(recovery_tasks) > 2):
            ondemand_vm.task = recovery_tasks.pop(0)
            ondemand_vm.task.origin = "on_demand"

    if policy_name == "SCB Burst HADS":
        if recovery_tasks:
            task = recovery_tasks[0]
            deadline_slack = task.deadline - time_now

            if deadline_slack < 40 and ondemand_vm.task is None:
                backup_task = Task(
                    task_id=task.task_id,
                    total_work=task.total_work,
                    deadline=task.deadline,
                    remaining_work=task.remaining_work,
                )
                ondemand_vm.task = backup_task
                ondemand_vm.task.origin = "on_demand_backup"

    if burst_vm.task is None and recovery_tasks:
        if policy_name == "SCB Burst HADS":
            recovery_tasks.sort(
                key=lambda task: (task.deadline - time_now) / max(task.remaining_work, 1)
            )
            burst_vm.task = recovery_tasks.pop(0)
            burst_vm.task.origin = "burst"
        else:
            burst_vm.task = recovery_tasks.pop(0)
            burst_vm.task.origin = "burst"

    if ondemand_vm.task is None and recovery_tasks:
        ondemand_vm.task = recovery_tasks.pop(0)
        ondemand_vm.task.origin = "on_demand"

    for vm in sorted(spot_vms, key=lambda item: item.spec.speed, reverse=True):
        if vm.task is None and pending_tasks:
            vm.task = pending_tasks.pop(0)
            vm.task.origin = "spot"


def run_simulation(policy_name: str, scenario: Scenario, tasks: list[Task], seed: int) -> dict[str, float | list[float]]:
    spot_vms = [VmState(spec=spec) for spec in SPOT_SPECS]
    burst_vm = VmState(spec=VmSpec(**{**BURST_SPEC.__dict__, "initial_credits": scenario.initial_credits}))
    ondemand_vm = VmState(spec=ON_DEMAND_SPEC)

    pending_tasks = clone_tasks(tasks)
    recovery_tasks: list[Task] = []
    time_now = 0
    max_deadline = max(task.deadline for task in pending_tasks)
    hard_stop = int(max_deadline * 3)

    metrics: dict[str, float | list[float]] = {
        "completed_tasks": 0.0,
        "deadline_misses": 0.0,
        "interruptions": 0.0,
        "fallback_uses": 0.0,
        "cost": 0.0,
        "spot_cost": 0.0,
        "burst_cost": 0.0,
        "ondemand_cost": 0.0,
        "credits_trace": [],
        "ondemand_trace": [],
        "recovery_trace": [],
        "avg_recovery_queue": [],
    }

    def clear_duplicate_task(task_id: int) -> None:
        for vm in [burst_vm, ondemand_vm]:
            if vm.task is not None and vm.task.task_id == task_id:
                vm.task = None

    while time_now < hard_stop:
        completed_tasks = int(metrics["completed_tasks"])
        if completed_tasks == len(tasks):
            break

        assign_tasks(policy_name, spot_vms, burst_vm, ondemand_vm, pending_tasks, recovery_tasks, time_now)

        for vm in spot_vms:
            if vm.task is None:
                continue
            if interruption_happens(vm.spec, time_now, seed, scenario):
                vm.task.interrupted_count += 1
                recovery_tasks.append(vm.task)
                vm.task.origin = "recovery"
                vm.task = None
                metrics["interruptions"] += 1

        for vm in spot_vms:
            if vm.task is None:
                continue
            vm.task.remaining_work -= vm.spec.speed * TIME_STEP
            vm.active_time += TIME_STEP
            vm.mode_history.append("spot")
            metrics["spot_cost"] += vm.spec.cost_per_hour / 3600.0
            if vm.task.remaining_work <= 0:
                finish_task(vm.task, time_now + TIME_STEP, metrics)
                vm.task = None

        if burst_vm.task is not None:
            backlog_snapshot = recovery_tasks + ([burst_vm.task] if burst_vm.task else [])
            if policy_name == "Burst HADS":
                mode, rate = use_burst_hads_policy(burst_vm.task, time_now, burst_vm)
            else:
                mode, rate = use_scb_policy(burst_vm.task, backlog_snapshot, time_now, burst_vm)

            if mode == "fallback":
                if ondemand_vm.task is None:
                    ondemand_vm.task = burst_vm.task
                    ondemand_vm.task.origin = "on_demand"
                    burst_vm.task = None
                    metrics["fallback_uses"] += 1
                else:
                    burst_vm.task.remaining_work -= burst_vm.spec.baseline_speed * TIME_STEP
                    burst_vm.credits = min(
                        burst_vm.spec.max_credits,
                        burst_vm.credits + burst_vm.spec.credit_gain * TIME_STEP,
                    )
                    burst_vm.active_time += TIME_STEP
                    burst_vm.mode_history.append("baseline")
                    metrics["burst_cost"] += burst_vm.spec.cost_per_hour / 3600.0
                    if burst_vm.task.remaining_work <= 0:
                        finished_task = burst_vm.task
                        finish_task(finished_task, time_now + TIME_STEP, metrics)
                        clear_duplicate_task(finished_task.task_id)
                        burst_vm.task = None
            else:
                burst_vm.task.remaining_work -= rate * TIME_STEP
                if mode == "burst":
                    burst_vm.credits = max(0.0, burst_vm.credits - burst_vm.spec.credit_cost * TIME_STEP)
                else:
                    burst_vm.credits = min(
                        burst_vm.spec.max_credits,
                        burst_vm.credits + burst_vm.spec.credit_gain * TIME_STEP,
                    )
                burst_vm.active_time += TIME_STEP
                burst_vm.mode_history.append(mode)
                metrics["burst_cost"] += burst_vm.spec.cost_per_hour / 3600.0
                if burst_vm.task.remaining_work <= 0:
                    finished_task = burst_vm.task
                    finish_task(finished_task, time_now + TIME_STEP, metrics)
                    clear_duplicate_task(finished_task.task_id)
                    burst_vm.task = None

        if ondemand_vm.task is not None:
            ondemand_vm.task.remaining_work -= ondemand_vm.spec.speed * TIME_STEP
            ondemand_vm.active_time += TIME_STEP
            ondemand_vm.mode_history.append("on_demand")
            metrics["ondemand_cost"] += ondemand_vm.spec.cost_per_hour / 3600.0
            if ondemand_vm.task.remaining_work <= 0:
                finished_task = ondemand_vm.task
                finish_task(finished_task, time_now + TIME_STEP, metrics)
                clear_duplicate_task(finished_task.task_id)
                ondemand_vm.task = None

        metrics["credits_trace"].append(burst_vm.credits)
        metrics["ondemand_trace"].append(1 if ondemand_vm.task else 0)
        metrics["recovery_trace"].append(len(recovery_tasks))
        metrics["avg_recovery_queue"].append(len(recovery_tasks))
        time_now += 1

    missed_unfinished = 0
    for collection in [pending_tasks, recovery_tasks]:
        for task in collection:
            if not task.completed:
                missed_unfinished += 1
    for vm in [*spot_vms, burst_vm, ondemand_vm]:
        if vm.task is not None and not vm.task.completed:
            missed_unfinished += 1

    metrics["deadline_misses"] += missed_unfinished
    metrics["cost"] = metrics["spot_cost"] + metrics["burst_cost"] + metrics["ondemand_cost"]
    metrics["makespan"] = float(time_now)
    metrics["completion_rate"] = metrics["completed_tasks"] / len(tasks)
    metrics["avg_recovery_queue"] = mean(metrics["avg_recovery_queue"]) if metrics["avg_recovery_queue"] else 0.0
    return metrics


def aggregate_results(results: list[dict[str, float | list[float]]]) -> dict[str, float]:
    keys = [
        "makespan",
        "cost",
        "spot_cost",
        "burst_cost",
        "ondemand_cost",
        "deadline_misses",
        "interruptions",
        "fallback_uses",
        "completion_rate",
        "avg_recovery_queue",
    ]
    summary = {key: mean(float(run[key]) for run in results) for key in keys}
    summary["credits_trace"] = [
        mean(run["credits_trace"][idx] if idx < len(run["credits_trace"]) else run["credits_trace"][-1] for run in results)
        for idx in range(max(len(run["credits_trace"]) for run in results))
    ]
    return summary


def run_experiments() -> dict[str, dict[str, dict[str, float]]]:
    all_results: dict[str, dict[str, dict[str, float]]] = {}
    for scenario in SCENARIOS:
        base_runs: list[dict[str, float | list[float]]] = []
        scb_runs: list[dict[str, float | list[float]]] = []
        for seed in range(MONTE_CARLO_RUNS):
            task_set = generate_tasks(scenario, seed + 101)
            base_runs.append(run_simulation("Burst HADS", scenario, task_set, seed + 700))
            scb_runs.append(run_simulation("SCB Burst HADS", scenario, task_set, seed + 700))

        all_results[scenario.name] = {
            "Burst HADS": aggregate_results(base_runs),
            "SCB Burst HADS": aggregate_results(scb_runs),
        }
    return all_results


def print_results(results: dict[str, dict[str, dict[str, float]]]) -> None:
    print("\nMulti-VM Burst HADS vs SCB Burst HADS")
    print("Spot fleet: c5.large + c4.large + c5.xlarge | Burstable: t3.large | Backup: m5.xlarge\n")

    for scenario in SCENARIOS:
        base = results[scenario.name]["Burst HADS"]
        scb = results[scenario.name]["SCB Burst HADS"]
        cost_delta = ((base["cost"] - scb["cost"]) / base["cost"] * 100.0) if base["cost"] else 0.0
        miss_delta = scb["deadline_misses"] - base["deadline_misses"]
        fallback_delta = base["fallback_uses"] - scb["fallback_uses"]

        print(f"Scenario: {scenario.name}")
        print(f"  {scenario.description}")
        print(
            "  Burst HADS     -> "
            f"makespan={base['makespan']:.1f}, cost=${base['cost']:.4f}, "
            f"misses={base['deadline_misses']:.2f}, on-demand uses={base['fallback_uses']:.2f}"
        )
        print(
            "  SCB Burst HADS -> "
            f"makespan={scb['makespan']:.1f}, cost=${scb['cost']:.4f}, "
            f"misses={scb['deadline_misses']:.2f}, on-demand uses={scb['fallback_uses']:.2f}"
        )
        print(
            "  Improvement    -> "
            f"cost={cost_delta:.2f}% lower, "
            f"deadline misses {'reduced' if miss_delta < 0 else 'increased'} by {abs(miss_delta):.2f}, "
            f"on-demand uses reduced by {fallback_delta:.2f}\n"
        )


def plot_results(results: dict[str, dict[str, dict[str, float]]]) -> None:
    scenario_names = [scenario.name for scenario in SCENARIOS]
    x_axis = list(range(len(scenario_names)))
    width = 0.35

    base_cost = [results[name]["Burst HADS"]["cost"] for name in scenario_names]
    scb_cost = [results[name]["SCB Burst HADS"]["cost"] for name in scenario_names]
    base_miss = [results[name]["Burst HADS"]["deadline_misses"] for name in scenario_names]
    scb_miss = [results[name]["SCB Burst HADS"]["deadline_misses"] for name in scenario_names]
    base_fallback = [results[name]["Burst HADS"]["fallback_uses"] for name in scenario_names]
    scb_fallback = [results[name]["SCB Burst HADS"]["fallback_uses"] for name in scenario_names]
    base_recovery = [results[name]["Burst HADS"]["avg_recovery_queue"] for name in scenario_names]
    scb_recovery = [results[name]["SCB Burst HADS"]["avg_recovery_queue"] for name in scenario_names]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    axes[0, 0].bar([x - width / 2 for x in x_axis], base_cost, width=width, label="Burst HADS")
    axes[0, 0].bar([x + width / 2 for x in x_axis], scb_cost, width=width, label="SCB Burst HADS")
    axes[0, 0].set_title("Total Cost")
    axes[0, 0].set_xticks(x_axis, scenario_names, rotation=15)
    axes[0, 0].set_ylabel("USD")
    axes[0, 0].legend()

    axes[0, 1].bar([x - width / 2 for x in x_axis], base_miss, width=width, label="Burst HADS")
    axes[0, 1].bar([x + width / 2 for x in x_axis], scb_miss, width=width, label="SCB Burst HADS")
    axes[0, 1].set_title("Deadline Misses")
    axes[0, 1].set_xticks(x_axis, scenario_names, rotation=15)
    axes[0, 1].legend()

    axes[1, 0].bar([x - width / 2 for x in x_axis], base_fallback, width=width, label="Burst HADS")
    axes[1, 0].bar([x + width / 2 for x in x_axis], scb_fallback, width=width, label="SCB Burst HADS")
    axes[1, 0].set_title("On-Demand Fallback Count")
    axes[1, 0].set_xticks(x_axis, scenario_names, rotation=15)
    axes[1, 0].legend()

    balanced_base = results["Balanced"]["Burst HADS"]["credits_trace"]
    balanced_scb = results["Balanced"]["SCB Burst HADS"]["credits_trace"]
    axes[1, 1].plot(balanced_base, label="Burst HADS")
    axes[1, 1].plot(balanced_scb, label="SCB Burst HADS")
    axes[1, 1].set_title("t3.large Credit Trend (Balanced Scenario)")
    axes[1, 1].set_xlabel("Time Step")
    axes[1, 1].set_ylabel("Credits")
    axes[1, 1].legend()

    plt.tight_layout()
    plt.savefig("mini_project\\burst_hads_comparison.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    plt.figure()
    plt.bar(scenario_names, base_recovery, label="Burst HADS")
    plt.bar(scenario_names, scb_recovery, bottom=base_recovery, label="SCB Burst HADS")
    plt.title("Recovery Queue Pressure")
    plt.legend()
    plt.savefig("mini_project\\recovery_pressure.png")
    plt.close()


if __name__ == "__main__":
    results = run_experiments()
    print_results(results)
    plot_results(results)
