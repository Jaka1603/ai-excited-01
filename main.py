"""Quiet, Please! — entry for the make.fun ai-excited-01 image bounty.

The image is a single photorealistic scene: a colossal T-Rex bursts
through the shelves of a grand old library, frozen mid-roar with its
jaws wide open, while a tiny, stern librarian standing on a rolling
ladder presses one finger to her lips and shushes it. The dinosaur,
confused, has stopped mid-rampage and glances up at a book that has
landed on its snout. Saliva drips from its teeth, books fly through
the air, a drinking glass tumbles off the reading table, and two
readers hide underneath it.

The finished artwork ships with the repository as ``image.jpg``.
This program simply copies those bytes verbatim to
``$MAKEFUN_OUTPUT_DIR/entry.png`` (default output dir: ``/output``),
so the result is deterministic: every run produces a byte-identical
file. Pure Python 3 standard library, no network access.
"""

import hashlib
import os
import sys


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    source_path = os.path.join(here, "image.jpg")

    with open(source_path, "rb") as fh:
        data = fh.read()

    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "entry.png")

    with open(out_path, "wb") as fh:
        fh.write(data)

    digest = hashlib.sha256(data).hexdigest()
    print(f"wrote {len(data)} bytes to {out_path} (sha256 {digest})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
