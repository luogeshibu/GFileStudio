from datetime import datetime

from g_file_studio.services.output_naming import (
    default_merge_output_name,
    make_task_timestamp,
    marked_output_name,
    normalize_merge_output_name,
)


def test_task_timestamp_format():
    assert make_task_timestamp(datetime(2026, 7, 29, 20, 15, 9)) == "20260729_201509"


def test_default_merge_name_and_manual_name():
    assert default_merge_output_name("20260729_201509") == "MERGED-20260729_201509.sln.pic.g"
    assert normalize_merge_output_name("JED-AJWD") == "JED-AJWD.sln.pic.g"
    assert normalize_merge_output_name("JED-AJWD.sln.pic.g") == "JED-AJWD.sln.pic.g"


def test_margin_and_frame_names_have_marker_and_timestamp():
    assert marked_output_name(
        "JED-14.sln.pic.g", "-ADJUSTED", "20260729_201509"
    ) == "JED-14-ADJUSTED-20260729_201509.sln.pic.g"
    assert marked_output_name(
        "JED-14.sln.pic.g", "-WITH-FRAME", "20260729_201509"
    ) == "JED-14-WITH-FRAME-20260729_201509.sln.pic.g"
