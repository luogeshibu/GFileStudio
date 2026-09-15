from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.models import InputMode
from g_file_studio.services.site_profile_service import SiteSmartProfile
from g_file_studio.services.symbol_discovery_service import discover_graphic_symbols


def _graphic(path: Path) -> Path:
    root = ET.Element("G", {"facID": "1", "facName": "TEST F01"})
    layer = ET.SubElement(root, "Layer")
    for index, name in enumerate(("97803", "972265"), 1):
        ET.SubElement(layer, "Text", {"id": f"t{index}", "x": str(index * 100), "y": "20", "w": "50", "h": "20", "ts": name})
        ET.SubElement(layer, "TransformerDis", {
            "id": f"tr{index}", "x": str(index * 100), "y": "70", "w": "40", "h": "40",
            "composeType": "GIcon", "devref": "#Transformer_OH.pb.icn.g:Transformer_OH",
        })
    ET.SubElement(layer, "Status", {
        "id": "s1", "x": "10", "y": "10", "w": "20", "h": "20", "composeType": "GIcon",
        "devref": "#NariPd_Generator.zt.icn.g:NariPd_Generator",
    })
    ET.SubElement(layer, "CBreakerDis", {
        "id": "lbs1", "x": "10", "y": "100", "w": "28", "h": "30", "composeType": "GIcon",
        "devref": "#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART",
        "p_NameString": "Y1",
    })
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return path


def test_business_graphic_discovery_groups_devrefs_and_suggests_classification(tmp_path: Path):
    source = _graphic(tmp_path / "business.sln.pic.g")
    result = discover_graphic_symbols(source, InputMode.SINGLE_FILE, log=lambda _line: None)
    assert result["file_count"] == 1
    assert result["candidate_count"] == 3
    assert result["instance_count"] == 4

    by_ref = {row["observed_devref"]: row for row in result["candidates"]}
    transformer = by_ref["#Transformer_OH.pb.icn.g:Transformer_OH"]
    assert transformer["count"] == 2
    assert transformer["suggested_device_type"] == "Transformer"
    assert transformer["suggested_usage"] == "设备"
    assert transformer["sample_positions"]

    status = by_ref["#NariPd_Generator.zt.icn.g:NariPd_Generator"]
    assert status["suggested_usage"] == "状态图元"
    assert status["suggested_device_type"] == "Generator"

    lbs = by_ref["#Load_Breaker_Switch_SMART.zwk.icn.g:Load_Breaker_Switch_SMART"]
    assert lbs["suggested_scope"] == "SMART"
    assert lbs["suggested_usage"] == "设备组成图元"
    assert lbs["suggested_device_type"] == "LBS"


def test_discovery_metadata_alone_never_becomes_authoritative_standard():
    profile = SiteSmartProfile(
        profile_name="DISCOVERY",
        site_name="TEST",
        smart_lbs_devref="",
        smart_breaker_devref="",
        discovery_catalog={
            "#Transformer_OH.pb.icn.g:Transformer_OH": {
                "devref": "#Transformer_OH.pb.icn.g:Transformer_OH",
                "element_tag": "TransformerDis",
                "count": 139,
            }
        },
    ).normalized()
    assert profile.discovery_catalog
    assert profile.authoritative_ready is False


def test_site_profile_page_exposes_graphic_discovery_then_explicit_standard_upload():
    source = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    assert 'QGroupBox("图形 G 图元发现（只发现候选，不生成标准）")' in source
    assert 'QPushButton("扫描当前版本候选")' in source
    assert '"扫描图元 G 文件全名",' in source
    assert '"图形 G 发现 devref", "发现次数", "样本位置"' in source
    assert 'discover_graphic_symbols(' in source
    assert 'prepare_standard_file_records([path])' in source
    assert 'w×h、AlignCenter、Pins 会自动从标准图元读取' in source


def test_discovery_marks_known_rmu_internal_symbols_as_components(tmp_path: Path):
    root = ET.Element("G", {"facID": "1", "facName": "TEST F01"})
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "ZhaiWaiJieDiDaoZha", {
        "id": "g1", "composeType": "GIcon",
        "devref": "#External_grounddisconnector_new.zwjddz.icn.g:External_grounddisconnector_new",
    })
    ET.SubElement(layer, "CBreakerDis", {
        "id": "l1", "composeType": "GIcon",
        "devref": "#RMU_LBS_S.zwk.icn.g:RMU_LBS_S",
    })
    source = tmp_path / "rmu.sln.pic.g"
    ET.ElementTree(root).write(source, encoding="utf-8", xml_declaration=True)
    result = discover_graphic_symbols(source, InputMode.SINGLE_FILE, log=lambda _line: None)
    by_ref = {row["observed_devref"]: row for row in result["candidates"]}
    assert by_ref["#External_grounddisconnector_new.zwjddz.icn.g:External_grounddisconnector_new"]["suggested_usage"] == "设备组成图元"
    assert by_ref["#RMU_LBS_S.zwk.icn.g:RMU_LBS_S"]["suggested_usage"] == "设备组成图元"


def test_directory_discovery_aggregates_many_graphic_g_files(tmp_path: Path):
    _graphic(tmp_path / "a.sln.pic.g")
    _graphic(tmp_path / "b.sln.pic.g")
    result = discover_graphic_symbols(tmp_path, InputMode.DIRECTORY, log=lambda _line: None)
    assert result["file_count"] == 2
    assert result["candidate_count"] == 3
    assert result["instance_count"] == 8
    transformer = next(row for row in result["candidates"] if row["suggested_device_type"] == "Transformer")
    assert transformer["count"] == 4
    assert transformer["files"] == ["a.sln.pic.g", "b.sln.pic.g"]
