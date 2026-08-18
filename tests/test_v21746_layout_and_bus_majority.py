from decimal import Decimal
import xml.etree.ElementTree as ET

from g_file_studio.engines.merge_engine import normalize_selected_main_bus_rows, get_bus_line


def test_bus_majority_y_normalizes_minority_and_attached_endpoint() -> None:
    layer = ET.fromstring('''<Layer>
      <Bus id="3001" keyid="K" x="97" y="197" w="106" h="6" x1="100" y1="200" x2="200" y2="200" d="100,200 200,200"/>
      <ConnectLine id="3401" x="117" y="197" w="6" h="56" d="120,200 120,250"/>
      <Bus id="3002" keyid="K" x="297" y="197" w="106" h="6" x1="300" y1="200" x2="400" y2="200" d="300,200 400,200"/>
      <ConnectLine id="3402" x="317" y="197" w="6" h="56" d="320,200 320,250"/>
      <Bus id="3003" keyid="K" x="497" y="217" w="106" h="6" x1="500" y1="220" x2="600" y2="220" d="500,220 600,220"/>
      <ConnectLine id="3403" x="517" y="217" w="6" h="36" d="520,220 520,250"/>
    </Layer>''')

    targets, changes = normalize_selected_main_bus_rows(layer, {"K"})

    assert targets["K"] == Decimal("200")
    assert len(changes) == 1
    assert changes[0]["bus_id"] == "3003"
    bus3 = next(e for e in layer if e.get("id") == "3003")
    assert get_bus_line(bus3)[1] == Decimal("200")
    line3 = next(e for e in layer if e.get("id") == "3403")
    assert line3.get("d") == "520,200 520,250"
    assert line3.get("y") == "197"
    assert line3.get("h") == "56"


def test_distinct_keyids_never_share_y_target() -> None:
    layer = ET.fromstring('''<Layer>
      <Bus id="a1" keyid="A" x1="0" y1="100" x2="100" y2="100" d="0,100 100,100"/>
      <Bus id="a2" keyid="A" x1="200" y1="100" x2="300" y2="100" d="200,100 300,100"/>
      <Bus id="b1" keyid="B" x1="0" y1="180" x2="100" y2="180" d="0,180 100,180"/>
      <Bus id="b2" keyid="B" x1="200" y1="182" x2="300" y2="182" d="200,182 300,182"/>
    </Layer>''')
    targets, _changes = normalize_selected_main_bus_rows(layer, {"A", "B"})
    assert targets["A"] == Decimal("100")
    assert targets["B"] in {Decimal("180"), Decimal("182")}
    assert targets["A"] != targets["B"]
