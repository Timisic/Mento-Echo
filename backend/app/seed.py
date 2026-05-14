from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_engine
from app.models import Participant
from app.services import log_audit, normalize_participant_code, normalize_group

DEFAULT_PARTICIPANT_CODE = "PILOT001"
DEFAULT_PARTICIPANT_GROUP = "experiment"


def seed_demo_participant() -> Participant:
    settings = get_settings()
    participant_code = normalize_participant_code(
        os.environ.get("SEED_PARTICIPANT_CODE", DEFAULT_PARTICIPANT_CODE)
    )
    assigned_group = normalize_group(os.environ.get("SEED_ASSIGNED_GROUP", DEFAULT_PARTICIPANT_GROUP))
    if assigned_group not in {"experiment", "control", None}:
        raise ValueError("SEED_ASSIGNED_GROUP must be experiment, control, or blank")

    with Session(get_engine()) as db:
        participant = db.scalar(
            select(Participant).where(Participant.participant_code == participant_code)
        )
        created = False
        if participant is None:
            participant = Participant(participant_code=participant_code, assigned_group=assigned_group)
            db.add(participant)
            created = True
        else:
            participant.assigned_group = participant.assigned_group or assigned_group
        log_audit(
            db,
            admin_id=settings.admin_username,
            action="seed_demo_participant",
            target_type="participant",
            target_id=participant_code,
            metadata={"created": created, "assigned_group": participant.assigned_group},
        )
        db.commit()
        db.refresh(participant)
        print("=== Mentor Echo 本地演示账号 ===")
        print(f"研究者账号: {settings.admin_username}")
        print(f"研究者密码: {settings.admin_password}")
        print(f"被试编号: {participant.participant_code}")
        print("被试密码: 无需密码，输入被试编号即可进入")
        print(f"预设分组: {participant.assigned_group or '首次进入时随机'}")
        return participant


if __name__ == "__main__":
    seed_demo_participant()
