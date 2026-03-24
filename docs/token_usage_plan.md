# Implementation Plan - LLM Token Usage Visibility

The goal is to expose LLM token usage (input and output) to the frontend (Athena) by including this data in the `Completed` message yielded at the end of an Elysia decision tree run.

## Proposed Changes

### [Elysia Core]

#### [MODIFY] [objects.py](file:///Users/mp/AthenaAI/elysia/elysia/objects.py)
#### [MODIFY] [tree.py](file:///Users/mp/AthenaAI/elysia/elysia/tree/tree.py)

## Verification Plan

### Automated Tests
- Create a test script `/tmp/test_tokens.py` that initializes a `Tree`, runs a simple query, and intercepts the yielded results to verify that the `Completed` payload contains the expected `usage` field with non-null token counts.
- Run the test using `python /tmp/test_tokens.py`.

### Manual Verification
- Check the backend logs to ensure `log_token_usage()` still outputs the correct information.
- Provide the user with a code snippet to run in their environment to see the token usage in the output of `async_run`.
