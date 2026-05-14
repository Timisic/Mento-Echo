# Keep questionnaires as versioned configuration for MVP

Status: accepted

MVP questionnaire definitions will be structured configuration with immutable version labels rather than researcher-editable admin screens. The experiment depends on comparability across participants, so changing wording, options, or scoring rules must be a deliberate configuration/version change rather than an untracked UI edit.

## Considered Options

- Admin-editable questionnaire builder.
- Fixed/versioned questionnaire configuration.
- External questionnaire platform.

## Consequences

Researchers cannot freely edit questions through the MVP admin UI. Implementation must convert the Word questionnaire into structured definitions and produce a new `questionnaire_version` when wording or scoring changes.
