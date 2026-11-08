import json
import os
import tempfile
import warnings
from pathlib import Path

import yaml


def records(path: Path):
    with path.open("rb") as stream:
        for line, raw in enumerate(stream, 1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except (ValueError, UnicodeError, RecursionError):
                if not raw.endswith(b"\n"):
                    warnings.warn(f"{path.name} line {line}: incomplete final record")
                    break
                raise ValueError(f"{path.name} line {line}: invalid JSON") from None
            if not isinstance(row, dict):
                raise ValueError(f"{path.name} line {line}: expected an object")
            yield row


def atomic(path: Path, data: str):
    path.parent.mkdir(exist_ok=True, parents=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf8", dir=path.parent, delete=False) as file:
        temp = Path(file.name)
        try:
            file.write(data)
            file.flush()
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)


class UniqueLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        mapping = super().construct_mapping(node, deep=deep)
        if len(mapping) != len(node.value):
            raise ValueError("duplicate YAML field")
        return mapping


def read_yaml(path):
    try:
        return yaml.load(path.read_text(), Loader=UniqueLoader)
    except yaml.YAMLError:
        raise ValueError(f"{path.name}: invalid YAML") from None
