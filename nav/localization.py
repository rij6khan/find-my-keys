import pyzed.sl as sl
import cv2
import numpy as np
from PIL import Image

def detect_tag_pose(image, fx, fy, cx, cy, kp):
    """
    Detect an AprilTag and estimate the camera pose relative
    to the tag.

    Returns:
        R_cam_tag : 3x3 rotation matrix
        t_cam_tag : 3x1 translation vector

    Convention:
        X_cam = R_cam_tag @ X_tag + t_cam_tag
    """

    # AprilTag family
    TAG_FAMILY = cv2.aruco.DICT_APRILTAG_36h11

    # Physical side length of the AprilTag, in meters
    TAG_SIZE = 0.1

    # Camera intrinsics
    # Replace these with your calibrated camera parameters.
    K = np.array([
        [fx,  0, cx],
        [ 0, fy, cy],
        [ 0,  0,  1]
    ], dtype=np.float64)

    DIST_COEFFS = np.array([
        kp
    ], dtype=np.float64)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    dictionary = cv2.aruco.getPredefinedDictionary(TAG_FAMILY)

    parameters = cv2.aruco.DetectorParameters()

    detector = cv2.aruco.ArucoDetector(dictionary, parameters)

    corners, ids, _ = detector.detectMarkers(gray)

    if ids is None:
        raise RuntimeError("No AprilTag detected.")

    # Use the first detected tag.
    # For multiple tags, select the desired ID here.
    tag_corners = corners[0].reshape(4, 2)

    # Tag coordinate system:
    #
    #       0 -------- 1
    #       |          |
    #       |          |
    #       3 -------- 2
    #
    half = TAG_SIZE / 2.0

    object_points = np.array([
        [-half,  half, 0],
        [ half,  half, 0],
        [ half, -half, 0],
        [-half, -half, 0]
    ], dtype=np.float64)

    success, rvec, tvec = cv2.solvePnP(
        object_points,
        tag_corners,
        K,
        DIST_COEFFS,
        flags=cv2.SOLVEPNP_IPPE_SQUARE
    )

    if not success:
        raise RuntimeError("solvePnP failed.")

    R_cam_tag, _ = cv2.Rodrigues(rvec)

    return R_cam_tag, tvec.reshape(3, 1), tag_corners


# ------------------------------------------------------------
# Relative transformation
# ------------------------------------------------------------

def relative_transform(R1, t1, R2, t2):
    """
    Compute transformation from camera 1 coordinates
    to camera 2 coordinates.

    Given:

        X_cam1 = R1 @ X_tag + t1
        X_cam2 = R2 @ X_tag + t2

    We want:

        X_cam2 = R21 @ X_cam1 + t21

    Therefore:

        R21 = R2 @ R1.T
        t21 = t2 - R21 @ t1
    """

    R21 = R2 @ R1.T
    t21 = t2 - R21 @ t1

    T21 = np.eye(4)

    T21[:3, :3] = R21
    T21[:3, 3] = t21.flatten()

    return T21

def localize(imgs, fx, fy, cx, cy, kp):
    if imgs[0] is None or imgs[1] is None:
        raise RuntimeError("Could not load input images.")


    # Pose of camera 1 relative to AprilTag
    R1, t1, corners1 = detect_tag_pose(imgs[0], fx, fy, cx, cy, kp)

    # Pose of camera 2 relative to AprilTag
    R2, t2, corners2 = detect_tag_pose(imgs[1], fx, fy, cx, cy, kp)

    # Save image with corners marked
    corners = [corners1, corners2]
    for i, image in enumerate(imgs):
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        for corner in corners[i]:
            corner = corner.astype(int)
            image[corner[1]-5:corner[1]+5,corner[0]-5:corner[0]+5,0] = 255
            image[corner[1]-5:corner[1]+5,corner[0]-5:corner[0]+5,1] = 0
            image[corner[1]-5:corner[1]+5,corner[0]-5:corner[0]+5,2] = 0
        img = Image.fromarray(image)
        img.save(f"april_tag_{i}.png")

    # Transformation from camera 1 -> camera 2
    T21 = relative_transform(R1, t1, R2, t2)


    print("Rotation matrix:")
    print(T21[:3, :3])

    print("\nTranslation vector [m]:")
    print(T21[:3, 3])

    print("\n4x4 transformation matrix:")
    print(T21)

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

    # Capture 50 frames and stop
    i = 0
    imgs = []
    image = sl.Mat()
    runtime_parameters = sl.RuntimeParameters()
    while(i<2):
        read_key = input("Press Enter to take image.")
        # Grab an image, a RuntimeParameters object must be given to grab()
        if zed.grab(runtime_parameters) <= sl.ERROR_CODE.SUCCESS:
            # A new image is available if grab() returns ERROR_CODE.SUCCESS or a WARNING (an error_code lower than ERROR_CODE.SUCCESS)
            zed.retrieve_image(image, sl.VIEW.LEFT)
            imgs.append(image.get_data().copy()[:,:,:3])
            timestamp = zed.get_timestamp(sl.TIME_REFERENCE.CURRENT)  # Get the timestamp at the time the image was captured
            print("Image resolution: {0} x {1} || Image timestamp: {2}\n".format(image.get_width(), image.get_height(),
                timestamp.get_milliseconds()))
            i = i + 1

    # Close the camera
    zed.close()

    localize(imgs, fx, fy, cx, cy, kp)

if __name__ == "__main__":
    main()