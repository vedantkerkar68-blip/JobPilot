"""JobPilot backend package.

A small, read-only analytics API over a personal internship tracking
spreadsheet.  Modules:

* :mod:`app.config`    - environment-driven settings.
* :mod:`app.sheets`    - CSV and Google Sheets (read-only) data sources.
* :mod:`app.analytics` - analytics, deduplication and preference matching.
* :mod:`app.schemas`   - Pydantic response models.
* :mod:`app.main`      - the FastAPI application and routes.
"""

from __future__ import annotations

__version__ = "0.1.0"