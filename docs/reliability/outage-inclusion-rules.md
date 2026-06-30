# Outage Inclusion Rules

Outages are assigned to periods by `outage_start`.

The configuration controls:

- planned outage inclusion;
- unplanned outage inclusion;
- minimum duration;
- maximum duration;
- sustained interruption threshold.

Duration classes:

- `MOMENTARY_OR_SHORT`: below the sustained threshold;
- `SUSTAINED`: at or above the sustained threshold and below the restoration target;
- `PROLONGED`: at or above the restoration target.

SAIDI and SAIFI use validated event-level customer interruption values. ASAI uses merged outage windows for entity outage time to avoid double-counting availability when outage windows overlap for the same entity.
