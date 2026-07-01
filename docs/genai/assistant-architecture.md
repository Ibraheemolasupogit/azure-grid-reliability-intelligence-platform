# Assistant Architecture

Milestone 9 implements a local, provider-neutral Grid Operations Assistant. It
uses only governed repository evidence from reports, metrics, manifests, outputs,
documentation, and contracts.

```mermaid
flowchart TD
    A["Approved reports, metrics, and manifests"] --> B["Source governance and extraction"]
    B --> C["Chunking and local index"]
    C --> D["Query classification and retrieval"]
    D --> E["Grounding and safety checks"]
    E --> F["Grounded response"]
    E --> G["Refusal or qualification"]
    F --> H["Citations, audit, metrics, and reports"]
    G --> H
```

No Azure AI Foundry, Azure AI Search, Azure OpenAI, external model, internet
access, or operational action is used.
