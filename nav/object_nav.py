#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import signal
import time
import uuid

import cv2
import numpy as np
from scipy.spatial.transform import Rotation
from commlink import Publisher, Subscriber, RPCClient

TAG_IDS = {0, 1, 2}
TAG_POINTS = np.array([[-.085, .085, 0], [.085, .085, 0],
                       [.085, -.085, 0], [-.085, -.085, 0]])
ZED_HOST = os.getenv("FMK_ZED_HOST", "127.0.0.1")
YOR_HOST = os.getenv("FMK_YOR_HOST", "localhost")
GOAL_TOPIC = "fmk/goal"
STATUS_TOPIC = "fmk/status"


def pose_matrix(pose):
    matrix = np.eye(4)
    matrix[:3, :3] = Rotation.from_quat(pose[:4]).as_matrix()
    matrix[:3, 3] = pose[4:7]
    return matrix


def tag_detector(image, intrinsics, pose=None):
    detector = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11),
        cv2.aruco.DetectorParameters())
    corners, ids, _ = detector.detectMarkers(image)
    found = {} if ids is None else {
        int(i): c.reshape(4, 2).astype(np.float64)
        for i, c in zip(ids.flatten(), corners) if int(i) in TAG_IDS}
    return found, image, pose


def compute_transform(reference, live, intrinsics, calibration):
    """Return R_T_W using all twelve tag corners; R is the fixed SLAM world."""
    ref_corners, _, _ = reference
    live_corners, _, pose = live
    if set(ref_corners) != TAG_IDS or set(live_corners) != TAG_IDS:
        raise ValueError("Both images must contain tag IDs 0, 1, and 2")
    prefix = "image" if "image_fx" in intrinsics else "sensor"
    K_C = np.array([[intrinsics[f"{prefix}_fx"], 0, intrinsics[f"{prefix}_cx"]],
                      [0, intrinsics[f"{prefix}_fy"], intrinsics[f"{prefix}_cy"]],
                      [0, 0, 1]], dtype=float)
    if prefix == "sensor":
        K_C[0, 2] -= float(intrinsics.get("crop_x", 0.))
        K_C[1, 2] -= float(intrinsics.get("crop_y", 0.))
    D_C = np.asarray(intrinsics.get("distortion", np.zeros(5)), dtype=float)
    points = []
    for tag_id in sorted(TAG_IDS):
        ok, rvec, tvec = cv2.solvePnP(TAG_POINTS, ref_corners[tag_id], K_C, D_C,
                                     flags=cv2.SOLVEPNP_IPPE_SQUARE)
        if not ok or tvec[2, 0] <= 0:
            raise RuntimeError(f"Reference pose failed for tag {tag_id}")
        points.extend(TAG_POINTS @ cv2.Rodrigues(rvec)[0].T + tvec.reshape(3))
    K_Z = np.asarray(calibration["matrix"], dtype=float)
    D_Z = np.asarray(calibration["distortion"], dtype=float)
    pixels = np.concatenate([live_corners[i] for i in sorted(TAG_IDS)])
    points = np.asarray(points)
    ok, rvec, tvec, inliers = cv2.solvePnPRansac(
        points, pixels, K_Z, D_Z, iterationsCount=200,
        reprojectionError=3.0, confidence=.999, flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok or inliers is None or any(
            not np.any((inliers.flatten() // 4) == i) for i in range(3)):
        raise RuntimeError("PnP-RANSAC did not retain all three tags")
    idx = inliers.flatten()
    rvec, tvec = cv2.solvePnPRefineLM(points[idx], pixels[idx], K_Z, D_Z, rvec, tvec)
    Zopt_T_Copt = np.eye(4)
    Zopt_T_Copt[:3, :3] = cv2.Rodrigues(rvec)[0]
    Zopt_T_Copt[:3, 3] = tvec.flatten()
    if np.any((points @ Zopt_T_Copt[:3, :3].T + tvec.reshape(3))[:, 2] <= 0):
        raise RuntimeError("PnP placed tags behind the camera")

    def components(value, keys):
        return [value[k] for k in keys] if isinstance(value, dict) else value

    W_T_C = np.eye(4)
    W_T_C[:3, :3] = Rotation.from_quat(components(
        intrinsics["camera_world_quaternion"], "xyzw")).as_matrix()
    W_T_C[:3, 3] = components(intrinsics["camera_world_position"], "xyz")
    # Unity camera: right/up/forward; OpenCV: right/down/forward.
    Copt_T_C = np.diag([1., -1., 1., 1.])
    # ZED RIGHT_HANDED_Y_UP: right/up/backward.
    Z_T_Zopt = np.diag([1., -1., -1., 1.])
    Z_T_C = Z_T_Zopt @ Zopt_T_Copt @ Copt_T_C
    R_T_Z = pose_matrix(pose[7:14])
    R_T_W = R_T_Z @ Z_T_C @ np.linalg.inv(W_T_C)
    return R_T_W


class ImageSub:
    def __init__(self):
        self.sub = Subscriber(host=ZED_HOST, port=6000,
                              topics=["zed/image", "zed/pose", "zed/calibration"])

    def read(self):
        image, pose, calibration = (self.sub[t] for t in
                                    ("zed/image", "zed/pose", "zed/calibration"))
        if image is None or pose is None or calibration is None:
            return None
        now = time.time_ns()
        if now - image["timestamp"] > 1_000_000_000 or abs(image["timestamp"] - pose[18]) > 100_000_000:
            return None
        return image, pose, calibration

    def stop(self):
        self.sub.stop()


class GoalPub:
    def __init__(self):
        self.pub = Publisher("*", port=6001)
        self.status = Subscriber(host=os.getenv("FMK_SLAM_HOST", "127.0.0.1"),
                                 port=6002, topics=[STATUS_TOPIC])
        self.id = uuid.uuid4().hex

    def navigate(self, point):
        goal = {"id": self.id, "x": float(point[0]), "z": float(point[2])}
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            self.pub.publish(GOAL_TOPIC, goal)
            status = self.status[STATUS_TOPIC]
            if status is not None and status.get("id") == self.id:
                if status["state"] == "arrived":
                    return
                if status["state"] == "failed":
                    raise RuntimeError(status.get("error", "Navigation failed"))
            time.sleep(.2)
        raise TimeoutError("Navigation did not finish within 300 seconds")

    def stop(self):
        for _ in range(3):
            self.pub.publish(GOAL_TOPIC, {"id": self.id, "cancel": True})
            time.sleep(.1)
        self.status.stop()


class Rotator:
    def __init__(self):
        self.client = RPCClient(YOR_HOST, 5557)

    def rotate(self):
        self.client.set_base_velocity([0., 0., .2])

    def halt(self):
        self.client.set_base_velocity([0., 0., 0.])

    def restore(self, position):
        self.halt()
        self.client.follow_path([(float(position[0]), float(position[2]))])


def parse_args():
    parser = argparse.ArgumentParser(description="Navigate to an object using three AprilTags")
    parser.add_argument("--tag-path", required=True)
    parser.add_argument("--int-json", required=True)
    return parser.parse_args()


def main(args):
    image = cv2.imread(args.tag_path)
    if image is None:
        raise ValueError(f"Cannot load {args.tag_path}")
    intrinsics = json.loads(Path(args.int_json).read_text())
    obj = json.loads(Path("object.json").read_text())
    W_T_O = np.eye(4)
    W_T_O[:3, 3] = [obj[f"quest_{axis}"] for axis in "xyz"]
    if not np.isfinite(W_T_O).all():
        raise ValueError("Object coordinates must be finite")
    reference = tag_detector(image, intrinsics)
    if set(reference[0]) != TAG_IDS:
        raise ValueError("Reference image must contain all three tags")
    subscriber = ImageSub()
    rotator = Rotator()
    goals = None
    last_pose = None

    def interrupted(signum, frame):
        raise KeyboardInterrupt

    old_handler = signal.signal(signal.SIGTERM, interrupted)
    try:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            data = subscriber.read()
            if data is None:
                rotator.halt()
                time.sleep(.1)
                continue
            frame, last_pose, calibration = data
            live = tag_detector(frame["image"], calibration, last_pose)
            if set(live[0]) == TAG_IDS:
                rotator.halt()
                break
            rotator.rotate()
            time.sleep(.05)
        else:
            raise TimeoutError("All three AprilTags were not visible within 120 seconds")
        R_T_W = compute_transform(reference, live, intrinsics, calibration)
        R_T_O = R_T_W @ W_T_O
        print(f"Object in SLAM world frame: {R_T_O[:3, 3]}")
        goals = GoalPub()
        goals.navigate(R_T_O[:3, 3])
        print("Arrived at object goal")
    finally:
        try:
            try:
                if goals is not None:
                    goals.stop()
            finally:
                rotator.halt()
            data = subscriber.read()
            if data is not None:
                rotator.restore(data[1][4:7])
            elif last_pose is not None:
                rotator.restore(last_pose[4:7])
            else:
                rotator.client.follow_path(None)
        finally:
            subscriber.stop()
            signal.signal(signal.SIGTERM, old_handler)


if __name__ == "__main__":
    main(parse_args())
