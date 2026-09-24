"""Resolve the published state inputs pinned in data/sources.json."""

import hashlib
import json
import os
import pathlib
import shutil
import tempfile

import requests

from local_elections.paths import ROOT


def resolve(provider, root=None):
    root = ROOT if root is None else pathlib.Path(root)
    specifications = json.loads((root / "data" / "sources.json").read_text())
    specification = specifications.get(provider)
    if specification is None:
        return None
    revision = specification["ref"]
    directory = (
        pathlib.Path(os.environ.get("INDIA_DATA_HOME", "~/data")).expanduser()
        / provider
        / revision
    )
    for relative, expected in specification["files"].items():
        destination = directory / relative
        if destination.exists():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != expected:
                raise ValueError(f"Cached source checksum mismatch: {destination}")
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        sibling = root.parent / provider / relative
        with tempfile.NamedTemporaryFile(
            dir=destination.parent, delete=False
        ) as handle:
            temporary = pathlib.Path(handle.name)
        try:
            if (
                sibling.exists()
                and hashlib.sha256(sibling.read_bytes()).hexdigest() == expected
            ):
                shutil.copyfile(sibling, temporary)
            else:
                url = (
                    f"https://raw.githubusercontent.com/in-rolls/{provider}/"
                    f"{revision}/{relative}"
                )
                with requests.get(url, timeout=120, stream=True) as response:
                    response.raise_for_status()
                    with temporary.open("wb") as handle:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            handle.write(chunk)
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != expected:
                raise ValueError(f"Published source checksum mismatch: {destination}")
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    return directory, revision
