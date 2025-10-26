import numpy as np
from sklearn.cluster import DBSCAN

def merge_clusters_across_positions(scan_data, eps=3.0, min_samples=1):
    """Merge clusters detected at different motor positions using DBSCAN"""
    if not scan_data:
        return []

    cluster_features = []
    cluster_info = []

    for scan in scan_data:
        motor_x, motor_y = scan['motor_position']
        cluster = scan['cluster']

        if not cluster:
            continue

        x1 = min([box[0] for box in cluster])
        y1 = min([box[1] for box in cluster])
        x2 = max([box[2] for box in cluster])
        y2 = max([box[3] for box in cluster])

        cluster_features.append([motor_x, motor_y])
        cluster_info.append({
            'motor_position': (motor_x, motor_y),
            'bbox': (x1, y1, x2, y2),
            'cluster': cluster
        })

    if len(cluster_features) < 1:
        return []

    features = np.array(cluster_features)
    dbscan = DBSCAN(eps=eps, min_samples=min_samples)
    labels = dbscan.fit_predict(features)

    merged = {}
    for i, label in enumerate(labels):
        if label not in merged:
            merged[label] = []
        merged[label].append(cluster_info[i])

    return list(merged.values())
