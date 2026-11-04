import argparse
from datetime import datetime
from pathlib import Path
import signal
import time

from commlink import Subscriber, RPCClient
import numpy as np
from scipy.spatial.transform import Rotation as R
import threading
import rerun as rr

# Pub/sub topics from zed_pub_node.py
POSE_TOPIC = "zed/pose"
IMAGE_TOPIC = "zed/image"
DEPTH_TOPIC = "zed/depth"
PCD_TOPIC = "zed/pcd"
ZED_PUB_PORT = 6000

# RPC from SLAM -> Yor (follow_path via RPC)
YOR_RPC_HOST = "192.168.1.10" 
YOR_RPC_PORT = 5557

def xyzw_xyz_to_matrix(qt7):
    """
    qt7: [qx, qy, qz, qw, tx, ty, tz]
    """
    qt7 = np.asarray(qt7, dtype=np.float32).reshape(-1)
    if qt7.shape[0] < 7:
        raise ValueError(f"Expected 7 values [qx,qy,qz,qw,tx,ty,tz], got {qt7.shape}")
    q = qt7[:4]
    t = qt7[4:7]
    R_mat = R.from_quat(q).as_matrix().astype(np.float32)
    T = np.eye(4, dtype=np.float32)
    T[:3, :3] = R_mat
    T[:3, 3] = t
    return T

class ZedSub:
    """Wrapper around Subscriber to get the latest RGB image, depth map, pose, and point cloud from the ZED camera, with optional Z-up to Y-up conversion."""
    def __init__(self, host: str = "192.168.1.11", port: int = ZED_PUB_PORT, up_axis: str = "y"):
        self._up_axis = str(up_axis).lower()
        if self._up_axis not in ("y", "z"):
            self._up_axis = "y"
        self._zup_to_yup = np.array(
            [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, -1.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype=np.float32,
        )
        topics = [IMAGE_TOPIC, DEPTH_TOPIC, POSE_TOPIC, PCD_TOPIC]
        self._sub = Subscriber(host=host, port=port, topics=topics)
        self._sub_lock = threading.Lock()

    def _zup_to_yup_transform(self, T: np.ndarray) -> np.ndarray:
        """Convert a 4x4 transformation matrix from Z-up to Y-up by applying the appropriate rotation."""
        return self._zup_to_yup @ T @ self._zup_to_yup.T

    def _zup_to_yup_pose(self, pose_qt: np.ndarray) -> np.ndarray:
        """Convert pose from Z-up to Y-up by applying the appropriate transformation. Expects pose_qt as [qx, qy, qz, qw, tx, ty, tz]."""
        pose_qt = np.asarray(pose_qt, dtype=np.float32).reshape(-1)
        if pose_qt.size < 7:
            return pose_qt
        quat = pose_qt[:4]
        trans = pose_qt[4:7]
        T = np.eye(4, dtype=np.float32)
        T[:3, :3] = R.from_quat(quat).as_matrix().astype(np.float32)
        T[:3, 3] = trans
        T = self._zup_to_yup_transform(T)
        quat_y = R.from_matrix(T[:3, :3]).as_quat().astype(np.float32)
        trans_y = T[:3, 3].astype(np.float32)
        return np.concatenate([quat_y, trans_y])
    
    def _sub_get(self, topic):
        """Thread-safe get for subscriber topics."""
        with self._sub_lock:
            return self._sub[topic]

    def _zup_to_yup_points(self, pcd):
        """Convert point cloud from Z-up to Y-up by swapping axes. Expects shape (..., 3) or (..., N) with XYZ in the first 3 channels."""
        arr = np.asarray(pcd)
        if arr.ndim < 2 or arr.shape[-1] < 3:
            return arr
        xyz = arr[..., :3].astype(np.float32, copy=False)
        x = xyz[..., 0]
        y = xyz[..., 1]
        z = xyz[..., 2]
        xyz_yup = np.stack([x, z, -y], axis=-1)
        if arr.shape[-1] > 3:
            out = arr.copy()
            out[..., :3] = xyz_yup
            return out
        return xyz_yup

    def stop(self):
        self._sub.stop()
    
    def ready(self) -> bool:
        """Return True once at least the pose topic has been received."""
        ready_attr = getattr(self._sub, "ready", None)
        if callable(ready_attr):
            return bool(ready_attr())
        if ready_attr is not None:
            return bool(ready_attr)

        try:
            pose_msg = self._sub_get(POSE_TOPIC)
        except Exception:
            return False
        return pose_msg is not None

    def get_rgb_depth_pose(self):
        """Get the latest RGB image, depth map, and pose. Pose is returned as [qx, qy, qz, qw, tx, ty, tz]."""
        img_msg = self._sub_get(IMAGE_TOPIC)
        depth_msg = self._sub_get(DEPTH_TOPIC)
        pose_msg = self._sub_get(POSE_TOPIC)

        if img_msg is None or depth_msg is None or pose_msg is None:
            raise RuntimeError("ZedSub not ready yet")
        
        image_rgb = img_msg["image"]
        depth_m = depth_msg["depth"]
        pose_qt = pose_msg[7:14]
        if self._up_axis == "z":
            pose_qt = self._zup_to_yup_pose(pose_qt)

        return image_rgb, depth_m, pose_qt
    
    def get_pcd_pose(self):
        """Get the latest point cloud and pose. Pose is returned as [qx, qy, qz, qw, tx, ty, tz]."""
        pcd_msg = self._sub_get(PCD_TOPIC)
        pose_msg = self._sub_get(POSE_TOPIC)

        if pcd_msg is None or pose_msg is None:
            raise RuntimeError("ZedSub not ready yet or Points not being streamed")
        
        pcd = pcd_msg["points"]
        pose_qt = pose_msg[7:14]  # Pose as [qx, qy, qz, qw, tx, ty, tz]
        if self._up_axis == "z":
            pose_qt = self._zup_to_yup_pose(pose_qt)
            pcd = self._zup_to_yup_points(pcd)
        return pcd, pose_qt
    
    def get_pose(self):
        """Get the latest pose as (translation, yaw, full_transform). Translation is (x, z) in world coordinates, yaw is in radians."""
        pose_msg = self._sub_get(POSE_TOPIC)
        base_quat = pose_msg[0:7]
        base_transform = xyzw_xyz_to_matrix(base_quat)
        if self._up_axis == "z":
            base_transform = self._zup_to_yup_transform(base_transform)
        translation = base_transform[:3, 3].astype(np.float32)
        yaw = float(np.arctan2(base_transform[0, 2], base_transform[2, 2]))
        return translation, yaw, base_transform

def parse_args():
    parser = argparse.ArgumentParser(description="Record ZED data to a Rerun file.")
    parser.add_argument(
        "--save-dir", type=str, default="rerun", required=True,
        help="Directory for the .rrd recording (required; default: rerun).",
    )

    def boolean(value):
        if value.lower() in ("true", "1", "yes"):
            return True
        if value.lower() in ("false", "0", "no"):
            return False
        raise argparse.ArgumentTypeError("Expected true or false")

    for name in ("pcd", "pose", "depth"):
        parser.add_argument(
            f"--{name}", type=boolean, nargs="?", const=True, default=True,
            help=f"Save {name} data (true/false; default: true).",
        )
    return parser.parse_args()


def main(args):
    save_dir = Path(args.save_dir).expanduser()
    save_dir.mkdir(parents=True, exist_ok=True)
    recording_path = save_dir / f"zed_{datetime.now():%Y%m%d_%H%M%S_%f}.rrd"
    subscriber = None
    previous_sigterm = None

    def request_shutdown(signum, frame):
        raise KeyboardInterrupt

    rr.init("zed_recording", spawn=False)
    try:
        # Stream to disk throughout collection so recordings need not fit in RAM.
        rr.save(str(recording_path))
        previous_sigterm = signal.signal(signal.SIGTERM, request_shutdown)
        subscriber = ZedSub(host="127.0.0.1", port=6000, up_axis="y")
        print("ZED subscriber initialized; listening for published data on 127.0.0.1:6000.", flush=True)
        print(f"Saving Rerun recording to {recording_path}. Press Ctrl+C to stop.", flush=True)
        rr.log("world", rr.ViewCoordinates.RIGHT_HAND_Y_UP, static=True)
        last_messages = {}
        frame = 0
        while True:
            rr.set_time_sequence("frame", frame)
            # Read topics independently: a missing point cloud must not block poses/depth.
            for enabled, topic in (
                (args.pcd, PCD_TOPIC),
                (args.pose, POSE_TOPIC),
                (args.depth, DEPTH_TOPIC),
            ):
                if not enabled:
                    continue
                message = subscriber._sub_get(topic)
                if message is None or message is last_messages.get(topic):
                    continue
                if topic == PCD_TOPIC:
                    points = np.asarray(message["points"])
                    xyz = points[..., :3].reshape(-1, 3)
                    xyz = xyz[np.isfinite(xyz).all(axis=1)]
                    rr.log("world/points", rr.Points3D(xyz))
                elif topic == POSE_TOPIC:
                    transform = xyzw_xyz_to_matrix(message[7:14])
                    rr.log(
                        "world/camera",
                        rr.Transform3D(translation=transform[:3, 3], mat3x3=transform[:3, :3]),
                    )
                    # The subscriber carries no calibration. This 60-degree
                    # vertical FOV and 16:9 aspect are visualization estimates.
                    rr.log(
                        "world/camera/image",
                        rr.Pinhole(
                            fov_y=np.deg2rad(60.0), aspect_ratio=16 / 9,
                            camera_xyz=rr.ViewCoordinates.RUB,
                        ),
                    )
                else:
                    rr.log(
                        "world/camera/image/depth",
                        rr.DepthImage(np.asarray(message["depth"]), meter=1.0),
                    )
                last_messages[topic] = message
            frame += 1
            time.sleep(0.03)
    except KeyboardInterrupt:
        print("Stopping ZED recording.", flush=True)
    finally:
        try:
            if subscriber is not None:
                subscriber.stop()
        finally:
            # Closing the file sink flushes queued recording data, even on errors.
            rr.disconnect()
            if previous_sigterm is not None:
                signal.signal(signal.SIGTERM, previous_sigterm)


if __name__ == "__main__":
    main(parse_args())
