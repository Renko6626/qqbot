import os
import signal


def restart_process() -> None:
    """Terminate normally; the container's restart policy starts a new process."""
    os.kill(os.getpid(), signal.SIGTERM)
