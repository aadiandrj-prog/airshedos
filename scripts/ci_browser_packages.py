"""Select a reachable signed Ubuntu archive on disposable GitHub Linux runners only."""

import os
import platform
import subprocess
import sys
from pathlib import Path


def direct_archives(
    content: str, archive: str = "https://archive.ubuntu.com/ubuntu"
) -> str:
    for before in (
        "mirror+file:/etc/apt/apt-mirrors-security.txt",
        "mirror+file:/etc/apt/apt-mirrors.txt",
        "http://azure.archive.ubuntu.com/ubuntu",
        "https://azure.archive.ubuntu.com/ubuntu",
        "http://archive.ubuntu.com/ubuntu",
        "http://security.ubuntu.com/ubuntu",
        "https://archive.ubuntu.com/ubuntu",
        "https://security.ubuntu.com/ubuntu",
    ):
        content = content.replace(before, archive)
    return content


def select_archive(suite):
    # Probe signed release files before altering apt; apt still performs the actual
    # cryptographic verification with the unchanged Ubuntu archive keyring.
    for archive in (
        "https://archive.ubuntu.com/ubuntu",
        "https://mirrors.edge.kernel.org/ubuntu",
        "https://mirror.math.princeton.edu/pub/ubuntu/ubuntu",
    ):
        for pocket in (suite, suite + "-security"):
            try:
                result = subprocess.run(
                    [
                        "curl",
                        "--fail",
                        "--silent",
                        "--show-error",
                        "--location",
                        "--proto",
                        "=https",
                        "--proto-redir",
                        "=https",
                        "--connect-timeout",
                        "5",
                        "--max-time",
                        "10",
                        "--max-filesize",
                        "1048576",
                        archive + "/dists/" + pocket + "/InRelease",
                    ],
                    capture_output=True,
                    timeout=12,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                break
            if result.returncode or not result.stdout.startswith(
                b"-----BEGIN PGP SIGNED MESSAGE-----"
            ):
                break
        else:
            return archive
    raise SystemExit(
        "No reachable Ubuntu archive; browser dependencies remain required"
    )


def main():
    if os.getenv("GITHUB_ACTIONS") != "true" or sys.platform != "linux":
        raise SystemExit("This setup is only for disposable GitHub Linux runners")
    release = platform.freedesktop_os_release()
    suite = release.get("VERSION_CODENAME", "")
    if release.get("ID") != "ubuntu" or not suite.isalpha():
        raise SystemExit("Expected the disposable Ubuntu runner")
    archive = select_archive(suite)
    apt = Path("/etc/apt")
    paths = [
        apt / "sources.list",
        *(apt / "sources.list.d").glob("*.sources"),
        *(apt / "sources.list.d").glob("*.list"),
    ]
    for path in paths:
        if path.is_file():
            original = path.read_text()
            updated = direct_archives(original, archive)
            if original != updated:
                path.write_text(updated)
    (apt / "apt.conf.d/80-airshedos-ci-network").write_text(
        'Acquire::http::Timeout "20";\nAcquire::https::Timeout "20";\nAcquire::Retries "2";\n'
    )
    print(f"Selected {archive}; Ubuntu package signature verification remains enabled.")


if __name__ == "__main__":
    main()
