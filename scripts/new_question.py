"""Start a blank question branch while preserving previous attempts."""

import argparse
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Question name, for example arrays-01")
    name = parser.parse_args().name
    branch = f"question/{name}"
    try:
        git("check-ref-format", "--branch", branch)
        if git("status", "--porcelain", "--untracked-files=all"):
            print(
                "Commit or stash current work before starting a question. "
                "No files or branches changed.",
                file=sys.stderr,
            )
            return 1
        git("rev-parse", "--verify", "interview-starter^{commit}")
        git("switch", "-c", branch, "interview-starter")
    except subprocess.CalledProcessError as error:
        print(error.stderr.strip(), file=sys.stderr)
        return 1
    print(f"Ready on {branch}. Paste the prompt, starter and examples, then commit the import.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
