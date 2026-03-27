from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import run_simulation
from scheduler.md_burst_hads import MDBurstHADS
from scheduler.burst_hads import BurstHADS

import matplotlib.pyplot as plt


task_sizes = [10, 20, 50, 100]
runs = 5
deadline_factors = [0.5, 1.0, 2.0]  # tight, normal, loose

for df in deadline_factors:
    print(f"\n--- Deadline Factor: {df} ---")

    results = {}

    for n in task_sizes:
        md_makespan = []
        base_makespan = []

        for _ in range(runs):
            md = run_simulation(MDBurstHADS, n, df)
            base = run_simulation(BurstHADS, n, df)

            md_makespan.append(md.makespan())
            base_makespan.append(base.makespan())

        results[n] = {
            "md": sum(md_makespan) / runs,
            "base": sum(base_makespan) / runs,
        }

    print(results)

    tasks = list(results.keys())
    md_mk = [results[n]["md"] for n in tasks]
    base_mk = [results[n]["base"] for n in tasks]

    plt.figure()
    plt.plot(tasks, md_mk, marker="o", label="MD-BurstHADS")
    plt.plot(tasks, base_mk, marker="o", label="Burst-HADS")
    plt.xlabel("Tasks")
    plt.ylabel("Makespan")
    plt.title(f"Makespan (Deadline Factor={df})")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.show()
