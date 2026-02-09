from ultralytics import YOLO
from Common.dbscan import cluster_boxes_dbscan

_model = None

def get_model():
    global _model
    if _model is None:
        _model = YOLO("yolo/leaf.pt")
    return _model

def detect_plants(frame):
    model = get_model()
    results = model(frame)
    if results[0].boxes is None or len(results[0].boxes) == 0:
        return []
    boxes = [box.tolist() for box in results[0].boxes.xyxy.cpu().numpy()]
    return cluster_boxes_dbscan(boxes, eps=2000, min_samples=3)
