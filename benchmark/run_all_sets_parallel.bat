@echo off

start cmd /k "echo Running set A... && python benchmark/harness.py --tasks benchmark/tasks/tasks_set_a.json --output benchmark/results/results_set_a.json && python benchmark/run_baseline.py --tasks benchmark/tasks/tasks_set_a.json --results benchmark/results/results_set_a.json"

start cmd /k "echo Running set B... && python benchmark/harness.py --tasks benchmark/tasks/tasks_set_b.json --output benchmark/results/results_set_b.json && python benchmark/run_baseline.py --tasks benchmark/tasks/tasks_set_b.json --results benchmark/results/results_set_b.json"

start cmd /k "echo Running set C... && python benchmark/harness.py --tasks benchmark/tasks/tasks_set_c.json --output benchmark/results/results_set_c.json && python benchmark/run_baseline.py --tasks benchmark/tasks/tasks_set_c.json --results benchmark/results/results_set_c.json"

start cmd /k "echo Running set E... && python benchmark/harness.py --tasks benchmark/tasks/tasks_set_e.json --output benchmark/results/results_set_e.json && python benchmark/run_baseline.py --tasks benchmark/tasks/tasks_set_e.json --results benchmark/results/results_set_e.json"

start cmd /k "echo Running set F... && python benchmark/harness.py --tasks benchmark/tasks/tasks_set_f.json --output benchmark/results/results_set_f.json && python benchmark/run_baseline.py --tasks benchmark/tasks/tasks_set_f.json --results benchmark/results/results_set_f.json"