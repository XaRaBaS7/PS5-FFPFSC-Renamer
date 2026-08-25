"""Compatibility entry point for the current desktop interface."""

from .gui_v14 import RenamerApp, main

__all__ = ["RenamerApp", "main"]


if __name__ == "__main__":
    main()
