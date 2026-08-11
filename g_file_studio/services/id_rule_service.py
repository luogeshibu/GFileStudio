from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from platformdirs import user_config_dir


@dataclass(frozen=True)
class IdRule:
    tag: str
    prefix: str
    total_length: int
    enabled: bool = True
    verified: bool = True
    note: str = ""

    @property
    def sequence_width(self) -> int:
        return max(0, self.total_length - len(self.prefix))

    def matches(self, value: str) -> bool:
        """严格校验：数字、固定前缀、固定总位数三者必须同时满足。"""
        return (
            self.enabled
            and value.isdigit()
            and value.startswith(self.prefix)
            and len(value) == self.total_length
        )

    def build(self, sequence: int) -> str:
        width = self.sequence_width
        if width <= 0:
            raise ValueError(f"<{self.tag}> 的总位数必须大于前缀长度。")
        if sequence < 0:
            raise ValueError("流水序号不能为负数。")
        text = f"{self.prefix}{sequence:0{width}d}"
        if len(text) != self.total_length:
            raise ValueError(
                f"<{self.tag}> 流水 {sequence} 已超出模板 {self.prefix}+{self.total_length}位 的可用范围。"
            )
        return text

    def build_after(self, current_max_id: str | int | None) -> str:
        """同类型按完整 ID 数值 +1；结果仍必须满足前缀和总位数。"""
        if current_max_id is None:
            return self.build(1)
        text = str(current_max_id).strip()
        if not self.matches(text):
            raise ValueError(
                f"<{self.tag}> 当前最大 ID {text!r} 不符合模板：前缀 {self.prefix!r}，总位数 {self.total_length}。"
            )
        candidate = str(int(text) + 1)
        if not self.matches(candidate):
            raise ValueError(
                f"<{self.tag}> 的 ID 已增长越过模板可用范围（前缀 {self.prefix}，总位数 {self.total_length}），请人工更新模板。"
            )
        return candidate


DEFAULT_RULES: tuple[IdRule, ...] = (
    # 规则由用户提供的真实 G 文件样本确认：固定前缀 + 固定总位数。
    IdRule("Merge", "20", 8, note="用户确认：20 开头、总 8 位；同类型完整 ID 递增"),
    IdRule("rect", "2", 7, note="用户确认：2 开头、总 7 位；同类型完整 ID 递增"),
    IdRule("Text", "8", 7, note="用户确认：8 开头、总 7 位；同类型完整 ID 递增"),
    IdRule("ConnectLine", "34", 8, note="用户确认：34 开头、总 8 位；同类型完整 ID 递增"),
    IdRule("FeedLine", "35", 8, note="用户确认：35 开头、总 8 位；同类型完整 ID 递增"),
    IdRule("Bus", "30", 8, note="用户确认：30 开头、总 8 位；同类型完整 ID 递增"),
    IdRule("BusDis", "38", 8, note="用户确认：38 开头、总 8 位；同类型完整 ID 递增"),
    IdRule("CBreaker", "100", 9, note="用户确认：100 开头、总 9 位；同类型完整 ID 递增"),
    IdRule("Disconnector", "101", 9, note="用户确认：101 开头、总 9 位；同类型完整 ID 递增"),
    IdRule("GroundDisconnector", "111", 9, note="用户确认：111 开头、总 9 位；同类型完整 ID 递增"),
    IdRule("CBreakerDis", "117", 9, note="用户确认：117 开头、总 9 位；同类型完整 ID 递增"),
    IdRule("Status", "126", 9, note="用户确认：126 开头、总 9 位；同类型完整 ID 递增"),
    IdRule("pwbh", "182", 9, note="用户确认：182 开头、总 9 位；同类型完整 ID 递增"),
    IdRule("ZhaiWaiJieDiDaoZha", "188", 9, note="用户确认：188 开头、总 9 位；同类型完整 ID 递增"),
)


class IdRuleService:
    """持久化元素 ID 模板。只管理 ``id``，完全不处理 Alias。"""

    def __init__(self, json_path: str | Path | None = None) -> None:
        base = Path(user_config_dir("GFileStudio", "NARI")) / "Config"
        self.json_path = Path(json_path) if json_path is not None else base / "id_rules.json"
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.json_path.exists():
            self.save_rules(DEFAULT_RULES)

    def load_rules(self) -> dict[str, IdRule]:
        if not self.json_path.exists():
            return {rule.tag: rule for rule in DEFAULT_RULES}
        try:
            data = json.loads(self.json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"无法读取 ID 规则模板：{self.json_path}：{exc}") from exc

        result: dict[str, IdRule] = {}
        for item in data.get("rules", []):
            try:
                total_length_raw = item.get("total_length")
                if total_length_raw in (None, ""):
                    # v2.17.4 的 prefix-only 模板会在下方迁移；人工新类型缺少位数则不加载。
                    continue
                rule = IdRule(
                    tag=str(item["tag"]).strip(),
                    prefix=str(item["prefix"]).strip(),
                    total_length=int(total_length_raw),
                    enabled=bool(item.get("enabled", True)),
                    verified=bool(item.get("verified", True)),
                    note=str(item.get("note", "")),
                )
            except (KeyError, TypeError, ValueError):
                continue
            if (
                rule.tag
                and rule.prefix.isdigit()
                and rule.total_length > len(rule.prefix)
            ):
                result[rule.tag] = rule

        defaults = {rule.tag: rule for rule in DEFAULT_RULES}
        deleted_tags = {str(tag) for tag in data.get("deleted_tags", []) if str(tag).strip()}
        changed = False
        version = int(data.get("version", 1) or 1)
        # v2.17.5：恢复并锁定“前缀 + 总位数”。内置已确认类型迁移到最新规则；
        # 用户自行添加且字段完整的规则保持不变。
        if version < 4:
            for tag, default in defaults.items():
                if tag in deleted_tags:
                    continue
                current = result.get(tag)
                if current is None:
                    result[tag] = default
                    changed = True
                    continue
                if current.prefix != default.prefix or current.total_length != default.total_length:
                    result[tag] = IdRule(
                        tag=tag,
                        prefix=default.prefix,
                        total_length=default.total_length,
                        enabled=current.enabled,
                        verified=current.verified,
                        note=current.note or default.note,
                    )
                    changed = True
        else:
            # 新安装配置缺少内置类型时补齐，但绝不覆盖完整人工规则。
            for tag, default in defaults.items():
                if tag in deleted_tags:
                    continue
                if tag not in result:
                    result[tag] = default
                    changed = True

        if changed:
            self.save_rules(result.values(), deleted_tags=deleted_tags)
        return result

    def _deleted_tags(self) -> set[str]:
        if not self.json_path.exists():
            return set()
        try:
            data = json.loads(self.json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
        return {str(tag) for tag in data.get("deleted_tags", []) if str(tag).strip()}

    def save_rules(self, rules: Iterable[IdRule], deleted_tags: set[str] | None = None) -> None:
        ordered = sorted(rules, key=lambda r: r.tag.lower())
        deleted = self._deleted_tags() if deleted_tags is None else set(deleted_tags)
        payload = {
            "version": 5,
            "allocation": "per_type_full_id_increment",
            "match": "prefix_and_total_length",
            "deleted_tags": sorted(deleted),
            "rules": [asdict(rule) for rule in ordered],
        }
        tmp = self.json_path.with_suffix(self.json_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.json_path)

    def upsert(self, rule: IdRule) -> None:
        rules = self.load_rules()
        rules[rule.tag] = rule
        deleted = self._deleted_tags()
        deleted.discard(rule.tag)
        self.save_rules(rules.values(), deleted_tags=deleted)

    def remove(self, tag: str) -> None:
        rules = self.load_rules()
        rules.pop(tag, None)
        deleted = self._deleted_tags()
        deleted.add(tag)
        self.save_rules(rules.values(), deleted_tags=deleted)
