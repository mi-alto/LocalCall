# Contributing

Use English for new documentation, identifiers, commit messages and pull requests. The existing interface is Italian; English UI localization is welcome as a separate change.

Keep audio processing local. Do not add remote inference, telemetry or participant-data uploads. Never attach real meeting audio, tokens, participant names or private browser profiles to issues or pull requests; use synthetic fixtures.

Run the relevant Python tests for server or attribution changes and browser tests for extension or UI changes. Changes to page adapters need controlled DOM fixtures and a clearly described real-call validation when available. Do not describe synthetic fixtures as proof of live service compatibility.

Document changes in behavior and remaining limitations. Keep model weights, generated packages and local review output out of commits. Check the staged diff before committing.

Contributions to LocalCall source are provided under the project’s GPL-3.0-only license. Preserve applicable third-party notices.
