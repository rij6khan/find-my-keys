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
    """Return robot-base-from-Unity-world using all twelve tag corners."""
    ref_corners, _, _ = reference
    live_corners, _, pose = live
    if set(ref_corners) != TAG_IDS or set(live_corners) != TAG_IDS:
        raise ValueError("Both images must contain tag IDs 0, 1, and 2")
    prefix = "image" if "image_fx" in intrinsics else "sensor"
    k_ref = np.array([[intrinsics[f"{prefix}_fx"], 0, intrinsics[f"{prefix}_cx"]],
                      [0, intrinsics[f"{prefix}_fy"], intrinsics[f"{prefix}_cy"]],
                      [0, 0, 1]], dtype=float)
    d_ref = np.asarray(intrinsics.get("distortion", np.zeros(5)), dtype=float)
    points = []
    for tag_id in sorted(TAG_IDS):
        ok, rvec, tvec = cv2.solvePnP(TAG_POINTS, ref_corners[tag_id], k_ref, d_ref,
                                     flags=cv2.SOLVEPNP_IPPE_SQUARE)
        if not ok or tvec[2, 0] <= 0:
            raise RuntimeError(f"Reference pose failed for tag {tag_id}")
        points.extend(TAG_POINTS @ cv2.Rodrigues(rvec)[0].T + tvec.reshape(3))
    k_live = np.asarray(calibration["matrix"], dtype=float)
    d_live = np.asarray(calibration["distortion"], dtype=float)
    pixels = np.concatenate([live_corners[i] for i in sorted(TAG_IDS)])
    points = np.asarray(points)
    ok, rvec, tvec, inliers = cv2.solvePnPRansac(
        points, pixels, k_live, d_live, iterationsCount=200,
        reprojectionError=3.0, confidence=.999, flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok or inliers is None or any(
            not np.any((inliers.flatten() // 4) == i) for i in range(3)):
        raise RuntimeError("PnP-RANSAC did not retain all three tags")
    idx = inliers.flatten()
    rvec, tvec = cv2.solvePnPRefineLM(points[idx], pixels[idx], k_live, d_live, rvec, tvec)
    optical_from_ref = np.eye(4)
    optical_from_ref[:3, :3] = cv2.Rodrigues(rvec)[0]
    optical_from_ref[:3, 3] = tvec.flatten()
    if np.any((points @ optical_from_ref[:3, :3].T + tvec.reshape(3))[:, 2] <= 0):
        raise RuntimeError("PnP placed tags behind the camera")

    def components(value, keys):
        return [value[k] for k in keys] if isinstance(value, dict) else value

    unity_world_from_camera = np.eye(4)
    unity_world_from_camera[:3, :3] = Rotation.from_quat(components(
        intrinsics["camera_world_quaternion"], "xyzw")).as_matrix()
    unity_world_from_camera[:3, 3] = components(intrinsics["camera_world_position"], "xyz")
    # Unity camera: right/up/forward; OpenCV: right/down/forward.
    ref_optical_from_unity_camera = np.diag([1., -1., 1., 1.])
    # ZED RIGHT_HANDED_Y_UP: right/up/backward.
    zed_from_optical = np.diag([1., -1., -1., 1.])
    world_from_camera = pose_matrix(pose[7:14])
    world_from_base = pose_matrix(pose[:7])
    return (np.linalg.inv(world_from_base) @ world_from_camera @ zed_from_optical
            @ optical_from_ref @ ref_optical_from_unity_camera
            @ np.linalg.inv(unity_world_from_camera))


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
    point = np.array([obj[f"quest_{axis}"] for axis in "xyz"] + [1.], dtype=float)
    if not np.isfinite(point).all():
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
        transform = compute_transform(reference, live, intrinsics, calibration)
        local_point = transform @ point
        world_point = pose_matrix(last_pose[:7]) @ local_point
        print(f"Object in robot frame: {local_point[:3]}")
        goals = GoalPub()
        goals.navigate(world_point)
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
