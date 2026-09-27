# Recover the localization contract seen by the audit tab

A release-gate browser capture under `/app/data` came from a long-lived frontend session that crossed Service Worker and webpack hot-update generations. Reconstruct the localization compatibility manifest from the browser/build evidence that actually governed each recorded route checkpoint.

Read `/app/data/capture_notes.md`. The captured worker and HMR runtime sources are authoritative for their respective browser/runtime behavior.

Write the completed manifest to `/app/output/i18n_contract.json`.

You have 9000 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
