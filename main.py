"""Start command Railpack can find without a framework.

Railway runs this when the service is built from the repository root.
"""

from jev_desk.server import main

if __name__ == "__main__":
    main()
