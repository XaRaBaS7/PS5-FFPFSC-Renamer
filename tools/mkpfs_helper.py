from __future__ import annotations

import sys
from multiprocessing import freeze_support

from mkpfs.__main__ import main


if __name__ == "__main__":
    freeze_support()
    raise SystemExit(main(sys.argv[1:]))
