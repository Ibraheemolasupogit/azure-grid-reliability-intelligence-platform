# Operational Runbook

Run the full local demonstration:

```bash
make assistant-demo
```

Run the assistant against existing evidence:

```bash
python3 -m grid_reliability.genai.pipeline --config configs/genai_assistant.yaml
```

Outputs are written under `outputs/genai/` and reports under
`reports/genai/<run_id>/`. Responses support human review only.
