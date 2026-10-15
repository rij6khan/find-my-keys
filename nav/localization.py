import pyzed.sl as sl
import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation as R
import argparse
import json
import cv2

def localize(imgs, intrinsics):
    if imgs[0] is None or imgs[1] is None:
        raise RuntimeError("Could not load input images.")

    tag_size = 0.17
    half = tag_size / 2

    object_points = np.array([
        [-half, half, 0],
        [half, half, 0],
        [half, -half, 0],
        [-half, -half, 0]
    ], dtype=np.float64)

    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())

    transforms = {}
    target_ids = [0, 1]

    for i, (image, intr) in enumerate(zip(imgs, intrinsics)):
        fx, fy, cx, cy, kp = intr

        K = np.array([
            [fx, 0, cx],
            [0, fy, cy],
            [0, 0, 1]
        ], dtype=np.float64)

        dist_coeffs = np.array([kp], dtype=np.float64)

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = detector.detectMarkers(gray)

        if ids is None:
            raise RuntimeError(f"No AprilTags detected in image {i}.")

        ids = ids.flatten()
        marked_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        transforms[i] = {}

        for tag_corners, tag_id in zip(corners, ids):
            pts = tag_corners.reshape(4, 2)

            for x, y in pts.astype(int):
                marked_image[max(0, y-5):y+5, max(0, x-5):x+5] = [255, 0, 0]

            if tag_id not in target_ids:
                continue

            success, rvec, tvec = cv2.solvePnP(
                object_points,
                pts,
                K,
                dist_coeffs,
                flags=cv2.SOLVEPNP_IPPE_SQUARE
            )

            if not success:
                raise RuntimeError(f"solvePnP failed for tag ID {tag_id} in image {i}.")

            R, _ = cv2.Rodrigues(rvec)

            T = np.eye(4)
            T[:3, :3] = R
            T[:3, 3] = tvec.flatten()

            transforms[i][tag_id] = T

        Image.fromarray(marked_image).save(f"april_tag_{i}.png")

        missing = set(target_ids) - transforms[i].keys()
        if missing:
            raise RuntimeError(f"AprilTag IDs {sorted(missing)} not detected in image {i}.")

    return (
        transforms[0][0],
        transforms[0][1],
        transforms[1][0],
        transforms[1][1]
    )

def compute_error(q_T_tag0, q_T_tag1, y_T_tag0, y_T_tag1):
    y_T_q = y_T_tag0 @ np.linalg.inv(q_T_tag0)
    y_T_tag1_test = y_T_q @ q_T_tag1
    T_error = np.linalg.inv(y_T_tag1_test) @ y_T_tag1
    
    t_error = T_error[0:3, 3]
    translation_error = np.linalg.norm(t_error)
    
    R_error = T_error[0:3, 0:3]
    trace = np.clip((np.trace(R_error) - 1.0) / 2.0, -1.0, 1.0)
    rotation_error_rad = np.arccos(trace)
    rotation_error_deg = np.degrees(rotation_error_rad)
    
    return translation_error, rotation_error_deg

def plot(T21, t2):
    t = T21 @ t2

def main(args):
    quest_im = np.array(Image.open(args.img_path))
    with open(args.json_path, 'r', encoding='utf-8') as file:
        quest_data = json.load(file)
    quest_fx = quest_data["sensor_fx"]
    quest_fy = quest_data["sensor_fy"]
    quest_cx = quest_data["sensor_cx"]
    quest_cy = quest_data["sensor_cy"]
    quest_disto = np.zeros(5)
    quest_intrinsics = [quest_fx, quest_fy, quest_cx, quest_cy, quest_disto]
    quest_position = quest_data["camera_world_position"]
    quest_orientation = quest_data["camera_world_quaternion"]
    quest_rot = R.from_quat(quest_orientation).as_matrix()
    w_T_q = np.eye(4)
    w_T_q[:3, :3] = quest_rot
    w_T_q[:3, 3] = quest_position

    zed = sl.Camera()
    init_params = sl.InitParameters()
    init_params.camera_resolution = sl.RESOLUTION.AUTO
    init_params.camera_fps = 30

    err = zed.open(init_params)
    if err > sl.ERROR_CODE.SUCCESS:
        print("Camera Open : "+repr(err)+". Exit program.")
        exit()

    intrinsics = []
    intrinsics.append(quest_intrinsics)
    info = zed.get_camera_information().camera_configuration.calibration_parameters.left_cam
    intrinsics.append([info.fx, info.fy, info.cx, info.cy, info.disto[0:5]])

    # Capture 50 frames and stop
    imgs = []
    imgs.append(quest_im)
    image = sl.Mat()
    runtime_parameters = sl.RuntimeParameters()

    while(True):
        read_key = input("Press any key to take image, press q to quit.")
        if read_key == 'q':
            break
        # Grab an image, a RuntimeParameters object must be given to grab()
        if zed.grab(runtime_parameters) <= sl.ERROR_CODE.SUCCESS:
            # A new image is available if grab() returns ERROR_CODE.SUCCESS or a WARNING (an error_code lower than ERROR_CODE.SUCCESS)
            zed.retrieve_image(image, sl.VIEW.LEFT)
            imgs.append(image.get_data().copy()[:,:,:3])
            timestamp = zed.get_timestamp(sl.TIME_REFERENCE.CURRENT)  # Get the timestamp at the time the image was captured
            print("Image resolution: {0} x {1} || Image timestamp: {2}\n".format(image.get_width(), image.get_height(),
                timestamp.get_milliseconds()))

        q_T_tag0, q_T_tag1, y_T_tag0, y_T_tag1 = localize(imgs, intrinsics)
        trans_error, rot_error = compute_error(q_T_tag0, q_T_tag1, y_T_tag0, y_T_tag1)
        print(f"\nTranslation error: {trans_error} m")
        print(f"Rotation error: {rot_error} deg\n")
        imgs.pop()

    # Close the camera
    zed.close()

def parse():
    parser = argparse.ArgumentParser()
    parser.add_argument("--img_path", type=str, required=True, default="quest_tag.jpg")
    parser.add_argument("--json_path", type=str, required=True, default="quest_cam.json")
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    args = parse()
    main(args)