import open3d as o3d
import numpy as np
import sys

#read file of a point cloud
def visual_point_cloud(object):
    pcd = o3d.io.read_point_cloud(f"../find-my-keys/manipulation/point_clouds/{object}_point_cloud.ply")
    print(pcd)
    o3d.visualization.draw_geometries([pcd])

def main():
    visual_point_cloud(object=sys.argv[1])

if __name__ == "__main__": 
    main()