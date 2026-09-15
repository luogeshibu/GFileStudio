from __future__ import annotations

from pathlib import Path

from g_file_studio.processors.smart_profile_processor import standard_connection_scope
from g_file_studio.services.site_profile_service import SiteSmartProfile


SMART_LBS = "#LBS.g:LBS"
SMART_CB = "#CB.g:CB"
NORMAL_LBS = "#LBS_N.g:LBS_N"
NORMAL_CB = "#CB_N.g:CB_N"
GROUND = "#GND.g:GND"


def test_shared_standard_connection_scope_exposes_single_pin_authority():
    profile = SiteSmartProfile(
        profile_name="Jeddah Connection Standard",
        site_name="Jeddah",
        smart_lbs_devref=SMART_LBS,
        smart_breaker_devref=SMART_CB,
        normal_lbs_devref=NORMAL_LBS,
        normal_breaker_devref=NORMAL_CB,
        smart_ground_devref=GROUND,
        normal_ground_devref=GROUND,
        geometry_templates={
            SMART_LBS: [{"anchor_offsets": [[0, 10], [20, 10]]}],
            SMART_CB: [{"anchor_offsets": [[0, 10], [20, 10]]}],
            NORMAL_LBS: [{"anchor_offsets": [[0, 10], [20, 10]]}],
            NORMAL_CB: [{"anchor_offsets": [[0, 10], [20, 10]]}],
            GROUND: [{"anchor_offsets": [[0, 14]]}],
        },
    )
    eligible, single_pin = standard_connection_scope(profile)
    assert {SMART_LBS, SMART_CB, NORMAL_LBS, NORMAL_CB, GROUND} <= eligible
    assert GROUND in single_pin
    assert SMART_CB not in single_pin


def test_jeddah_batch_reuses_symbol_standard_connection_cleanup_in_stage4():
    batch = Path("g_file_studio/jeddah/batch_processor.py").read_text(encoding="utf-8")
    page = Path("g_file_studio/ui/pages/jeddah_batch_page.py").read_text(encoding="utf-8")

    start = batch.index("def process_jeddah_batch")
    profile_apply = batch.index("apply_smart_profile_to_tree(", start)
    connection_cleanup = batch.index("normalize_standard_device_connections(", profile_apply)
    feeder_title = batch.index("move_feeder_titles_above_buses(", connection_cleanup)
    assert profile_apply < connection_cleanup < feeder_title

    assert "standard_connection_scope(active_rmu_profile)" in batch
    assert '"redundant_connection_line_removed_count"' in batch
    assert '"connection_line_straightened_count"' in batch
    assert '"connection_device_realigned_count"' in batch
    assert "重复贯穿 ConnectLine" in page
    assert "单 Pin" in page


def test_release_version_is_v218134():
    assert '__version__ = "2.18.148"' in Path("g_file_studio/__init__.py").read_text(encoding="utf-8")
    assert 'version = "2.18.148"' in Path("pyproject.toml").read_text(encoding="utf-8")
