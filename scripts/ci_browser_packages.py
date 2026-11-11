"""Use signed direct Ubuntu archives on disposable GitHub Linux runners only."""

import os
import sys
from pathlib import Path


def direct_archives(content: str) -> str:
    for before, after in (
        (
            "mirror+file:/etc/apt/apt-mirrors-security.txt",
            "https://security.ubuntu.com/ubuntu",
        ),
        ("mirror+file:/etc/apt/apt-mirrors.txt", "https://archive.ubuntu.com/ubuntu"),
        ("http://azure.archive.ubuntu.com/ubuntu", "https://archive.ubuntu.com/ubuntu"),
        (
            "https://azure.archive.ubuntu.com/ubuntu",
            "https://archive.ubuntu.com/ubuntu",
        ),
        ("http://archive.ubuntu.com/ubuntu", "https://archive.ubuntu.com/ubuntu"),
        ("http://security.ubuntu.com/ubuntu", "https://security.ubuntu.com/ubuntu"),
    ):
        content = content.replace(before, after)
    return content


def main():
    if os.getenv("GITHUB_ACTIONS") != "true" or sys.platform != "linux":
        raise SystemExit("This setup is only for disposable GitHub Linux runners")
    apt = Path("/etc/apt")
    paths = [
        apt / "sources.list",
        *(apt / "sources.list.d").glob("*.sources"),
        *(apt / "sources.list.d").glob("*.list"),
    ]
    for path in paths:
        if path.is_file():
            original = path.read_text()
            updated = direct_archives(original)
            if original != updated:
                path.write_text(updated)
    (apt / "apt.conf.d/80-airshedos-ci-network").write_text(
        'Acquire::http::Timeout "20";\nAcquire::https::Timeout "20";\nAcquire::Retries "2";\n'
    )
    print(
        "Selected direct HTTPS Ubuntu archives; signed package verification remains enabled."
    )


if __name__ == "__main__":
    main()
