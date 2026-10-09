import pyzed.sl as sl
import cv2
import numpy as np
from PIL import Image

def compute_error(fx, fy, cx, cy, kp, img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=np.float64)
    dist_coeffs = kp

    tag_size = 0.17  # meters; actual tag side length

    aruco = cv2.aruco
    dictionary = aruco.getPredefinedDictionary(aruco.DICT_APRILTAG_36h11)
    detector = aruco.ArucoDetector(dictionary, aruco.DetectorParameters())
    corners, ids, _ = detector.detectMarkers(gray)

    image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    for corner in corners[i]:
        corner = corner.astype(int)
        image[corner[1]-5:corner[1]+5,corner[0]-5:corner[0]+5,0] = 255
        image[corner[1]-5:corner[1]+5,corner[0]-5:corner[0]+5,1] = 0
        image[corner[1]-5:corner[1]+5,corner[0]-5:corner[0]+5,2] = 0
    image = Image.fromarray(image)
    image.save("april_tag_error.png")

    if ids is None or len(ids) < 2:
        raise ValueError("At least two AprilTags must be detected")

    obj_pts = np.array([
        [-tag_size / 2,  tag_size / 2, 0],
        [ tag_size / 2,  tag_size / 2, 0],
        [ tag_size / 2, -tag_size / 2, 0],
        [-tag_size / 2, -tag_size / 2, 0]
    ], dtype=np.float64)

    centers = {}

    for corner, tag_id in zip(corners, ids.flatten()):
        ok, rvec, tvec = cv2.solvePnP(
            obj_pts, corner.reshape(4, 2), K, dist_coeffs,
            flags=cv2.SOLVEPNP_IPPE_SQUARE
        )
        if ok:
            centers[tag_id] = tvec.flatten()

    tag_ids = list(centers)
    for i in range(len(tag_ids)):
        for j in range(i + 1, len(tag_ids)):
            a, b = tag_ids[i], tag_ids[j]
            distance = np.linalg.norm(centers[a] - centers[b])
            print(f"Tags {a} and {b}: {distance:.4f} m")

    true_dist = tag_size + 0.1
    return np.linalg.norm(distance - true_dist)

def main():
    zed = sl.Camera()
    init_params = sl.InitParameters()
    init_params.camera_resolution = sl.RESOLUTION.AUTO
    init_params.camera_fps = 30

    err = zed.open(init_params)
    if err > sl.ERROR_CODE.SUCCESS:
        print("Camera Open : "+repr(err)+". Exit program.")
        exit()

    info = zed.get_camera_information().camera_configuration.calibration_parameters.left_cam
    fx = info.fx
    fy = info.fy
    cx = info.cx
    cy = info.cy
    kp = info.disto[0:5]

    image = sl.Mat()
    runtime_parameters = sl.RuntimeParameters()

    read_key = input("Press Enter to take image.")
    # Grab an image, a RuntimeParameters object must be given to grab()
    if zed.grab(runtime_parameters) <= sl.ERROR_CODE.SUCCESS:
        # A new image is available if grab() returns ERROR_CODE.SUCCESS or a WARNING (an error_code lower than ERROR_CODE.SUCCESS)
        zed.retrieve_image(image, sl.VIEW.LEFT)
        img = image.get_data().copy()[:,:,:3]
        timestamp = zed.get_timestamp(sl.TIME_REFERENCE.CURRENT)  # Get the timestamp at the time the image was captured
        print("Image resolution: {0} x {1} || Image timestamp: {2}\n".format(image.get_width(), image.get_height(),
            timestamp.get_milliseconds()))

    # Close the camera
    zed.close()

    mse = compute_error(fx, fy, cx, cy, kp, img)
    print(f"AprilTag localization error: {mse}")

if __name__ == "__main__":
    main()