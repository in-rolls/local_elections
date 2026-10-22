"""Import a state's parser by name.

This used to load `src/local_elections/states/<state>/parse.py` from a path with
importlib, and
the reason was real: every state calls its parser `parse.py`, so a plain
`import parse` resolved to whichever one reached sys.path first, and the next
test module got that same module back out of the cache - testing another
state's code while appearing to pass.

The package layout removes the collision rather than working around it. Each
parser is now `local_elections.states.<state>.parse`, which is a distinct
name, so the standard import machinery does the right thing and the cache is an
advantage instead of a hazard.
"""

import importlib


def load(state):
    """Return the named state's parser module."""
    return importlib.import_module(f"local_elections.states.{state}.parse")
