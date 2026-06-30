# Feature Engineering

All features are historical or known at the observation timestamp.

Implemented operational features include load, utilisation, transformer temperature, alarm count, constrained/offline state counts, frequency deviation count, and voltage deviation count.

Implemented weather features include current regional weather at the observation timestamp plus recent severe-weather count, precipitation total, and maximum wind gust inside the lookback window.

Implemented smart-meter features include aggregate energy, energy change, meter count, estimated-reading share, missing-reading indicator, and voltage-quality issue count.

Implemented asset and maintenance features include asset age, expected-life ratio, criticality score, operational-status score, inspection-overdue flag, maintenance recency, corrective and emergency maintenance counts, deferred maintenance, follow-up count, and recent downtime.

Implemented prior-outage features include prior unplanned outage count, days since previous unplanned outage, prior equipment-failure outage count, prior severe-weather outage count, and historical duration for outages completed before the observation timestamp.
