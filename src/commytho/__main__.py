"""Permet python -m commytho, ce dont se sert la tâche planifiée."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
