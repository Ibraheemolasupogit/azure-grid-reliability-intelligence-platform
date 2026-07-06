# Deployment Sequence

Blueprint deployment order:

1. Resource groups and baseline tags.
2. Networking and private DNS.
3. Monitoring and Key Vault.
4. Storage.
5. Event ingestion.
6. Analytics.
7. Azure Machine Learning.
8. Azure AI Foundry and Azure AI Search.
9. Governance.
10. Reporting integration.
11. Diagnostic settings.
12. Validation and smoke tests.

Each stage needs approvals, what-if review, rollback expectations, and validation
gates. This milestone does not execute deployment.
