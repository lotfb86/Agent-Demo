from __future__ import annotations

from pathlib import Path

from api.services.config import get_settings


class SkillsError(RuntimeError):
    pass


def _agent_dir(agent_id: str) -> Path:
    settings = get_settings()
    path = settings.resolved_skills_dir / agent_id
    if not path.exists():
        raise SkillsError(f"Agent skills directory not found: {agent_id}")
    return path


def read_identity(agent_id: str) -> str:
    path = _agent_dir(agent_id) / "identity.md"
    if not path.exists():
        raise SkillsError(f"Identity file missing for {agent_id}")
    return path.read_text()


def read_skills(agent_id: str) -> str:
    path = _agent_dir(agent_id) / "skills.md"
    if not path.exists():
        raise SkillsError(f"Skills file missing for {agent_id}")
    return path.read_text()


def write_skills(agent_id: str, content: str) -> None:
    path = _agent_dir(agent_id) / "skills.md"
    path.write_text(content)


def append_training_instruction(agent_id: str, instruction: str) -> str:
    content = read_skills(agent_id)
    updated = content.rstrip() + "\n\n## Training Update\n- " + instruction.strip() + "\n"
    write_skills(agent_id, updated)
    return updated
