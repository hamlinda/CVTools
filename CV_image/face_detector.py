import cv2          # OpenCV — image loading, DNN inference, drawing, and display
import numpy as np  # NumPy — used to scale the raw detection bounding-box coordinates
import sys          # sys.argv for CLI arguments; sys.exit for clean error exits
import os           # os.path checks for file existence and basename for window title
import urllib.request  # standard-library HTTP client used to download the model files

# ---------------------------------------------------------------------------
# DNN model configuration
# ---------------------------------------------------------------------------
# OpenCV ships a pre-trained ResNet-10 Single Shot Detector (SSD) face model.
# The model consists of two files:
#   1. deploy.prototxt  — the Caffe network architecture (text, ~28 KB)
#   2. *.caffemodel     — the trained weights (binary, ~10 MB)
# Both are hosted on OpenCV's GitHub and are downloaded automatically on first run.

MODEL_URL  = "https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel"
CONFIG_URL = "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt"
MODEL_FILE  = "res10_300x300_ssd_iter_140000.caffemodel"  # saved locally next to this script
CONFIG_FILE = "deploy.prototxt"                            # saved locally next to this script

# ---------------------------------------------------------------------------
# Tunable display / detection parameters
# ---------------------------------------------------------------------------
CONFIDENCE_THRESHOLD = 0.2   # detections below this confidence (0–1) are discarded;
                              # lower = more detections but more false positives

BOX_COLOR      = (0, 255, 0)  # BGR green — color of the bounding-box rectangle
TEXT_COLOR     = (0, 255, 0)  # BGR green — kept for reference (labels use white-on-green)
LABEL_BG_COLOR = (0, 180, 0)  # slightly darker green for the confidence label background


# ---------------------------------------------------------------------------
# download_model_files()
# ---------------------------------------------------------------------------
def download_model_files():
    """Download the Caffe prototxt and caffemodel if they are not already on disk."""
    # Iterate over both (URL, local-filename) pairs in dependency order:
    # the prototxt must exist before we try to load the net, so it is listed first.
    for url, filename in [(CONFIG_URL, CONFIG_FILE), (MODEL_URL, MODEL_FILE)]:
        if not os.path.exists(filename):
            # File is missing — fetch it from GitHub and stream it straight to disk.
            print(f"Downloading {filename}...")
            urllib.request.urlretrieve(url, filename)  # blocks until complete
            print(f"  Saved {filename}")
        # If the file already exists we skip silently to avoid redundant downloads.


# ---------------------------------------------------------------------------
# load_net()
# ---------------------------------------------------------------------------
def load_net():
    """Ensure model files are present, then load and return the OpenCV DNN face detector."""
    download_model_files()

    # cv2.dnn.readNetFromCaffe loads a Caffe-format network.
    # Arguments: (prototxt path, caffemodel path)
    # The returned 'net' object holds the full network graph and weights in memory.
    net = cv2.dnn.readNetFromCaffe(CONFIG_FILE, MODEL_FILE)
    return net


# ---------------------------------------------------------------------------
# detect_faces()
# ---------------------------------------------------------------------------
def detect_faces(net, image):
    """
    Run the DNN face detector on 'image' and return a list of detections.

    Returns:
        list of (x1, y1, x2, y2, confidence) tuples in pixel coordinates,
        where (x1, y1) is the top-left corner and (x2, y2) is the bottom-right.
    """
    h, w = image.shape[:2]  # original image dimensions needed to un-normalise the boxes

    # cv2.dnn.blobFromImage converts the image into the 4-D tensor the network expects.
    #   • resize to (300×300) — the resolution the SSD model was trained on
    #   • scalefactor=1.0    — no pixel-value scaling (values stay 0–255)
    #   • mean subtraction   — (104, 177, 123) are the per-channel BGR means used during
    #                          training; subtracting them centres the input distribution
    blob = cv2.dnn.blobFromImage(
        cv2.resize(image, (300, 300)),
        scalefactor=1.0,
        size=(300, 300),
        mean=(104.0, 177.0, 123.0),
    )

    net.setInput(blob)   # push the pre-processed blob into the network's input layer
    detections = net.forward()  # run the forward pass; shape is (1, 1, N, 7)
    # detections[0, 0, i] = [_, _, confidence, x1_norm, y1_norm, x2_norm, y2_norm]
    # Coordinates are normalised to [0, 1] relative to the 300×300 input — we must
    # scale them back to the original image dimensions before drawing.

    faces = []
    for i in range(detections.shape[2]):  # iterate over every proposed detection
        confidence = float(detections[0, 0, i, 2])  # extract the confidence score

        # Skip weak detections that are likely background or noise
        if confidence < CONFIDENCE_THRESHOLD:
            continue

        # Scale normalised [0,1] box coords back to pixel space using the original size
        box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
        x1, y1, x2, y2 = box.astype(int)

        # Clamp coordinates to valid image bounds to avoid drawing outside the canvas
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w - 1, x2), min(h - 1, y2)

        faces.append((x1, y1, x2, y2, confidence))

    return faces  # may be an empty list if no faces pass the threshold


# ---------------------------------------------------------------------------
# draw_faces()
# ---------------------------------------------------------------------------
def draw_faces(image, faces):
    """
    Draw a bounding box and confidence label on a copy of 'image' for every
    detected face.  Returns the annotated copy without modifying the original.
    """
    output = image.copy()  # work on a copy so the caller's array is unchanged

    for x1, y1, x2, y2, confidence in faces:
        # Draw the rectangular bounding box around the face region.
        # cv2.rectangle(image, top-left, bottom-right, BGR-color, thickness)
        cv2.rectangle(output, (x1, y1), (x2, y2), BOX_COLOR, 2)

        # Build the label string, e.g. "87.4%"
        label = f"{confidence * 100:.1f}%"

        # Measure how many pixels the label text will occupy so we can size the
        # background rectangle to fit it exactly.
        (text_w, text_h), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1
        )

        # Pin the label just above the top edge of the face box.
        # 'label_y' is the baseline y-coordinate of the rendered text.
        # We clamp it so the label never renders above the image top edge.
        label_y = max(y1, text_h + 6)

        # Filled rectangle that acts as the label background for readability
        cv2.rectangle(
            output,
            (x1, label_y - text_h - 6),         # top-left of background rect
            (x1 + text_w + 4, label_y + baseline - 4),  # bottom-right
            LABEL_BG_COLOR,
            cv2.FILLED,  # solid fill (no border)
        )

        # Render the confidence percentage text in white over the green background
        cv2.putText(
            output,
            label,
            (x1 + 2, label_y - 4),       # slight inset so text doesn't touch the edge
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,                          # font scale
            (255, 255, 255),              # white text
            1,                            # stroke thickness (pixels)
            cv2.LINE_AA,                  # anti-aliased rendering for smooth edges
        )

    return output


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------
def main():
    # --- Argument validation ------------------------------------------------
    if len(sys.argv) < 2:
        # Tell the user how to invoke the script and exit with a non-zero code.
        print("Usage: python face_detector.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]  # first positional argument is the image file path

    if not os.path.exists(image_path):
        print(f"Error: file not found — {image_path}")
        sys.exit(1)

    # --- Load the image -----------------------------------------------------
    # cv2.imread decodes the image into a NumPy array in BGR channel order.
    # Returns None if the file cannot be decoded (unsupported format, corrupt, etc.)
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: could not read image — {image_path}")
        sys.exit(1)

    # --- Run detection ------------------------------------------------------
    print("Loading face detection model...")
    net = load_net()

    print("Detecting faces...")
    faces = detect_faces(net, image)  # returns list of (x1,y1,x2,y2,confidence)

    # --- Report results to the terminal -------------------------------------
    if not faces:
        print("No faces detected.")
    else:
        print(f"Detected {len(faces)} face(s):")
        for idx, (x1, y1, x2, y2, conf) in enumerate(faces, 1):
            print(f"  Face {idx}: [{x1},{y1} → {x2},{y2}]  confidence {conf*100:.1f}%")

    # --- Annotate and display -----------------------------------------------
    output = draw_faces(image, faces)  # returns a new image with boxes + labels drawn

    # If the image is very large it may exceed the screen; scale it down while
    # preserving the aspect ratio so all faces are still clearly visible.
    screen_max = 900  # maximum pixel dimension (width or height) for the display window
    h, w = output.shape[:2]
    if max(h, w) > screen_max:
        scale = screen_max / max(h, w)   # uniform scale factor < 1.0
        output = cv2.resize(output, (int(w * scale), int(h * scale)))

    # Open a native OS window with a descriptive title and show the annotated image.
    # cv2.imshow is non-blocking — we must call waitKey to process GUI events.
    window_title = f"Face Detection — {os.path.basename(image_path)}"
    cv2.imshow(window_title, output)
    print("\nPress any key to close the window.")
    cv2.waitKey(0)          # block until the user presses any keyboard key
    cv2.destroyAllWindows() # cleanly close all OpenCV windows before exiting


# Standard Python entry-point guard — only run main() when executed directly,
# not when this module is imported by another script.
if __name__ == "__main__":
    main()
