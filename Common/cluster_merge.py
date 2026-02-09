import numpy as np
from sklearn.cluster import DBSCAN

def merge_clusters_across_positions(scan_data, eps=3.0, min_samples=1, camera_fov_x=3, camera_fov_y=2):
    """Merge detection boxes across different motor positions using DBSCAN"""
    if not scan_data:
        return []

    camera_fov_x = camera_fov_x * 2
    camera_fov_y = camera_fov_y * 2
    frame_w, frame_h = 640, 480
    center_x, center_y = frame_w / 2, frame_h / 2

    box_features = []
    box_info = []

    for scan in scan_data:
        motor_y, motor_x = scan['motor_position']
        x1, y1, x2, y2 = scan['bbox']

        pixel_offset_x = (x1 + x2) / 2 - center_x
        pixel_offset_y = (y1 + y2) / 2 - center_y

        motor_offset_x = (pixel_offset_x / frame_w) * camera_fov_x
        motor_offset_y = (pixel_offset_y / frame_h) * camera_fov_y

        world_x = motor_x + motor_offset_x
        world_y = motor_y + motor_offset_y

        if not (0 <= world_x <= 9.5 and 0 <= world_y <= 9.0):
            continue

        box_features.append([world_x, world_y])
        box_info.append({
            'motor_position': (motor_y, motor_x),
            'bbox': scan['bbox']
        })

    if len(box_features) < 1:
        return []

    features = np.array(box_features)
    dbscan = DBSCAN(eps=eps, min_samples=min_samples)
    labels = dbscan.fit_predict(features)

    merged = {}
    for i, label in enumerate(labels):
        if label not in merged:
            merged[label] = []
        merged[label].append(box_info[i])

    return list(merged.values())
