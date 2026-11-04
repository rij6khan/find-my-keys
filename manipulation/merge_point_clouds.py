#This file merges the point clouds given the camera poses of the scenes captured. 
# The merged point cloud is saved to a new file.
import open3d as o3d
import numpy as np

# Load the three point clouds and their respective poses
timestamps = [1793633614394, 1793633693931, 1793633719899] #point clouds of the 3 scenes captured
pcd1 = o3d.io.read_point_cloud(f"../find-my-keys/manipulation/point_clouds/{timestamps[0]}_scene_mug_point_cloud.ply")
pcd2 = o3d.io.read_point_cloud(f"../find-my-keys/manipulation/point_clouds/{timestamps[1]}_scene_mug_point_cloud.ply")
pcd3 = o3d.io.read_point_cloud(f"../find-my-keys/manipulation/point_clouds/{timestamps[2]}_scene_mug_point_cloud.ply")

pose1 = np.load(f"../find-my-keys/manipulation/point_clouds/{timestamps[0]}_pose.npy")
pose2 = np.load(f"../find-my-keys/manipulation/point_clouds/{timestamps[1]}_pose.npy")
pose3 = np.load(f"../find-my-keys/manipulation/point_clouds/{timestamps[2]}_pose.npy")

# Transform the point clouds to the world coordinate frame using their respective poses
pcd1.transform(pose1)
pcd2.transform(pose2)
pcd3.transform(pose3)

#check for fitness, rmse, and correspondences between point clouds
for i in range(len(timestamps)):
    for j in range(i + 1, len(timestamps)):
        source = [pcd1, pcd2, pcd3][i]
        target = [pcd1, pcd2, pcd3][j]
        threshold = 10.0  # distance threshold for correspondence
        reg_p2p = o3d.pipelines.registration.registration_icp(
            source, target, threshold, np.eye(4),
            o3d.pipelines.registration.TransformationEstimationPointToPoint()
        )
        print(f"Point Clouds {timestamps[i]} and {timestamps[j]}:")
        print(f"Fitness: {reg_p2p.fitness}")
        print(f"RMSE: {reg_p2p.inlier_rmse}")
        print(f"Correspondences: {len(reg_p2p.correspondence_set)}")

# Combine the transformed point clouds
combined_pcd = pcd1 + pcd2 + pcd3   

# Visualize the combined point cloud
o3d.visualization.draw_geometries([combined_pcd])

# Save the combined point cloud to a new file
o3d.io.write_point_cloud("../find-my-keys/manipulation/merged_point_clouds/combined_scene_mug_point_cloud.ply", combined_pcd)
print('successfully merged point clouds')

