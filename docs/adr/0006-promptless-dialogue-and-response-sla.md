# Prefer promptless Codex GPT-5.5 dialogue within a 10-second response SLA

The participant-facing AI dialogue should not use hidden system prompts, developer instructions, base instructions, or model-side topic guidance. Codex GPT-5.5 is the preferred dialogue model provider when it can return a usable assistant reply within 10 seconds; if it cannot, the platform should degrade to DeepSeek or another faster OpenAI-compatible provider rather than making the participant wait.

## Considered Options

- Keep research-topic system prompts and prompt versions for reproducibility.
- Use Codex only, even when latency exceeds the participant-facing SLA.
- Use promptless dialogue with Codex-first routing and bounded DeepSeek fallback.

## Consequences

This makes the AI dialogue less experimentally steered by hidden instructions, so future analysis should treat the model conversation as promptless provider output rather than a controlled prompt-condition intervention. Implementation should remove model-side prompt fields from provider calls and use stored provider/model/timing metadata, not prompt versions, for technical reproducibility.
