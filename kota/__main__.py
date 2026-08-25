"""Entry point for `python -m kota`, the `kota` command and the shortcut."""

import os
import sys

# Run by path, as a shortcut does, there is no package around this file,
# so the checkout has to go on the path before anything is imported.
if not __package__:
    here = os.path.dirname(os.path.realpath(__file__))
    sys.path[:] = [p for p in sys.path if os.path.realpath(p or ".") != here]
    sys.path.insert(0, os.path.dirname(here))

from kota.cli import main

if __name__ == "__main__":
    sys.exit(main())
