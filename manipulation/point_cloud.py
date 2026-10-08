import pyzed.sl as sl
import cv2
import numpy as np
#import matplotlib.pyplot as plt
import open3d as o3d
from PIL import Image
from ultralytics import YOLO #for object detection+segmentation
import os

seg_model = YOLO(os.path.join("../find-my-keys/manipulation/", "yolov8n-seg.pt")) #replace with HMD model weights for integration?

#initialize the ZED camera + config parameters
cap = sl.Camera()
init_params = sl.InitParameters()
init_params.camera_resolution = sl.RESOLUTION.AUTO
#init_params.depth_mode = sl.DEPTH_MODE.NEURAL
init_params.camera_fps = 30

error = cap.open(init_params)
if error != sl.ERROR_CODE.SUCCESS:
    print("Error opening ZED camera:", error)
    exit(1)

#retrieve depth data and image from the ZED camera
image = sl.Mat()
depth_map = sl.Mat()
point_cloud = sl.Mat()
runtime = sl.RuntimeParameters()

try:
    while True:
        if cap.grab(runtime) != sl.ERROR_CODE.SUCCESS:
            continue

        cap.retrieve_image(image, sl.VIEW.LEFT)
        cap.retrieve_measure(point_cloud, sl.MEASURE.XYZRGBA)
 
        frame = cv2.cvtColor(image.get_data(), cv2.COLOR_BGRA2BGR)
        cloud = point_cloud.get_data()

        #object detection+segmentation
        result = seg_model(frame, retina_masks=True, verbose=False)[0]

        object_clouds = []
        if result.masks is not None:
            masks = result.masks.data.cpu().numpy().astype(bool)
            classes = result.boxes.cls.cpu().numpy().astype(int)

            #get point clouds of each object detected
            for mask, cls in zip(masks, classes):
                xyz = cloud[mask][:, :3]
                bgr = frame[mask]

                pts = xyz[np.isfinite(xyz).all(axis=1)]
                bgr = bgr[np.isfinite(xyz).all(axis=1)]
                if len(xyz) == 0:
                    continue
                rgb = bgr[:, ::-1].astype(np.float64)/255.0

                object_clouds.append((result.names[cls], pts))
                pcd = o3d.geometry.PointCloud()
                pcd.points = o3d.utility.Vector3dVector(pts) 
                pcd.colors = o3d.utility.Vector3dVector(rgb)
                #print(pcd.has_colors())
                o3d.io.write_point_cloud(f"../find-my-keys/manipulation/point_clouds/{result.names[cls]}_point_cloud.ply", pcd)
          
        cv2.imshow("detections", result.plot())
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
finally:
    cap.close()
    cv2.destroyAllWindows()