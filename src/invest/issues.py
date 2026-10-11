"""Shared typed uncertainty gates."""

def _issue(code, message, **fields):
    return dict(code=code, message=message, blocks_calculation=True,
                blocks_proposals=True, blocks_execution_review=True, **fields)

