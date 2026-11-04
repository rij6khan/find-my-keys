# This file captures the point cloud of the scene using the ZED camera and saves it to a .ply file. 
# It also saves the camera pose (translation + orientation) at the time of capture to a .npy file. 
# The point cloud is captured when the user presses the 'c' key, and the program can be exited by pressing the 'q' key.
import pyzed.sl as sl
import cv2
import numpy as np
import open3d as o3d
from PIL import Image
from ultralytics import YOLO #for object detection+segmentation
import os

#replace with HMD model weights for integration?
seg_model = YOLO(os.path.join("../find-my-keys/manipulation/", "yolov9c-seg.pt")) 

#initialize the ZED camera + config parameters
zed = sl.Camera()
init_params = sl.InitParameters()
init_params.camera_resolution = sl.RESOLUTION.AUTO
init_params.coordinate_units = sl.UNIT.MILLIMETER
init_params.coordinate_system = sl.COORDINATE_SYSTEM.IMAGE
init_params.camera_fps = 30

error = zed.open(init_params)
if error != sl.ERROR_CODE.SUCCESS:
    print("Error opening ZED camera:", error)
    exit(1)

#retrieve depth data, pose, and image from the ZED camera
image = sl.Mat()
point_cloud = sl.Mat()
runtime = sl.RuntimeParameters()
zed_pose = sl.Pose()
tracking_params = sl.PositionalTrackingParameters()
error = zed.enable_positional_tracking(tracking_params)

if error != sl.ERROR_CODE.SUCCESS:
    print("Error enabling positional tracking:", error)

try:
    while True:
        if zed.grab(runtime) != sl.ERROR_CODE.SUCCESS:
            continue

        # just taking poses and point clouds from left camera, but could also use right camera or depth map
        zed.retrieve_image(image, sl.VIEW.LEFT)
        zed.retrieve_measure(point_cloud, sl.MEASURE.XYZRGBA)
 
        frame = cv2.cvtColor(image.get_data(), cv2.COLOR_BGRA2BGR)
        cloud = point_cloud.get_data()

        state = zed.get_position(zed_pose, sl.REFERENCE_FRAME.WORLD)

        if state == sl.POSITIONAL_TRACKING_STATE.OK:
            T_world_camera = np.array(zed_pose.pose_data().m, copy=True)
        else:
            T_world_camera = None

        # get the camera pose (translaton + orientation)
        T_world_camera = np.array(zed_pose.pose_data().m, copy=True)
        timestamp = zed_pose.timestamp.get_milliseconds()

        #object detection+segmentation - will later delete this since we do segmentation in segment_obj_and_grasp.py
        result = seg_model(frame, retina_masks=True, verbose=False)[0]

        object_clouds = []
        if result.masks is not None:
            masks = result.masks.data.cpu().numpy().astype(bool)
            classes = result.boxes.cls.cpu().numpy().astype(int)
            
            #get point clouds of each object detected
            for mask, cls in zip(masks, classes):
                xyz = cloud[mask, :3]
                bgr = frame[mask]

                valid = np.isfinite(xyz).all(axis=1)

                pts = xyz[valid]
                bgr = bgr[valid]

                if len(pts) == 0:
                    continue

                rgb = bgr[:, ::-1].astype(np.float64) / 255.0

                object_clouds.append((result.names[cls], pts))
                pcd = o3d.geometry.PointCloud()
                pcd.points = o3d.utility.Vector3dVector(pts) 
                pcd.colors = o3d.utility.Vector3dVector(rgb)
                #print(pcd.has_colors())
                o3d.io.write_point_cloud(f"../find-my-keys/manipulation/point_clouds/{result.names[cls]}_point_cloud.ply", pcd)

        #display the detections ontop of the camera view
        cv2.imshow("detections", result.plot())

        #user input to either exit camera view (q) or capture point cloud + pose of robot's current view (c)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("c"):
            #capture point cloud info
            error_code = point_cloud.write(f"../find-my-keys/manipulation/point_clouds/{timestamp}_scene_mug_point_cloud.ply")
            #and pose info
            if T_world_camera is not None and error_code == sl.ERROR_CODE.SUCCESS:
                np.save(
                    f"../find-my-keys/manipulation/point_clouds/{timestamp}_pose.npy",
                    T_world_camera
                )
                print(f'Timestamp:{timestamp},Translation:{T_world_camera[0, 3]},{T_world_camera[1, 3]},{T_world_camera[2, 3]},\n')
                print(f'Orientation:{T_world_camera[0, 0]},{T_world_camera[0, 1]},{T_world_camera[0, 2]},{T_world_camera[0, 3]}\n')
            else:
                print("Warning: No valid camera pose for this capture.")
            if error_code == sl.ERROR_CODE.SUCCESS:
                print("Point cloud successfully saved!")
            else:
                print("Error saving point cloud:", error_code)
                        
finally:
    #stop camera view and close all windows
    zed.close()
    cv2.destroyAllWindows()