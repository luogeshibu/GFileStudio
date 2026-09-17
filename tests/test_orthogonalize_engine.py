from __future__ import annotations

import xml.etree.ElementTree as ET

from g_file_studio.engines.orthogonalize_engine import orthogonalize_tree


def _tree(xml: str) -> ET.ElementTree:
    return ET.ElementTree(ET.fromstring(xml))


def test_diagonal_line_gets_right_angle_without_changing_endpoints_or_topology():
    tree = _tree(
        '''<G><Layer>
        <CBreakerDis id="117" x="0" y="0" w="20" h="20" />
        <TransformerDis id="118" x="100" y="100" w="20" h="20" />
        <ConnectLine id="340" d="20,10 100,100" x="17" y="7" w="86" h="96"
            link="0,0,117;1,0,118" node_area="0,0,117;1,0,118" />
        <Text id="900" x="50" y="50" w="20" h="10">设备名</Text>
        <DText id="901" x="51" y="51" w="20" h="10">0.00</DText>
        </Layer></G>'''
    )
    line = tree.getroot().find("Layer/ConnectLine")
    assert line is not None
    before_refs = (line.get("link"), line.get("node_area"))

    result = orthogonalize_tree(tree)

    assert result.inspected_lines == 1
    assert result.changed_lines == 1
    points = [tuple(map(float, token.split(","))) for token in line.get("d").split()]
    assert points[0] == (20.0, 10.0)
    assert points[-1] == (100.0, 100.0)
    assert len(points) == 3
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in zip(points, points[1:]))
    assert (line.get("link"), line.get("node_area")) == before_refs
    assert tree.getroot().find("Layer/Text").text == "设备名"
    assert tree.getroot().find("Layer/DText").text == "0.00"


def test_line_is_skipped_when_both_elbows_cross_an_unrelated_device():
    tree = _tree(
        '''<G><Layer>
        <TransformerDis id="999" x="45" y="-5" w="10" h="110" />
        <ConnectLine id="340" d="0,0 100,100" />
        </Layer></G>'''
    )

    result = orthogonalize_tree(tree)

    assert result.changed_lines == 0
    assert result.skipped_lines == 1
    assert tree.getroot().find("Layer/ConnectLine").get("d") == "0,0 100,100"


def test_bus_endpoint_attributes_follow_the_unchanged_route_endpoints():
    tree = _tree(
        '''<G><Layer>
        <Bus id="300" d="0,0 40,20" x1="0" y1="0" x2="40" y2="20" />
        </Layer></G>'''
    )

    result = orthogonalize_tree(tree)
    bus = tree.getroot().find("Layer/Bus")

    assert result.changed_lines == 1
    assert bus is not None
    assert bus.get("x1") == "0"
    assert bus.get("y1") == "0"
    assert bus.get("x2") == "40"
    assert bus.get("y2") == "20"


def test_same_standard_devices_align_and_connected_line_endpoints_follow_them():
    tree = _tree(
        '''<G><Layer>
        <CBreakerDis id="a" x="100" y="0" w="20" h="20" devref="std:breaker" />
        <CBreakerDis id="b" x="106" y="100" w="20" h="20" devref="std:breaker" />
        <TransformerDis id="e1" x="200" y="10" w="20" h="20" devref="std:transformer" />
        <TransformerDis id="e2" x="200" y="110" w="20" h="20" devref="std:transformer" />
        <ConnectLine id="l1" d="110,20 200,20" link="0,0,a;1,0,e1" />
        <ConnectLine id="l2" d="116,120 200,120" link="0,0,b;1,0,e2" />
        <Text id="name" x="108" y="-30" w="40" h="10">设备名称</Text>
        <DText id="measure" x="108" y="-45" w="40" h="10">0.00</DText>
        </Layer></G>'''
    )

    result = orthogonalize_tree(tree)

    layer = tree.getroot().find("Layer")
    assert layer is not None
    first = layer.find("CBreakerDis[@id='a']")
    second = layer.find("CBreakerDis[@id='b']")
    line1 = layer.find("ConnectLine[@id='l1']")
    line2 = layer.find("ConnectLine[@id='l2']")
    assert first is not None and second is not None
    assert line1 is not None and line2 is not None
    assert first.get("x") == "103"
    assert second.get("x") == "103"
    assert line1.get("d").split()[0] == "113,20"
    assert line2.get("d").split()[0] == "113,120"
    assert result.aligned_devices == 2
    assert result.aligned_lines == 2
    assert layer.find("Text").text == "设备名称"
    assert layer.find("DText").text == "0.00"


def test_confirmed_two_device_line_is_redrawn_in_place_with_same_identity():
    tree = _tree(
        '''<G><Layer>
        <CBreakerDis id="a" x="0" y="0" w="20" h="20" devref="std:breaker" />
        <TransformerDis id="b" x="100" y="100" w="20" h="20" devref="std:transformer" />
        <ConnectLine id="branch-a" d="0,10 20,10" node_area="0,0,a" />
        <ConnectLine id="branch-b" d="120,110 140,110" node_area="0,0,b" />
        <ConnectLine id="route" d="20,10 100,100" link="0,0,a;1,0,b" node_area="0,0,a;1,0,b" />
        </Layer></G>'''
    )
    line = tree.getroot().find("Layer/ConnectLine[@id='route']")
    assert line is not None
    before_id = line.get("id")
    before_link = line.get("link")
    before_node_area = line.get("node_area")

    result = orthogonalize_tree(tree)

    points = [tuple(map(float, token.split(","))) for token in line.get("d").split()]
    assert result.rebuilt_lines == 1
    assert result.changed_lines == 0
    assert before_id == line.get("id") == "route"
    assert before_link == line.get("link")
    assert before_node_area == line.get("node_area")
    assert points[0] == (20.0, 10.0)
    assert points[-1] == (100.0, 100.0)
    assert len(points) == 3
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in zip(points, points[1:]))


def test_unlike_device_leaf_moves_so_real_connection_points_share_an_axis():
    tree = _tree(
        '''<G><Layer>
        <CBreakerDis id="a" x="0" y="0" w="20" h="20" devref="std:breaker" />
        <TransformerDis id="b" x="140" y="100" w="20" h="20" devref="std:transformer" />
        <ConnectLine id="route" d="20,10 140,100"
            link="0,0,a;1,0,b" node_area="0,0,a;1,0,b" />
        </Layer></G>'''
    )
    layer = tree.getroot().find("Layer")
    assert layer is not None
    line = layer.find("ConnectLine[@id='route']")
    device = layer.find("CBreakerDis[@id='a']")
    assert line is not None and device is not None

    result = orthogonalize_tree(tree)

    points = [tuple(map(float, token.split(","))) for token in line.get("d").split()]
    assert result.connection_aligned_lines == 1
    assert result.aligned_devices == 1
    assert result.rebuilt_lines == 0
    assert device.get("y") == "90"
    assert points == [(20.0, 100.0), (140.0, 100.0)]
    assert line.get("link") == "0,0,a;1,0,b"
    assert line.get("node_area") == "0,0,a;1,0,b"
