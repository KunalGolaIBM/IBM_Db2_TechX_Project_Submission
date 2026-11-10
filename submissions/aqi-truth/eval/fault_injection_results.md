# Fault-injection results

Faults are simulated; the days they are planted into are real.

| Planted fault | Cases | AQI Truth (Db2) flags | Min/max threshold flags | Plain average flags |
|---|---|---|---|---|
| Stuck | 33 | 33 (100%) | 0 (0%) | 0 (0%) |
| Spike | 33 | 25 (75%) | 4 (12%) | 0 (0%) |
| Dropout | 33 | 33 (100%) | 0 (0%) | 0 (0%) |
| Sentinel | 33 | 33 (100%) | 33 (100%) | 0 (0%) |
| Zero | 33 | 33 (100%) | 0 (0%) | 0 (0%) |
| Scale | 33 | 33 (100%) | 33 (100%) | 0 (0%) |
| No fault (false alarms) | 100 | 0 (0%) | 0 (0%) | 0 (0%) |

Faults caught: AQI Truth 190/198 (96%), threshold 70/198 (35%), plain average 0/198. False alarms on clean days: AQI Truth 0/100, threshold 0/100.
Clean real param-days available: 3081; seed 7.
