import xml.etree.ElementTree as ET

from g_file_studio.services.symbol_inventory_service import _assign_global_standalone_names


def _device(tag: str, eid: str, x: float, y: float, line_id: str, w: float = 80, h: float = 80):
    return ET.Element(tag, {
        "id": eid, "x": str(x), "y": str(y), "w": str(w), "h": str(h),
        "node_area": f"1,0,{line_id}",
    })


def _line(eid: str, device_id: str, d: str):
    return ET.Element("ConnectLine", {
        "id": eid, "d": d, "node_area": f"0,1,{device_id}", "link": f"0,1,{device_id}",
    })


def _text(eid: str, value: str, x: float, y: float, w: float = 150, h: float = 50):
    return ET.Element("Text", {
        "id": eid, "ts": value, "x": str(x), "y": str(y), "w": str(w), "h": str(h),
    })


def test_adel_vertical_transformers_use_visual_nearest_text_without_direction_bias():
    # Geometry replayed from the user's JED-STH-ADEL sample.  v2.18.128 used a
    # transformer-specific directional score and shifted the labels by one row.
    devices = [
        _device("TransformerDis", "115000119", 28081, 2153, "34001861"),
        _device("TransformerDis", "115000120", 28081, 2309, "34001864"),
        _device("TransformerDis", "115001130", 28081, 2429, "34001866"),
        _device("TransformerDis", "115001131", 28081, 2582, "34001868"),
    ]
    lines = [
        _line("34001861", "115000119", "28084,2192 28064,2192"),
        _line("34001864", "115000120", "28084,2348 28065,2347"),
        _line("34001866", "115001130", "28084,2468 28065,2466"),
        _line("34001868", "115001131", "28084,2621 28065,2617"),
    ]
    texts = [
        _text("8000865", "973150", 28184, 2163),
        _text("8000866", "96467", 28195, 2348, 125),
        _text("8000867", "972760", 28192, 2460),
        _text("8000868", "96260", 28192, 2621, 125),
    ]

    assigned = _assign_global_standalone_names(devices, texts, devices + lines + texts)

    assert assigned[id(devices[0])][0] == "973150"
    assert assigned[id(devices[1])][0] == "96467"
    assert assigned[id(devices[2])][0] == "972760"
    assert assigned[id(devices[3])][0] == "96260"


def test_adel_parallel_and_lower_transformers_use_connection_anchor_and_global_unique_text():
    # The right-hand 971886 is visually nearest the right transformer electrical
    # endpoint, while 971878 belongs to the lower transformer.  Logical GIcon box
    # centers alone make these two look misleadingly close.
    devices = [
        _device("TransformerDis", "115000099", 28250, 1523, "34001857"),
        _device("TransformerDis", "115000100", 28632, 1523, "34001857"),
        _device("TransformerDis", "115000101", 28537, 1583, "34000847"),
        _device("TransformerDis", "115000102", 28591, 1792, "34000860"),
    ]
    lines = [
        ET.Element("ConnectLine", {
            "id": "34001857", "d": "28289,1526 28671,1526",
            "node_area": "0,0,115000099;0,1,115000100",
            "link": "0,0,115000099;0,1,115000100",
        }),
        _line("34000847", "115000101", "28576,1660 28475,1656"),
        _line("34000860", "115000102", "28594,1831 28575,1830"),
    ]
    texts = [
        _text("8000873", "971886", 28089, 1529),
        _text("8000872", "971886", 28750, 1536),
        _text("8000871", "971878", 28627, 1637),
        _text("8000870", "973762", 28686, 1809),
        # This annotation is geometrically close but is not an equipment name.
        _text("8000918", "F", 28525, 1706, 27),
    ]

    assigned = _assign_global_standalone_names(devices, texts, devices + lines + texts)

    assert assigned[id(devices[0])][0] == "971886"
    assert assigned[id(devices[1])][0] == "971886"
    assert assigned[id(devices[2])][0] == "971878"
    assert assigned[id(devices[3])][0] == "973762"
    assert len({assigned[id(device)][3] for device in devices}) == 4


def test_global_nearest_rule_is_not_transformer_specific_and_searches_all_directions():
    devices = [
        _device("CBreakerDis", "lbs", 100, 100, "l1", 40, 40),
        _device("CBreakerDis", "rec", 400, 400, "l2", 40, 40),
    ]
    lines = [
        _line("l1", "lbs", "100,120 50,120"),
        _line("l2", "rec", "420,440 420,500"),
    ]
    texts = [
        # Left of first device.
        _text("t1", "LBS-1162", 20, 100, 70, 30),
        # Below/right of second device; no top/bottom preference is allowed.
        _text("t2", "REC-15", 430, 455, 80, 30),
    ]
    assigned = _assign_global_standalone_names(devices, texts, devices + lines + texts)
    assert assigned[id(devices[0])][0] == "LBS-1162"
    assert assigned[id(devices[1])][0] == "REC-15"
