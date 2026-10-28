# Numeric UPRN validation proof

Environment: Python 3.14.7, FastMCP 4.1.4, editable install with dev dependencies.
HTTP is mocked; these checks do not claim live API availability or billing correctness.

## Full suite

Command: `.venv/bin/python -m pytest -q` (exit 0).

```text
........................................................................ [ 25%]
........................................................................ [ 51%]
........................................................................ [ 77%]
...............................................................          [100%]
279 passed in 7.58s
```

Both address_match and address_postcode return a numeric UPRN in the mock response.
Each value is passed through the MCP client to every manifest tool accepting uprn;
each call sends exactly one HTTP request with the identifier as digits.
Unit cases cover zero, integer and string identifiers, leading zero preservation,
negative values, fractional and whole floats, booleans and non-digit strings.
MCP invalid-input checks verify that rejected calls never reach HTTP.
Schema tests check every manifest parameter and parity rejects missing integer
support, number in place of integer, and integer support on ordinary strings.

## Regression control

Temporarily replacing only calls.py with its pre-change HEAD version, then running
`.venv/bin/python -m pytest tests/test_calls.py tests/test_server_parity.py -q`,
returned exit 1: 6 failed, 98 passed. Failures were numeric zero, numeric UPRN,
the schema check, server listing parity, and both address-result chains.
The fixed file was restored before the successful full-suite run above.

## Other checks

Ruff on the six changed Python files: All checks passed (exit 0).
The broad repository lint run found nine pre-existing findings in unchanged files;
those are outside this ticket.
Merge-queue legs command with PROJECT_ONYX_CODE_ROOT set: exit 0, no legs printed
(the project has no configured legs). No credential-dependent checks were deferred.
Buttons and vision: not applicable, no Live Preview for homedata-mcp.
AI: not applicable, this package change makes no model calls.
