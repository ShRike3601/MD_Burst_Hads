from models.task import Task
from models.job import Job
from models.vm import VM

from simulation.event_engine import EventEngine
from simulation.execution_engine import start_execution

from scheduler.md_burst_hads import MDBurstHADS
from scheduler.burst_hads import BurstHADS

from metrics.metrics import Metrics

def run_simulation(scheduler_class):

    # create tasks
    tasks = []

    # create 10 tasks with varied runtime
    for i in range(10):
        runtime = (i % 5 + 1) * 2   # 2,4,6,8,10 pattern
        tasks.append(Task(i, runtime=runtime, job_id=0))

    job = Job(0, tasks, deadline=25)

    # create VMs
    vm1 = VM(0, "ondemand", speed=1, cost_rate=1)
    vm2 = VM(1, "ondemand", speed=2, cost_rate=1)

    # scheduler
    scheduler = scheduler_class([job], [vm1, vm2])
    scheduler.schedule(0)

    # 🔥 ensure tasks are in VM queues before execution
    for vm in [vm1, vm2]:
        vm.tasks = list(vm.tasks)

    # engine
    engine = EventEngine(scheduler)
    scheduler.event_engine = engine

    # execution
    start_execution([vm1, vm2], 0, engine)

    from simulation.events import HibernationEvent
    event = HibernationEvent(3, vm1, scheduler)
    engine.add_event(event)

    # run
    engine.run()

    # metrics
    metrics = Metrics([job], [vm1, vm2])

    return metrics

md_metrics = run_simulation(MDBurstHADS)
baseline_metrics = run_simulation(BurstHADS)

print("MD-BurstHADS Makespan:", md_metrics.makespan())
print("Baseline Makespan:", baseline_metrics.makespan())

print("MD Deadline Misses:", md_metrics.deadline_misses())
print("Baseline Deadline Misses:", baseline_metrics.deadline_misses())

print("MD Cost:", md_metrics.total_cost())
print("Baseline Cost:", baseline_metrics.total_cost())