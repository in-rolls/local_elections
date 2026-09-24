"""The last gate before a tag.

Everything upstream of this in `make release-check` has already run - the tests,
the master, the stats, the worklist, the coverage links, the manifest and its
verification. What is left is the question none of those ask: is this tree in a
state you would want to be able to cite forever?

It refuses on a dirty tree or a dirty sibling, because a manifest that
attributes rows to a commit they did not come from is worse than no manifest.
It prints the tag command rather than running it.
"""

import json
import subprocess
import sys
from pathlib import Path

from local_elections.common.runlog import command
from local_elections.paths import ROOT

# Everything in the repository that is written by a generator rather than by
# hand. `make coverage` rebuilds them all, so a stale one leaves the tree dirty
# and this script already refuses - but it refused with "uncommitted changes",
# which does not tell anyone that the readme was out of date. Naming them turns
# a puzzle into an instruction.
GENERATED = [
    "README.md",
    "WORKLIST.md",
    "MANIFEST.json",
    "MANIFEST.md",
    "DICTIONARY.md",
]


def git_output(directory, *args):
    """Read Git state, refusing unavailable or unsuccessful commands."""
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(directory), *args],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"cannot inspect Git state at {directory}: {exc}") from exc
    if result.returncode:
        raise RuntimeError(
            f"cannot inspect Git state at {directory}: "
            f"git exited {result.returncode}: {result.stderr.strip()}"
        )
    return result.stdout.rstrip("\r\n")


def live_state(directory):
    """Require a worktree rooted here and return its commit and changed paths."""
    top = git_output(directory, "rev-parse", "--show-toplevel")
    if not top or Path(top).resolve() != directory.resolve():
        raise RuntimeError(f"{directory} is not the root of a Git worktree")
    commit = git_output(directory, "rev-parse", "--verify", "HEAD^{commit}")
    if not commit:
        raise RuntimeError(f"{directory} has no committed HEAD")
    out = git_output(
        directory,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--ignore-submodules=none",
    )
    # Keep the leading status characters: strip() would remove the initial
    # blank in a worktree-only change before slicing its path.
    changed = [line[3:].strip() for line in out.splitlines() if line.strip()]
    return commit, changed


def dirty_files():
    """Paths Git currently reports as changed in this repository."""
    _, changed = live_state(ROOT)
    return changed


@command("validate", expectation_set="release")
def main():
    version = sys.argv[1] if len(sys.argv) > 1 else ""
    manifest = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))

    problems = []
    try:
        changed = dirty_files()
    except RuntimeError as exc:
        problems.append(str(exc))
        changed = []
    if changed:
        stale = [f for f in changed if f in GENERATED or f.startswith("data/")]
        problems.append("this repository has uncommitted changes")
        for path in changed[:8]:
            note = ""
            if path in GENERATED:
                note = (
                    "  <- generated; `make coverage` rebuilt it, so it was out of date"
                )
            problems.append(f"    {path}{note}")
        if len(changed) > 8:
            problems.append(f"    ... and {len(changed) - 8} more")
        if stale:
            problems.append(
                "  commit these: a release pins file hashes, so a "
                "generated file that is not committed is not the "
                "one the manifest describes"
            )
    if manifest.get("dirty"):
        problems.append("the manifest records a dirty build; rebuild from clean inputs")
    for sibling in manifest.get("sibling_repos", []):
        name = sibling["repo"]
        if not sibling.get("present"):
            problems.append(
                f"{name} was absent from the build; its state is missing "
                "from this release manifest"
            )
            continue
        try:
            live_commit, changed = live_state(ROOT.parent / name)
        except RuntimeError as exc:
            problems.append(str(exc))
            continue
        if changed:
            problems.append(f"{name} has uncommitted changes")
        pinned = sibling.get("commit")
        if pinned != live_commit:
            problems.append(
                f"{name} live commit {live_commit} differs from manifest pin {pinned!r}"
            )
        if sibling.get("dirty"):
            problems.append(
                f"the manifest records dirty inputs from {name}; rebuild it"
            )

    print()
    if problems:
        print("Not ready to tag:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    rows = manifest["totals"].get("master_rows", 0)
    states = len(
        {
            s
            for f in manifest["files"]
            for s in f.get("states", [])
            if f.get("kind") == "master"
        }
    )
    print(
        f"Ready to tag: {rows:,} pooled seat-event records across {states} states, "
        f"{len(manifest['files'])} files pinned."
    )
    if not version:
        print(
            "\nRe-run with a version to get the command:"
            "\n  make release-check VERSION=v0.1.0"
        )
        return 0
    print(
        f"\nRun this yourself - a tag cannot be taken back:\n"
        f"  uv run build-manifest --release {version} && \\\n"
        f"  git add MANIFEST.json MANIFEST.md && \\\n"
        f"  git commit -m 'Release {version}' && \\\n"
        f"  git tag -a {version} -m 'Release {version}' && \\\n"
        f"  git push origin main {version}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
