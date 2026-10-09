import pyzed.sl as sl
import cv2
import numpy as np
from PIL import Image
import apriltag

def compute_error(fx, fy, cx, cy, img):
    camera_matrix = np.array([[fx, 0, cx],
                          [0, fy, cy],
                          [0,  0,  1]], dtype=np.float32)
    dist_coeffs = np.zeros((5, 1)) # Assuming minimal distortion or pre-undistorted image
    tag_size = 0.165  # Size of the tag square in meters (e.g., 16.5 cm)

    # 2. Load image and detect AprilTags
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    options = apriltag.DetectorOptions(families="tag36h11")
    detector = apriltag.Detector(options)
    results = detector.detect(gray)

    # We need at least two tags to find the distance between them
    if len(results) >= 2:
        poses = []
        
        for r in results[:2]:  # Take the first two detected tags
            # Define 3D object points of the tag corners in its own local coordinate system
            obj_points = np.array([
                [-tag_size / 2,  tag_size / 2, 0],
                [ tag_size / 2,  tag_size / 2, 0],
                [ tag_size / 2, -tag_size / 2, 0],
                [-tag_size / 2, -tag_size / 2, 0]
            ], dtype=np.float32)
            
            # Image points from AprilTag detection corners
            img_points = np.array(r.corners, dtype=np.float32)
            
            # Estimate the 3D pose of the tag relative to the camera
            _, rvec, tvec = cv2.solvePnP(obj_points, img_points, camera_matrix, dist_coeffs)
            poses.append(tvec)
        
        # 3. Calculate Euclidean distance between xthe two 3D translation vectors
        t1, t2 = poses[0], poses[1]
        distance_3d = np.linalg.norm(t1 - t2)
        
        print(f"Real-world distance between tags: {distance_3d:.4f} meters")
    else:
        print("Could not detect at least two AprilTags.")

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

    mse = compute_error(fx, fy, cx, cy, img)

if __name__ == "__main__":
    main()