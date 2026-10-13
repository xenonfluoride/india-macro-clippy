#!/usr/bin/env python3
"""Build a Pages artifact only from the validated, hash-checked accepted pointer."""
import argparse
from pathlib import Path
import shutil
from newsletter import OUTPUTS, check_accepted


def assemble(destination, outputs=OUTPUTS):
    bundle = check_accepted(outputs)
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Use a new artifact directory; do not overwrite an existing site')
    destination.mkdir(parents=True)
    shutil.copyfile(bundle / 'newsletter.html', destination / 'index.html')
    for name in ('capture.json', 'review.json', 'edition.json', 'market.json', 'verification.json', 'manifest.json'):
        shutil.copyfile(bundle / name, destination / name)
    (destination / '.nojekyll').touch()
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    print(assemble(args.destination))
