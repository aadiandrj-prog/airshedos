"""Scan Git-visible files, optional artifacts and compiled frontend without printing secrets."""

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    "Google API key": rb"AIza[0-9A-Za-z_-]{35}",
    "Private key": rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "Google access token": rb"ya29\.[0-9A-Za-z_-]{20,}",
    "ADC refresh token": rb'"refresh_token"\s*:\s*"[^"\s]{12,}"',
    "GitHub token": rb"(?:gh[pousr]_[0-9A-Za-z]{30,}|github_pat_[0-9A-Za-z_]{30,})",
    "AWS access key": rb"(?:AKIA|ASIA)[0-9A-Z]{16}",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-build", action="store_true")
    parser.add_argument("--artifact", action="append", default=[])
    args = parser.parse_args()
    names = (
        subprocess.check_output(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    paths = {ROOT / name for name in names if name}
    if args.include_build:
        paths.update((ROOT / "apps/web/.next").rglob("*"))
    paths.update(Path(p).resolve() for p in args.artifact)
    # Compare the actual local API keys as well as generic signatures. Never print values.
    exact = []
    browser_key = b""
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "NEXT_PUBLIC_GOOGLE_MAPS_BROWSER_KEY":
                browser_key = value.strip().strip("\"'").encode()
            if key.strip() in (
                "GOOGLE_MAPS_PLATFORM_API_KEY",
                "NASA_FIRMS_MAP_KEY",
                "OPENAQ_API_KEY",
            ):
                value = value.strip().strip("\"'")
                if len(value) > 12:
                    exact.append(value.encode())
    failures, count = [], 0
    for path in sorted(paths):
        if not path.is_file() or path.is_symlink():
            continue
        count += 1
        data = path.read_bytes()
        for rule, pattern in RULES.items():
            matches = re.findall(pattern, data)
            if rule == "Google API key" and path.is_relative_to(ROOT / "apps/web/.next"):
                # Only this explicitly configured public credential may occur in bundles.
                # Backend keys, source files and arbitrary artifacts remain fully scanned.
                matches = [m for m in matches if m != browser_key or m in exact]
            if matches:
                failures.append(
                    (
                        str(path.relative_to(ROOT))
                        if path.is_relative_to(ROOT)
                        else str(path),
                        rule,
                    )
                )
        if any(key in data for key in exact):
            failures.append((str(path), "Actual local provider credential"))
    for path, rule in failures:
        print(f"FAIL: {path}: {rule}")
    print(
        f"Secret scan: {'FAIL' if failures else 'PASS'}; {count} files, {len(failures)} findings."
    )
    raise SystemExit(bool(failures))


if __name__ == "__main__":
    main()
