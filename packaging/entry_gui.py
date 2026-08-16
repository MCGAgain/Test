"""PyInstaller entry point for the GUI executable.

Same rationale as ``entry_cli.py``: an absolute import from the installed
package so PyInstaller bundles the package with its relative imports intact.
"""

from gamma_spectrum_analyzer.gui import main

if __name__ == "__main__":
    main()
