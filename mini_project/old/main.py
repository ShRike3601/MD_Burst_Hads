import random
import matplotlib.pyplot as plt

# -----------------------------
# CONFIG
# -----------------------------
NUM_TASKS = 100
DEADLINE = 1000
TIME_STEP = 1

P_INTERRUPT = 0.1  # change this later

INITIAL_CREDITS = 100
MAX_CREDITS = 200

CREDIT_CONSUMPTION = 1
CREDIT_GAIN = 0.2

SCB_THRESHOLD = 0.5 # tweak this

# -----------------------------
# TASK CLASS
# -----------------------------
class Task:
    def __init__(self, id):
        self.id = id
        self.total_time = random.randint(100, 300)
        self.remaining = self.total_time
        self.completed = False


# -----------------------------
# VM CLASSES
# -----------------------------
class SpotVM:
    def __init__(self):
        self.task = None
        self.interrupted = False


class BurstVM:
    def __init__(self):
        self.task = None
        self.credits = INITIAL_CREDITS

# -----------------------------
# CPS CALCULATION
# -----------------------------
def compute_cps(task, time, credits):
    remaining_time = task.remaining
    slack = max(1, DEADLINE - time - remaining_time)

    urgency = remaining_time / slack
    risk = P_INTERRUPT
    credit_pressure = 1 - (credits / MAX_CREDITS)

    cps = urgency * risk * credit_pressure
    return cps

# -----------------------------
# SIMULATION
# -----------------------------
def run_simulation(use_scb=True):
    tasks = [Task(i) for i in range(NUM_TASKS)]

    spot = SpotVM()
    burst = BurstVM()

    time = 0
    completed_tasks = 0

    credits_over_time = []

    while time < DEADLINE and completed_tasks < NUM_TASKS:

        # Assign task if idle
        if spot.task is None:
            for t in tasks:
                if not t.completed:
                    spot.task = t
                    break

        # Random interruption
        if spot.task and random.random() < P_INTERRUPT:
            interrupted_task = spot.task
            spot.task = None

            # Move to burst VM
            if burst.task is None:
                burst.task = interrupted_task

        # Process Spot VM
        if spot.task:
            spot.task.remaining -= TIME_STEP
            if spot.task.remaining <= 0:
                spot.task.completed = True
                completed_tasks += 1
                spot.task = None

        # Process Burst VM
        if burst.task:
            if use_scb:
                cps = compute_cps(burst.task, time, burst.credits)
                use_burst = cps > SCB_THRESHOLD
            else:
                use_burst = True  # baseline greedy

            if use_burst and burst.credits > 0:
                # Burst mode
                burst.task.remaining -= 2 * TIME_STEP
                burst.credits -= CREDIT_CONSUMPTION
            else:
                # Baseline mode
                burst.task.remaining -= TIME_STEP
                burst.credits += CREDIT_GAIN
                burst.credits = min(MAX_CREDITS, burst.credits)

            if burst.task.remaining <= 0:
                burst.task.completed = True
                completed_tasks += 1
                burst.task = None

        credits_over_time.append(burst.credits)
        time += TIME_STEP

    makespan = time
    return makespan, credits_over_time


# -----------------------------
# RUN BOTH MODELS
# -----------------------------
baseline_makespan, baseline_credits = run_simulation(use_scb=False)
scb_makespan, scb_credits = run_simulation(use_scb=True)

print("Baseline Makespan:", baseline_makespan)
print("SCB Makespan:", scb_makespan)

# -----------------------------
# PLOT
# -----------------------------
plt.plot(baseline_credits, label="Baseline")
plt.plot(scb_credits, label="SCB")
plt.legend()
plt.title("Credit Usage Over Time")
plt.show()