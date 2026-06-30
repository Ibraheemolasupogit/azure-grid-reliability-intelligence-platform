# Label Definition

For each entity and observation timestamp, the target is:

```text
1 if an unplanned outage starts after the observation timestamp
and on or before the configured prediction horizon boundary,
otherwise 0
```

Planned outages are excluded. Outages starting at or before the observation timestamp are not positive labels for that row. The label uses `outage_start`, not restoration time.

The CI profile uses:

- entity grain: `feeder`;
- observation frequency: 60 minutes;
- prediction horizon: 1 interval;
- lookback: 2 intervals.

Overlapping horizons may label more than one observation row for the same outage if the configured horizon is longer than one interval. The CI horizon is one interval, so each synthetic outage maps to one positive feeder-time row.
