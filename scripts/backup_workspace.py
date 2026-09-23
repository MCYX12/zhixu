"""Create a new local snapshot without deleting existing backups."""

import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from local_ai.backup import create_snapshot  # noqa: E402
from local_ai.config import load_settings  # noqa: E402
from local_ai.store import Store  # noqa: E402


def main():
    settings = load_settings()
    if not settings.database.is_file():
        raise SystemExit("当前数据库不存在，请先完成工作台初始化")
    root = ROOT / "data/backups"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = root / f"{stamp}-{uuid.uuid4().hex[:8]}"
    manifest = create_snapshot(Store(settings.database), settings, destination)
    print(f"备份及完整性校验完成：{destination}")
    print(json.dumps(manifest["counts"], ensure_ascii=False))
    print("备份包含企业资料和账号状态，请妥善保管。已有备份未删除；模型文件及原始访问密钥未复制。")


if __name__ == "__main__":
    main()
