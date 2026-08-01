from ultralytics import YOLO
from config import MODEL_PATH


def load_model():
    return YOLO(MODEL_PATH)


def detect_objects(model, frame):
    return model(frame)


def draw_boxes(results):
    return results[0].plot()