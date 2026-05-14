# Support imported assignments and first-entry randomization

Status: accepted

Participant imports may include an assigned group; if no group is imported, the platform randomizes the participant on first entry and locks the assignment. This supports both pilot workflows with researcher-controlled groups and formal runs where the platform performs random assignment, while preventing refresh or re-entry from changing a participant's condition.

## Considered Options

- Researcher imports every assignment.
- Platform randomizes every participant.
- Separate group-specific entry links.
- Hybrid imported-or-randomized assignment with locking.

## Consequences

Exports must record `assignment_source` so analysis can distinguish imported and randomized assignments. Assignment changes after locking should require explicit admin action and audit logging.
