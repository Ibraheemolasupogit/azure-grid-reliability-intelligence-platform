# Population and Denominators

The implemented population method is `observed_smart_meters`.

For each assessment period, the denominator is the unique count of `meter_id` values observed in validated smart-meter events for the entity hierarchy:

- feeder: unique meters on the feeder;
- substation: unique meters on feeders belonging to the substation;
- grid region: unique meters in the region.

This is an observed-meter population, not a certified customer count. It is used because the synthetic data does not provide a separate regulatory customer inventory.

Interrupted-customer counts from outage records are not used to infer denominators.
