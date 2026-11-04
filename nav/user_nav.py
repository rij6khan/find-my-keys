#!/usr/bin/env python3
"""Send terminal-entered world-frame goals to slam_fmk.py."""
import math
import os
import signal
import time
import uuid

from commlink import Publisher, Subscriber


class GoalPub:
    def __init__(self):
        self.pub = Publisher("*", port=6001)
        self.status = Subscriber(
            host=os.getenv("FMK_SLAM_HOST", "127.0.0.1"),
            port=6002, topics=["fmk/status"])
        self.goal_id = None

    def navigate(self, x, z):
        self.goal_id = uuid.uuid4().hex
        goal = {"id": self.goal_id, "x": x, "z": z}
        deadline = time.monotonic() + 300
        previous_state = None
        while time.monotonic() < deadline:
            self.pub.publish("fmk/goal", goal)
            status = self.status["fmk/status"]
            if status is not None and status.get("id") == self.goal_id:
                state = status.get("state")
                if state != previous_state:
                    print(f"SLAM: {state}", flush=True)
                    previous_state = state
                if state == "arrived":
                    self.goal_id = None
                    return
                if state == "failed":
                    raise RuntimeError(status.get("error") or "Navigation failed")
            time.sleep(.2)
        raise TimeoutError("Navigation did not finish within 300 seconds")

    def cancel(self):
        if self.goal_id is not None:
            for _ in range(5):
                self.pub.publish("fmk/goal", {"id": self.goal_id, "cancel": True})
                time.sleep(.1)
            self.goal_id = None

    def stop(self):
        try:
            self.cancel()
        finally:
            self.status.stop()


def main():
    print("Enter SLAM world coordinates in meters: x z (example: 1.5 -0.5).")
    print("Enter q to quit; Ctrl+C cancels navigation and exits.")
    goals = None

    def interrupted(signum, frame):
        raise KeyboardInterrupt

    old_handler = signal.signal(signal.SIGTERM, interrupted)
    try:
        while True:
            text = input("Goal x z > ").strip()
            if text.lower() in ("q", "quit", "exit"):
                break
            try:
                x, z = map(float, text.split())
                if not all(map(math.isfinite, (x, z))):
                    raise ValueError
            except ValueError:
                print("Enter two finite numbers separated by a space, or q to quit.")
                continue
            if goals is None:
                goals = GoalPub()
            try:
                goals.navigate(x, z)
            except (RuntimeError, TimeoutError) as error:
                print(error)
                goals.cancel()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
    finally:
        try:
            if goals is not None:
                goals.stop()
        finally:
            signal.signal(signal.SIGTERM, old_handler)


if __name__ == "__main__":
    main()
