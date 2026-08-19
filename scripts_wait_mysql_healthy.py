import subprocess
import time
import sys

CONTAINER_NAME = "eldojo-mysql-local"
TIMEOUT_SECONDS = 90
POLL_INTERVAL = 2


def main():
    deadline = time.time() + TIMEOUT_SECONDS
    out = ""

    while time.time() < deadline:
        try:
            out = subprocess.check_output(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{json .State.Health.Status}}",
                    CONTAINER_NAME,
                ],
                text=True,
            ).strip().strip('"')
            sys.stdout.write(f"  status={out}\n")
            sys.stdout.flush()
            if out == "healthy":
                break
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)

    if out != "healthy":
        sys.stderr.write(f"[TIMEOUT mysql not healthy after {TIMEOUT_SECONDS}s\n")
        sys.exit(1)

    print("  mysql healthy OK")


if __name__ == "__main__":
    main()
