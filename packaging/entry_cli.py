"""PyInstaller entry point for the CLI executable.

PyInstaller must be pointed at a *standalone* script (not a module inside the
package), otherwise relative imports like ``from .calibration import ...`` fail
at runtime with "attempted relative import with no known parent". This wrapper
uses an absolute import from the installed ``gamma_spectrum_analyzer`` package.
"""

import sys

from gamma_spectrum_analyzer.cli import app

if __name__ == "__main__":
    sys.exit(app())
