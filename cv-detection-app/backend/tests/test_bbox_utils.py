from backend.utils.bbox_utils import normalize_bbox, denormalize_bbox


def test_bbox_roundtrip():
    w, h = 1280, 720
    x1, y1, x2, y2 = 100, 50, 400, 300
    norm = normalize_bbox(x1, y1, x2, y2, w, h)
    dx1, dy1, dx2, dy2 = denormalize_bbox(norm, w, h)
    assert abs(dx1 - x1) <= 1
    assert abs(dy1 - y1) <= 1
    assert abs(dx2 - x2) <= 1
    assert abs(dy2 - y2) <= 1
