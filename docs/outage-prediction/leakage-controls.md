# Leakage Controls

Feature windows end at or before the observation timestamp. Label windows begin strictly after the observation timestamp.

The feature builders do not use:

- future outage flags;
- future restoration time;
- future outage duration;
- future final cause details;
- customers interrupted from the future outage;
- future telemetry;
- future weather observations;
- future maintenance completion;
- ingestion timestamps;
- label source outage IDs.

Chronological splitting preserves the final test period and applies a purge interval equal to the prediction horizon between training and validation/test periods.

Feature schema metadata records the prohibited fields and the past-only availability assumption.
