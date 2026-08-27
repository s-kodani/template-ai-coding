from scripts.validate_okf import PENDING_VERSION_HEADING, validate_log_md


def test_validate_log_md_accepts_pending_heading_first() -> None:
    text = f"""# Release Log

## {PENDING_VERSION_HEADING}

- **Added**: example

## v1.0.0

- **Added**: initial
"""
    assert validate_log_md(text) == []


def test_validate_log_md_rejects_pending_heading_not_first() -> None:
    text = f"""# Release Log

## v1.0.0

- **Added**: initial

## {PENDING_VERSION_HEADING}

- **Added**: example
"""
    errors = validate_log_md(text)
    assert any("must appear first" in err for err in errors)


def test_validate_log_md_rejects_multiple_pending_headings() -> None:
    text = f"""# Release Log

## {PENDING_VERSION_HEADING}

- **Added**: one

## {PENDING_VERSION_HEADING}

- **Added**: two
"""
    errors = validate_log_md(text)
    assert any("at most one pending version heading" in err for err in errors)
