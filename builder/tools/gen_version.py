#!/usr/bin/env python3
"""Write the git commit of a repository into a one-line version file (e.g. VERSION.TXT on a disc).

Usage: gen_version.py OUTPUT_PATH [REPO_DIR]     (REPO_DIR defaults to the current directory)

Writes `git rev-parse --short=8 HEAD` of REPO_DIR to OUTPUT_PATH as plain ASCII: one line, newline terminated,
at most 16 characters, no BOM. `-dirty` is appended when `git status --porcelain` lists anything (e.g.
`a1b2c3d4-dirty`). REPO_DIR must be the top-level folder of its own repository: a folder that only sits inside
another checkout (an exported or copied tree) is not that repository. When git is missing, REPO_DIR is not a
repository or anything fails, the file says `unknown` and the exit status is still 0: it never fails a build.
The string is printed to stdout.

Only git and the Python standard library are needed. Keep this file identical in every project that uses it:
copy it unchanged, never edit a single copy.
"""
import os
import subprocess
import sys

MAX_LEN = 16


def git(repo, *args):
    return subprocess.run(['git', '-C', repo] + list(args), capture_output=True, text=True, check=True,
                          timeout=60).stdout.strip()


def version(repo):
    try:
        top = git(repo, 'rev-parse', '--show-toplevel')
        if not top or os.path.realpath(top) != os.path.realpath(repo):
            return 'unknown'
        rev = git(repo, 'rev-parse', '--short=8', 'HEAD')
        if not rev or any(c not in '0123456789abcdef' for c in rev):
            return 'unknown'
        if git(repo, 'status', '--porcelain'):
            rev += '-dirty'
        return rev[:MAX_LEN]
    except Exception:
        return 'unknown'


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit('usage: gen_version.py OUTPUT_PATH [REPO_DIR]')
    out = sys.argv[1]
    v = version(sys.argv[2] if len(sys.argv) == 3 else os.getcwd())
    folder = os.path.dirname(os.path.abspath(out))
    os.makedirs(folder, exist_ok=True)
    with open(out, 'wb') as f:
        f.write(v.encode('ascii') + b'\n')
    print(v)


if __name__ == '__main__':
    main()
