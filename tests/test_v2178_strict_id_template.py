from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines.id_rule_engine import normalize_tree_ids_strict
from g_file_studio.services.id_rule_service import IdRule


def test_force_repairs_invalid_id_and_reference():
    root = ET.fromstring("""<G><Layer>
      <ConnectLine id=\"140\" d=\"0,0 1,1\"/>
      <CBreakerDis id=\"117000001\" node_area=\"0,0,140\"/>
    </Layer></G>""")
    tree = ET.ElementTree(root)
    rules = {
        "ConnectLine": IdRule("ConnectLine", "34", 8),
        "CBreakerDis": IdRule("CBreakerDis", "117", 9),
    }
    result = normalize_tree_ids_strict(tree, Path("x.g"), rules)
    line, dev = list(root.find("Layer"))
    assert result.format_fixed_count == 1
    assert line.get("id") == "34000001"
    assert dev.get("node_area") == "0,0,34000001"


def test_valid_id_is_unchanged():
    root = ET.fromstring("<G><Layer><ConnectLine id=\"34001838\"/></Layer></G>")
    tree = ET.ElementTree(root)
    rules = {"ConnectLine": IdRule("ConnectLine", "34", 8)}
    result = normalize_tree_ids_strict(tree, Path("x.g"), rules)
    assert result.changed_element_ids == 0
    assert root.find("Layer")[0].get("id") == "34001838"
