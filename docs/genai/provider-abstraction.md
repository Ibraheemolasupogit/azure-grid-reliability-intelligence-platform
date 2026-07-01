# Provider Abstraction

The provider interface is `generate(request) -> GenerationResult`.

The default `DeterministicLocalProvider` uses templates and retrieved evidence.
The Azure AI Foundry seam is documentation-oriented only: it performs no network
call, requires no Azure SDK, and returns no fabricated model output.
