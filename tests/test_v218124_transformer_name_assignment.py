import xml.etree.ElementTree as ET

from g_file_studio.services.symbol_inventory_service import _assign_transformer_text_names


def _transformer(element_id: str, x: float, y: float, rotate: int = 0) -> ET.Element:
    return ET.Element(
        "TransformerDis",
        {
            "id": element_id,
            "x": str(x),
            "y": str(y),
            "w": "150",
            "h": "150",
            "rotate": str(rotate),
            "tfr": f"rotate({rotate}) scale(3,3)",
        },
    )


def _text(element_id: str, value: str, x: float, y: float, w: float = 115, h: float = 55) -> ET.Element:
    return ET.Element(
        "Text",
        {
            "id": element_id,
            "ts": value,
            "x": str(x),
            "y": str(y),
            "w": str(w),
            "h": str(h),
        },
    )


def test_transformer_labels_are_assigned_globally_without_cascading_shift():
    # Geometry replayed from the AJWD-30 regression: the old center-distance greedy
    # resolver assigned 99798 to the preceding transformer, 99958 to the next one,
    # and left the final transformer unnamed.  Global anchor scoring must keep each
    # visible label with its own transformer.
    transformers = [
        _transformer("115000205", 2169, 3961, 0),
        _transformer("115000207", 2103, 4102, 90),
        _transformer("115000209", 2103, 4295, 90),
    ]
    texts = [
        _text("8000206", "99443", 2124, 3876),
        _text("8000208", "99798", 2087, 4012),
        _text("8000210", "99958", 2098, 4196),
    ]

    assigned = _assign_transformer_text_names(transformers, texts)

    assert assigned[id(transformers[0])][:3] == ("99443", "Nearby Text", "HIGH")
    assert assigned[id(transformers[1])][:3] == ("99798", "Nearby Text", "HIGH")
    assert assigned[id(transformers[2])][:3] == ("99958", "Nearby Text", "HIGH")


def test_transformer_side_label_beats_nearby_lbs_annotation_and_below_label_is_supported():
    # The 99966 label is visually tied to the transformer but sits in an unusual
    # side/anchor position inside the large GIcon bounding box.  A closer LBS label
    # must not steal the transformer name.
    side_transformer = _transformer("115000122", 2523, 3265, 0)
    below_transformer = _transformer("115000132", 2506, 3833, 0)
    texts = [
        _text("8000384", "LBS-1179", 2554, 3135, 197, 50),
        _text("8000123", "99966", 2354, 3234),
        _text("8000133", "99960", 2475, 3871),
    ]

    assigned = _assign_transformer_text_names([side_transformer, below_transformer], texts)

    assert assigned[id(side_transformer)][0] == "99966"
    assert assigned[id(side_transformer)][2] == "MEDIUM"
    assert assigned[id(below_transformer)][0] == "99960"
