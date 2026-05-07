#!/usr/bin/env python3
"""Executable shim for launching the desktop GUI."""

from gui_app.app import main


if __name__ == "__main__":
    raise SystemExit(main())
