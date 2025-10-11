import numpy as np
from sklearn.cluster import DBSCAN

def cluster_boxes_dbscan(boxes, eps=80, min_samples=2):
    if not boxes or len(boxes) < 2:
        return [[box] for box in boxes] if boxes else []

    features = []
    for box in boxes:
        center_x = (box[0] + box[2]) / 2
        center_y = (box[1] + box[3]) / 2
        width = box[2] - box[0]
        height = box[3] - box[1]
        features.append([center_x, center_y, width, height])

    features = np.array(features)
    dbscan = DBSCAN(eps=eps, min_samples=min_samples)
    cluster_labels = dbscan.fit_predict(features)

    clusters = {}
    for i, label in enumerate(cluster_labels):
        if label == -1:
            clusters[f"noise_{i}"] = [boxes[i]]
        else:
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(boxes[i])

    return list(clusters.values())
