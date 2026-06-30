# Outage Prediction Design

Milestone 6 implements local, deterministic outage-risk prediction over validated interim data. It consumes `data/interim/*.jsonl` only and does not read raw source files or quarantined records.

The CI profile uses `feeder` entity grain because the synthetic six-hour dataset contains two feeders and two unplanned feeder-linked outages. `substation` and `primary_asset` entity semantics are represented in the entity and label logic, but the CI workflow uses feeder grain for sufficient class variation.

Workflow:

1. load validated interim datasets;
2. build an entity-time panel at the configured observation frequency;
3. generate future unplanned-outage labels;
4. derive historical features ending at the observation timestamp;
5. split chronologically with a horizon-sized purge;
6. train transparent baselines and deterministic logistic regression;
7. evaluate, select a model, and interpret raw risk scores;
8. write predictions, metrics, metadata, manifests, and reports.

The implementation is synthetic decision support only. It is not certified engineering protection logic, restoration automation, or a real utility operating system.
