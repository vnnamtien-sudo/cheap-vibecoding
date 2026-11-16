# Task prompt templates

[← Back to README](../README.en.md)

Rule files provide working conventions. Each task brief should state its goal, allowed scope, and observable acceptance criteria.

## Implementation task

~~~text
Goal:
Files or directories allowed to change:
Existing behavior and constraints to preserve:
Completion criteria:
Required self-checks or tests:
How to mark items that lack evidence:
~~~

Search relevant code and callers before reading only the needed sections. Change only what is required for the goal. At completion, list changed files and the actual self-check commands and results. Mark checks that were not run.

## Read-only light review

Start each review in a fresh session with no context from the implementation session. Provide the changed files, acceptance criteria, and available self-check evidence.

~~~text
Review the following changes in read-only mode. Do not edit files:
Goal and acceptance criteria:
Changed files:
Actual self-check and test results:
Report only evidence-backed issues, with severity, file location, impact, and reproduction evidence.
If none are found, state “No issue found within this review scope” and list anything not checked.
~~~

See the [task template](../templates/dispatch/task.en.md), [handoff template](../templates/dispatch/handoff.en.md), and [light review template](../templates/dispatch/review.en.md) for more fields.
