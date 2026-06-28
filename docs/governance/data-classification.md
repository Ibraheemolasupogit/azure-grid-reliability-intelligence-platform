# Data Classification

This repository must use synthetic or non-sensitive development data only.

## Classification Levels

| Level | Description | Repository handling |
| --- | --- | --- |
| Public | Documentation and non-sensitive examples | May be committed |
| Internal | Project configuration without secrets | May be committed when reviewed |
| Confidential | Operational, customer, asset, or location-sensitive data | Must not be committed |
| Secret | Credentials, keys, tokens, connection strings | Must never be committed |

## Current State

Milestone 1 commits no datasets and no credentials. `.env.example` contains empty Azure variables to document future configuration shape.

## Future Controls

Later milestones should add schema validation, data-quality gates, lineage metadata, retention guidance, and checks that prevent sensitive operational data from entering committed fixtures.

