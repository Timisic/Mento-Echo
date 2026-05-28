# Prefer length-guarded promptless Codex GPT-5.5 dialogue within a 30-second response SLA

The participant-facing AI dialogue should not use hidden topic prompts, developer instructions, base instructions, personas, counseling style instructions, or model-side topic guidance. One neutral length/completeness guard is allowed to prevent overly long or abruptly truncated participant-facing replies. Codex GPT-5.5 is the preferred dialogue model provider when it can return a usable assistant reply within the configured 30-second participant-facing SLA; if it cannot, the platform should degrade to DeepSeek or another faster OpenAI-compatible provider rather than making the participant wait.

## Considered Options

- Keep research-topic system prompts and prompt versions for reproducibility.
- Use Codex only, even when latency exceeds the participant-facing SLA.
- Use length-guarded promptless dialogue with Codex-first routing and bounded DeepSeek fallback.

## Consequences

This keeps the AI dialogue free of hidden topic steering while protecting participants from very long replies. Future analysis should treat the model conversation as `length_guarded_promptless_v1` provider output rather than a controlled prompt-condition intervention. Implementation should record the length guard prompt mode and provider/model/timing metadata for technical reproducibility.
