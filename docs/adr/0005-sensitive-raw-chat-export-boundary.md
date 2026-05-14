# Separate routine analysis data from sensitive raw chat export

Status: accepted

The database stores complete raw dialogue because text coding and mechanism analysis are part of the research design, but routine analysis exports should emphasize participant status, questionnaire scores, and behavior metrics. Raw chat is exported as a clearly labelled sensitive file inside the ZIP package rather than being embedded in the wide analysis CSV.

## Considered Options

- Include complete chat text in every analysis CSV.
- Exclude raw chat from exports by default.
- Store raw chat and export it as a separate sensitive file.

## Consequences

The research team can perform qualitative/text analysis when needed, while ordinary statistical workflows can use `analysis_dataset.csv` without spreading raw dialogue content unnecessarily.
