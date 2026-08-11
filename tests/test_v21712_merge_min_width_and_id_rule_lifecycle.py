from decimal import Decimal
from pathlib import Path
import xml.etree.ElementTree as ET

from g_file_studio.engines import merge_engine
from g_file_studio.services.id_rule_service import IdRule, IdRuleService


def _write_g(path: Path, body: str) -> None:
    path.write_text(f'<G w="1000" width="1000" h="800" height="800"><Layer>{body}</Layer></G>', encoding='utf-8')


def test_merge_reserves_minimum_feeder_width_before_user_gap(tmp_path: Path):
    input_dir = tmp_path / 'input'
    output_dir = tmp_path / 'output'
    input_dir.mkdir()
    _write_g(input_dir / 'a.sln.pic.g', '<Text id="8000001" x="100" y="100" w="100" h="20" ts="A"/>')
    _write_g(input_dir / 'b.sln.pic.g', '<Text id="8000002" x="50" y="100" w="100" h="20" ts="B"/>')
    infos = merge_engine.discover_files(input_dir)
    output = output_dir / 'm.sln.pic.g'
    merge_engine.merge_g_files(
        infos, output,
        gap=Decimal('300'),
        left_margin=Decimal('0'), top_margin=Decimal('0'),
        right_margin=Decimal('0'), bottom_margin=Decimal('0'),
        feeder_min_width=Decimal('1000'),
    )
    layer = ET.parse(output).getroot().find('Layer')
    texts = layer.findall('Text')
    assert len(texts) == 2
    first_x = Decimal(texts[0].get('x'))
    second_x = Decimal(texts[1].get('x'))
    # 第一张实际仅 100 宽，但占用 1000，再额外加 300 用户间隔。
    assert second_x - first_x == Decimal('1300')


def test_deleted_default_id_rule_stays_deleted_until_user_readds(tmp_path: Path):
    path = tmp_path / 'rules.json'
    service = IdRuleService(path)
    assert 'ConnectLine' in service.load_rules()
    service.remove('ConnectLine')
    assert 'ConnectLine' not in service.load_rules()
    # 模拟重启后重新创建 service，默认规则也不能偷偷恢复。
    service2 = IdRuleService(path)
    assert 'ConnectLine' not in service2.load_rules()
    service2.upsert(IdRule('ConnectLine', '34', 8, note='用户重新确认'))
    assert service2.load_rules()['ConnectLine'].matches('34000001')
