#!/usr/bin/env python3
"""Print object coordinates in the fixed SLAM world frame R."""
import argparse
import json
from pathlib import Path
import time

import cv2
import numpy as np

if __package__:
    from .object_nav import ImageSub, TAG_IDS, compute_transform, tag_detector
else:
    from object_nav import ImageSub, TAG_IDS, compute_transform, tag_detector


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--object-json", type=Path, required=True)
    parser.add_argument("--tag-json", type=Path, required=True)
    parser.add_argument("--tag-path", type=Path, required=True, help="Reference tag image")
    return parser.parse_args()


def main(args):
    obj = json.loads(args.object_json.expanduser().read_text())
    intrinsics = json.loads(args.tag_json.expanduser().read_text())
    image = cv2.imread(str(args.tag_path.expanduser()))
    if image is None:
        raise ValueError(f"Cannot load {args.tag_path}")
    W_T_O = np.eye(4)
    W_T_O[:3, 3] = [obj[f"quest_{axis}"] for axis in "xyz"]
    if not np.isfinite(W_T_O).all():
        raise ValueError("Object coordinates must be finite")
    reference = tag_detector(image, intrinsics)
    if set(reference[0]) != TAG_IDS:
        raise ValueError("Reference image must contain tag IDs 0, 1, and 2")

    subscriber = ImageSub()
    try:
        deadline = time.monotonic() + 30.
        while time.monotonic() < deadline:
            data = subscriber.read()
            if data is not None:
                frame, pose, calibration = data
                live = tag_detector(frame["image"], calibration, pose)
                if set(live[0]) == TAG_IDS:
                    R_T_W = compute_transform(reference, live, intrinsics, calibration)
                    R_T_O = R_T_W @ W_T_O
                    print(f"x={R_T_O[0, 3]:.6f}, z={R_T_O[2, 3]:.6f}")
                    return
            time.sleep(.05)
        raise TimeoutError("No fresh live frame containing tag IDs 0, 1, and 2 within 30 seconds")
    finally:
        subscriber.stop()


if __name__ == "__main__":
    try:
        main(parse_args())
    except KeyboardInterrupt:
        raise SystemExit(130)
