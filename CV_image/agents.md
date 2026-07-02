# Agent Guidelines & Component Architecture: CV_image

This guide provides developer instructions, architectural details, and coding conventions for the `CV_image` sub-service.

---

## 1. Sub-Service Overview

The `CV_image` service is a standalone, offline command-line utility designed for face detection in static images. It uses OpenCV’s deep neural network (DNN) module with a pre-trained Caffe SSD (Single Shot MultiBox Detector) model.

### Key Architecture Flow
```
[User CLI Input] ──> [face_detector.py]
                          │
                          ├─> [Checks/Downloads Caffe Models]
                          │       ├── deploy.prototxt
                          │       └── res10_300x300_ssd_iter_140000.caffemodel
                          │
                          ├─> [cv2.imread & Decode]
                          ├─> [cv2.dnn.blobFromImage]
                          ├─> [Net Inference]
                          ├─> [Bounding-Box Scaling & Coordinates Clamp]
                          └─> [cv2.imshow / Window Render]
```

---

## 2. Technical Specifications & Configuration

### Model Assets
- **Config URL**: `https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt`
- **Weights URL**: `https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel`
- Both files are stored locally in `CV_image/` beside `face_detector.py` and are downloaded automatically on the first execution via `urllib.request.urlretrieve`.

### Tunable Parameters
- `CONFIDENCE_THRESHOLD = 0.2`: Detections below this score are discarded.
- Colors (BGR Space):
  - `BOX_COLOR = (0, 255, 0)`: Green border for the face bounding box.
  - `LABEL_BG_COLOR = (0, 180, 0)`: Slightly darker green for confidence label backgrounds.
  - Font: `cv2.FONT_HERSHEY_SIMPLEX` (scale `0.6`, thickness `1`).

---

## 3. Implementation Details

### A. Blob Pre-processing
- The detector scales and normalizes images before inference.
- Blob transformation details in [detect_faces](file:///home/dlh/dlhdev/cv_tools/CV_image/face_detector.py#L65-L112):
  - Resized to `300x300` resolution.
  - Standard scale factor: `1.0` (pixel values stay in `0–255` range).
  - Channel mean subtraction: `(104.0, 177.0, 123.0)` in BGR order to center the input distribution.

### B. Bounding Box Scaling & Clamping
- DNN returns relative coordinates in `[0.0, 1.0]` normalized space.
- Coordinates must be multiplied by original image width and height:
  ```python
  box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
  ```
- All coordinates must be clamped using `max(0, val)` and `min(bound - 1, val)` to prevent rendering boxes outside the bounds of the pixel array.

### C. Display Management
- If the image exceeds a height or width of `900` pixels, it is uniformly scaled down using `cv2.resize` while preserving the aspect ratio before rendering.
- Releasing GUI resources requires calling `cv2.destroyAllWindows()` after a key press is registered via `cv2.waitKey(0)`.

---

## 4. Development & Coding Conventions

- **CLI Conventions**: Verify CLI parameters via `sys.argv`. If missing, output usage details (`Usage: python face_detector.py <image_path>`) and terminate with `sys.exit(1)`.
- **Pure Functions**: Ensure rendering functions like [draw_faces](file:///home/dlh/dlhdev/cv_tools/CV_image/face_detector.py#L117-L164) copy input images using `image.copy()` rather than mutating parameters directly.
- **Error Handling**: Use guard clauses to exit early if files do not exist or if `cv2.imread` yields a `None` frame.
