from ultralytics import YOLO
import cv2
import numpy as np
from sklearn.cluster import DBSCAN

model = YOLO("leaf.pt")

cap = cv2.VideoCapture(702)


def cluster_boxes_dbscan(boxes, eps=50, min_samples=2):
    """使用DBSCAN对边界框进行聚类"""
    if not boxes or len(boxes) < 2:
        return [[box] for box in boxes] if boxes else []
    
    # 将边界框转换为特征向量 [center_x, center_y, width, height]
    features = []
    for box in boxes:
        center_x = (box[0] + box[2]) / 2
        center_y = (box[1] + box[3]) / 2
        width = box[2] - box[0]
        height = box[3] - box[1]
        features.append([center_x, center_y, width, height])
    
    features = np.array(features)
    
    # 应用DBSCAN聚类
    dbscan = DBSCAN(eps=eps, min_samples=min_samples)
    cluster_labels = dbscan.fit_predict(features)
    
    # 组织聚类结果
    clusters = {}
    for i, label in enumerate(cluster_labels):
        if label == -1:  # 噪声点，单独成一个聚类
            clusters[f"noise_{i}"] = [boxes[i]]
        else:
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(boxes[i])
    
    return list(clusters.values())


while cap.isOpened():
    success, frame = cap.read()

    if success:
        # 运行YOLO11跟踪，并在帧之间保持跟踪
        results = model.track(frame, persist=True)

        # 获取检测框
        detected_boxes = []
        if results[0].boxes is not None and len(results[0].boxes) > 0:
            # 转换检测框为[x1, y1, x2, y2]格式
            for box in results[0].boxes.xyxy.cpu().numpy():
                detected_boxes.append(box)

        # 对检测框进行聚类 (使用DBSCAN)
        clustered_boxes = cluster_boxes_dbscan(detected_boxes, eps=80, min_samples=2)
        
        # 打印调试信息
        if detected_boxes:
            print(f"检测到 {len(detected_boxes)} 个框，DBSCAN聚类后得到 {len(clustered_boxes)} 个聚类")
            
            # 计算框之间的距离信息
            if len(detected_boxes) >= 2:
                box1, box2 = detected_boxes[0], detected_boxes[1]
                center1 = [(box1[0] + box1[2])/2, (box1[1] + box1[3])/2]
                center2 = [(box2[0] + box2[2])/2, (box2[1] + box2[3])/2]
                distance = np.sqrt((center1[0] - center2[0])**2 + (center1[1] - center2[1])**2)
                print(f"  前两个框中心距离: {distance:.1f} 像素")
                
            # 找到最小的中心距离
            min_distance = float('inf')
            for i in range(len(detected_boxes)):
                for j in range(i + 1, len(detected_boxes)):
                    box1, box2 = detected_boxes[i], detected_boxes[j]
                    center1 = [(box1[0] + box1[2])/2, (box1[1] + box1[3])/2]
                    center2 = [(box2[0] + box2[2])/2, (box2[1] + box2[3])/2]
                    distance = np.sqrt((center1[0] - center2[0])**2 + (center1[1] - center2[1])**2)
                    if distance < min_distance:
                        min_distance = distance
            print(f"  最近框中心距离: {min_distance:.1f} 像素 (阈值: 80)")
            
            for i, cluster in enumerate(clustered_boxes):
                if len(cluster) > 1:
                    print(f"  聚类 {i}: {len(cluster)} 个框 ✓")
                else:
                    print(f"  聚类 {i}: {len(cluster)} 个框")

        # 可视化聚类结果
        cluster_colors = [
            (0, 0, 255),  # 红色
            (0, 255, 0),  # 绿色
            (255, 0, 0),  # 蓝色
            (255, 255, 0),  # 青色
            (255, 0, 255),  # 品红
            (0, 255, 255),  # 黄色
            (128, 0, 0),  # 深红色
            (0, 128, 0),  # 深绿色
            (0, 0, 128),  # 深蓝色
        ]

        # 绘制原始跟踪结果
        annotated_frame = results[0].plot()

        # 在原始图像上添加聚类信息
        for i, cluster in enumerate(clustered_boxes):
            if len(cluster) > 1:  # 只为包含多个框的聚类绘制边界
                color = cluster_colors[i % len(cluster_colors)]
                # 绘制聚类边界
                all_x1 = min([box[0] for box in cluster])
                all_y1 = min([box[1] for box in cluster])
                all_x2 = max([box[2] for box in cluster])
                all_y2 = max([box[3] for box in cluster])

                # 绘制聚类框（粗线表示聚类边界）
                cv2.rectangle(annotated_frame,
                              (int(all_x1), int(all_y1)),
                              (int(all_x2), int(all_y2)),
                              color, 4)

                # 添加聚类标签
                cv2.putText(annotated_frame, f"Cluster {i} ({len(cluster)} boxes)",
                            (int(all_x1), int(all_y1) - 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                            
                # 在聚类内部绘制细线连接各个框
                for j, box in enumerate(cluster):
                    center_x = int((box[0] + box[2]) / 2)
                    center_y = int((box[1] + box[3]) / 2)
                    if j > 0:
                        prev_box = cluster[j-1]
                        prev_center_x = int((prev_box[0] + prev_box[2]) / 2)
                        prev_center_y = int((prev_box[1] + prev_box[3]) / 2)
                        cv2.line(annotated_frame, (prev_center_x, prev_center_y), 
                                (center_x, center_y), color, 1)

        # 显示带注释的帧
        cv2.imshow("YOLO11 Tracking with Clustering", annotated_frame)

        # 如果按下'q'，退出循环
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    else:
        # 如果到达视频结尾，退出循环
        break