from __future__ import annotations

from pathlib import Path

import g_file_studio.services.site_profile_service as service_module
from g_file_studio.services.site_profile_service import (
    SiteProfileService,
    SiteSmartProfile,
    authoritative_geometry_templates,
)


def _icon(path: Path, tag: str, element_id: str, *, width: int = 30, height: int = 28, pin_shift: int = 0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<root><{tag} id="{element_id}" w="{width}" h="{height}" AlignCenter="15,14">'
        f'<pin id="p1" index="1" cx="15" cy="{4 + pin_shift}"/>'
        f'<pin id="p2" index="2" cx="15" cy="{24 + pin_shift}"/>'
        f'</{tag}></root>',
        encoding="utf-8",
    )
    return path


def test_managed_uploaded_icon_overrides_stale_learned_geometry_and_catalog(tmp_path: Path):
    icon = _icon(tmp_path / "SMART_LBS.g", "CBreakerDis", "SMART_LBS", width=30, height=28)
    service = SiteProfileService(tmp_path / "profiles.json")
    record = service.prepare_standard_file_records([icon])[0]
    devref = str(record["devref"])

    profile = SiteSmartProfile(
        profile_name="P",
        site_name="S",
        smart_lbs_devref=devref,
        smart_breaker_devref=devref,
        geometry_templates={
            devref: [{"rotation": 0, "width": 999, "height": 888, "anchor_offsets": [[1, 1], [2, 2]]}]
        },
        symbol_catalog={
            devref: {
                "devref": devref,
                "element_tag": "CBreakerDis",
                "element_id": "STALE",
                "source_file": "business-drawing.g",
                "width": 999,
                "height": 888,
                "align_center": [1, 1],
                "pins": [[1, 1], [2, 2]],
            }
        },
        managed_standard_files=[record],
    ).normalized()

    assert profile.symbol_catalog[devref]["source_file"] == "SMART_LBS.g"
    assert profile.symbol_catalog[devref]["width"] == 30
    assert profile.symbol_catalog[devref]["height"] == 28
    rows = authoritative_geometry_templates(profile)[devref]
    assert {row["rotation"] for row in rows} == {0, 90, 180, 270}
    assert all(row["width"] == 30 for row in rows)
    assert all(row["height"] == 28 for row in rows)
    assert not any(row["width"] == 999 for row in profile.geometry_templates[devref])


def test_saved_authoritative_standard_keeps_pin_identity_and_is_ready(tmp_path: Path, monkeypatch):
    user_data = tmp_path / "user-data"
    monkeypatch.setattr(service_module, "user_data_dir", lambda *_args, **_kwargs: str(user_data))
    source = tmp_path / "icons"
    paths = [
        _icon(source / "smart_lbs.g", "CBreakerDis", "SMART_LBS"),
        _icon(source / "smart_cb.g", "CBreakerDis", "SMART_CB"),
        _icon(source / "smart_ground.g", "ZhaiWaiJieDiDaoZha", "SMART_GROUND"),
        _icon(source / "normal_lbs.g", "CBreakerDis", "NORMAL_LBS"),
        _icon(source / "normal_cb.g", "CBreakerDis", "NORMAL_CB"),
        _icon(source / "normal_ground.g", "ZhaiWaiJieDiDaoZha", "NORMAL_GROUND"),
    ]
    service = SiteProfileService(tmp_path / "profiles.json")
    records = service.prepare_standard_file_records(paths)
    by_name = {str(row["original_name"]): str(row["devref"]) for row in records}
    assert all(row["pin_indices"] == ["1", "2"] for row in records)

    saved = service.upsert(SiteSmartProfile(
        profile_name="AUTH",
        site_name="Jeddah",
        smart_lbs_devref=by_name["smart_lbs.g"],
        smart_breaker_devref=by_name["smart_cb.g"],
        smart_ground_devref=by_name["smart_ground.g"],
        normal_lbs_devref=by_name["normal_lbs.g"],
        normal_breaker_devref=by_name["normal_cb.g"],
        normal_ground_devref=by_name["normal_ground.g"],
        managed_standard_files=records,
        # stale values must not become the standard
        geometry_templates={by_name["smart_lbs.g"]: [{"rotation": 0, "width": 777, "height": 777, "anchor_offsets": [[1, 1]]}]},
    ))
    ready, issues = service.validate_authoritative_standard(saved)
    assert ready is True, issues
    assert saved.standard_fingerprint
    assert authoritative_geometry_templates(saved)[by_name["smart_lbs.g"]][0]["width"] == 30


def test_ui_and_processor_make_uploaded_g_the_explicit_authority():
    page = Path("g_file_studio/ui/pages/site_profile_page.py").read_text(encoding="utf-8")
    processor = Path("g_file_studio/processors/smart_profile_processor.py").read_text(encoding="utf-8")
    engine = Path("g_file_studio/engines/smart_profile_engine.py").read_text(encoding="utf-8")
    assert 'QPushButton("为选中角色上传 / 更新标准 G")' in page
    assert '"标准来源", "状态"' in page
    assert "业务单线图不会参与 devref、尺寸、AlignCenter 或 pin 标准的生成" in page
    assert "authoritative_geometry_templates(profile)" in processor
    assert "allow_source_geometry_fallback=not managed" in processor
    assert "allow_source_geometry_fallback: bool = True" in engine


def test_authoritative_check_rejects_business_symbol_not_in_uploaded_standard(tmp_path: Path, monkeypatch):
    import xml.etree.ElementTree as ET

    from g_file_studio.models import InputMode
    from g_file_studio.processors.smart_profile_processor import (
        SmartProfileProcessingSettings,
        process_smart_profile_consistency,
    )

    user_data = tmp_path / "user-data-strict"
    monkeypatch.setattr(service_module, "user_data_dir", lambda *_args, **_kwargs: str(user_data))
    icon_dir = tmp_path / "icons-strict"
    paths = [
        _icon(icon_dir / "Load_Breaker_Switch_SMART.zwk.icn.g", "CBreakerDis", "Load_Breaker_Switch_SMART", width=28, height=30),
        _icon(icon_dir / "Circuit_Breaker_SMART.zwk.icn.g", "CBreakerDis", "Circuit_Breaker_SMART", width=30, height=30),
        _icon(icon_dir / "External_grounddisconnector_new.zwjddz.icn.g", "ZhaiWaiJieDiDaoZha", "External_grounddisconnector_new", width=20, height=20),
        _icon(icon_dir / "Load_Breaker_Switch_NON-SMART.zwk.icn.g", "CBreakerDis", "Load_Breaker_Switch_NON-SMART", width=28, height=30),
        _icon(icon_dir / "Circuit_Breaker_NO-SMART.zwk.icn.g", "CBreakerDis", "Circuit_Breaker_NO-SMART", width=30, height=30),
    ]
    service = SiteProfileService(tmp_path / "profiles-strict.json")
    records = service.prepare_standard_file_records(paths)
    devrefs = {str(row["original_name"]): str(row["devref"]) for row in records}
    ground = devrefs["External_grounddisconnector_new.zwjddz.icn.g"]
    profile = service.upsert(SiteSmartProfile(
        profile_name="STRICT",
        site_name="Jeddah",
        smart_lbs_devref=devrefs["Load_Breaker_Switch_SMART.zwk.icn.g"],
        smart_breaker_devref=devrefs["Circuit_Breaker_SMART.zwk.icn.g"],
        smart_ground_devref=ground,
        normal_lbs_devref=devrefs["Load_Breaker_Switch_NON-SMART.zwk.icn.g"],
        normal_breaker_devref=devrefs["Circuit_Breaker_NO-SMART.zwk.icn.g"],
        normal_ground_devref=ground,
        managed_standard_files=records,
    ))
    ready, issues = service.validate_authoritative_standard(profile)
    assert ready, issues

    target = tmp_path / "business.g"
    root = ET.Element("G")
    layer = ET.SubElement(root, "Layer")
    ET.SubElement(layer, "rect", id="2000001", x="100", y="100", w="240", h="220")
    ET.SubElement(layer, "BusDis", id="38000001", x="215", y="145", w="8", h="130", key_name="1001_BUS")
    ET.SubElement(
        layer, "CBreakerDis", id="117000001", x="145", y="150", w="28", h="30",
        p_NameString="Y1", devref="#Legacy_LBS.zwk.icn.g:Legacy_LBS",
    )
    ET.SubElement(
        layer, "CBreakerDis", id="117000002", x="245", y="205", w="30", h="30",
        p_NameString="Q1", devref=profile.smart_breaker_devref,
    )
    ET.SubElement(
        layer, "ZhaiWaiJieDiDaoZha", id="188000001", x="285", y="180", w="20", h="20",
        devref=ground,
    )
    ET.SubElement(layer, "Text", id="8000001", ts="1001", x="155", y="45", w="120", h="50")
    ET.SubElement(layer, "Text", id="8000002", ts="SMART", x="185", y="103", w="70", h="22", fs="20")
    ET.ElementTree(root).write(target, encoding="utf-8", xml_declaration=True)

    result = process_smart_profile_consistency(
        SmartProfileProcessingSettings(
            source_path=target,
            input_mode=InputMode.SINGLE_FILE,
            output_dir=tmp_path / "run-strict",
            profile=profile,
            require_authoritative_standard=True,
        ),
        log=lambda _msg: None,
    )
    assert result.statistics["Nonstandard Symbols"] >= 1
    assert any("图元变体不符合标准" in warning for warning in result.warnings)
    assert any(profile.smart_lbs_devref in warning for warning in result.warnings)
