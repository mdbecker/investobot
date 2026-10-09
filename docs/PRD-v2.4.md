# Investobot — Final CI Stabilization PRD

**Version:** 2.4  
**Priority:** P0 — Release blocker  
**Scope:** Fix one flaky GitHub Actions test without changing application functionality.

## 1. Problem

At commit `b8b72f9`, GitHub Actions reported **308 passed, 1 failed**.

Failing test:

`tests/test_web.py::test_reject_oversized_input`

The test submits a ~2.1 MB HTTP request. The WebUI correctly attempts to reject oversized requests with HTTP 413, but the client sometimes encounters a `BrokenPipe` while sending the body.

This is an HTTP test reliability issue, not an identified database defect.

## 2. Requirements

1. Make the oversized-request test deterministic by sending headers with `Content-Length` greater than the permitted limit, without transmitting the entire body.
2. Verify that the server returns HTTP **413** without reading the oversized request body.
3. Preserve the existing 2 MB request-size limit, input validation, and security behavior.
4. Ensure the test passes reliably on Linux GitHub Actions and the local Docker environment.
5. Do not modify financial calculations, SQLite storage, planning, or unrelated features.

## 3. Mandatory BDD Workflow

Follow **Red → Green → Refactor**.

Add or revise a BDD scenario covering oversized-request rejection, verify that it exposes the existing test failure or missing behavior, and apply the smallest necessary correction. If the server already behaves correctly, change only the test harness.

## 4. Acceptance Criteria

- Oversized requests consistently return HTTP 413.
- Rejection occurs before the body is read.
- Normal-sized requests continue working.
- The complete test suite passes.
- Ruff passes.
- GitHub Actions is fully green on the final commit.

## 5. Definition of Done

**One small, tested commit resolves the CI failure**, with no changes to investment logic, database architecture, or financial behavior.

After CI passes, mark Investobot V2.4 complete and close the MVP engineering stabilization phase.
