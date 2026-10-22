"""Check a checkout against MANIFEST.json.

Standard library only, and it imports nothing from scripts/common on purpose:
it has to run from a bare checkout, an unpacked release tarball, or a machine
where nothing else in this repository works. A verifier that needs the
repository to be in working order cannot tell you the repository is intact.

    uv run python -m local_elections.tools.verify_manifest            # exit 0 if
    every file matches
    uv run python -m local_elections.tools.verify_manifest --quiet    # only
    report failures
"""

import argparse
import hashlib
import json
import pathlib
import sys
import tarfile

# The one module that does not import local_elections.paths, and the only
# place in the repository where duplicating that computation is correct. This
# script has to run from a bare checkout or an unpacked tarball, with nothing
# installed and no package importable - that is the promise the readme makes
# about it, and there is a test asserting it imports nothing but the standard
# library. Importing the package to find the repository root would quietly
# break exactly the case this exists for.
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent

MANIFEST = ROOT / "MANIFEST.json"


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            sha.update(chunk)
    return sha.hexdigest()


def safe_path(root, name):
    path = pathlib.PurePosixPath(name)
    if (
        not name
        or name == "."
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in name
        or path.as_posix() != name
    ):
        raise ValueError(f"Unsafe manifest path: {name!r}")
    target = root / name
    component = root
    for part in path.parts:
        component = component / part
        if component.is_symlink():
            raise ValueError(f"Evidence path contains a symbolic link: {name!r}")
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Manifest path leaves verification root: {name!r}")
    return target


def validate_entries(manifest, root):
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Manifest must contain a nonempty files list")
    names = set()
    for entry in entries:
        name = entry["path"]
        safe_path(root, name)
        if name in names:
            raise ValueError(f"Duplicate manifest path: {name}")
        names.add(name)
        sha = entry["sha256"]
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError(f"Invalid SHA-256: {name}")
    return entries


def verify_archives(manifest, directory):
    expected = {entry["path"]: entry for entry in manifest["files"]}
    seen = set()
    asset_names = set()
    declared_assets = {asset["name"] for asset in manifest.get("assets", [])}
    unlisted = {
        p.name for p in directory.glob("source-evidence-*.tar.gz")
    } - declared_assets
    if unlisted:
        raise ValueError(f"Unlisted evidence archives: {sorted(unlisted)}")
    for asset in manifest.get("assets", []):
        name = asset["name"]
        path = safe_path(directory, name)
        if name in asset_names:
            raise ValueError(f"Duplicate asset name: {name}")
        asset_names.add(name)
        if "sha256" not in asset:
            raise ValueError(f"Asset has not been built: {name}")
        if path.stat().st_size != asset["bytes"] or digest(path) != asset["sha256"]:
            raise ValueError(f"Archive checksum/size mismatch: {name}")
        count, total = 0, 0
        with tarfile.open(path, "r|gz") as archive:
            for member in archive:
                key = member.name
                if key not in expected or key in seen or not member.isfile():
                    raise ValueError(
                        f"Unexpected/duplicate/nonfile archive member: {key}"
                    )
                entry = expected[key]
                if entry["asset"] != name or member.size != entry["bytes"]:
                    raise ValueError(f"Archive member mapping/size mismatch: {key}")
                content = archive.extractfile(member)
                if content is None:
                    raise ValueError(f"Unreadable archive member: {key}")
                sha = hashlib.sha256()
                with content as stream:
                    for chunk in iter(lambda: stream.read(1 << 20), b""):
                        sha.update(chunk)
                if sha.hexdigest() != entry["sha256"]:
                    raise ValueError(f"Archive member checksum mismatch: {key}")
                seen.add(key)
                count += 1
                total += member.size
        if count != asset["members"] or total != asset["uncompressed_bytes"]:
            raise ValueError(f"Archive totals mismatch: {name}")
    if seen != set(expected):
        raise ValueError(
            f"Archive coverage incomplete: {len(set(expected) - seen)} missing"
        )
    return len(seen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--manifest", type=pathlib.Path, default=MANIFEST)
    ap.add_argument("--root", type=pathlib.Path, default=ROOT)
    ap.add_argument("--archives", type=pathlib.Path)
    args = ap.parse_args()

    if not args.manifest.exists():
        print(f"no manifest at {args.manifest}")
        return 2
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        entries = validate_entries(manifest, args.root)
        if args.archives is not None:
            count = verify_archives(manifest, args.archives)
            print(f"OK: {count} archive members match the evidence manifest")
            return 0
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError) as error:
        print(f"FAILED: {error}")
        return 1

    missing, changed, ok = [], [], 0
    for entry in entries:
        path = args.root / entry["path"]
        if not path.is_file():
            missing.append(entry["path"])
            continue
        if digest(path) != entry["sha256"] or (
            "bytes" in entry and path.stat().st_size != entry["bytes"]
        ):
            changed.append(entry["path"])
            continue
        ok += 1

    extras = []
    if manifest.get("manifest_type") == "source_evidence":
        expected = {entry["path"] for entry in entries}
        actual = set()
        for scope in manifest["scopes"]:
            directory = safe_path(args.root, scope)
            for path in directory.rglob("*"):
                if path.name in manifest.get("excluded_names", []):
                    continue
                if path.is_file() or path.is_symlink():
                    actual.add(path.relative_to(args.root).as_posix())
        extras = sorted(actual - expected)

    release = manifest.get("release") or "(untagged)"
    print(
        f"manifest {release}, schema version "
        f"{manifest.get('schema_version')}, built from "
        f"{manifest.get('built_from_commit', '')[:12]}"
    )
    if manifest.get("dirty"):
        print("  WARNING: built from a tree with uncommitted changes")
    for sibling in manifest.get("sibling_repos", []):
        if sibling.get("dirty"):
            print(f"  WARNING: {sibling['repo']} was dirty when read")

    if not args.quiet or missing or changed:
        print(f"  {ok} file(s) match")
    for path in missing:
        print(f"  MISSING  {path}")
    for path in changed:
        print(f"  CHANGED  {path}")
    for path in extras:
        print(f"  UNLISTED  {path}")

    if missing or changed or extras:
        print(
            f"\nFAILED: {len(missing)} missing, {len(changed)} changed, "
            f"{len(extras)} unlisted"
        )
        return 1
    print("\nOK: every file matches the manifest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
