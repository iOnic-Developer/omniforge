"""Shared script metadata and JSON input validation for dashboard and MCP."""

from __future__ import annotations

import json
import re

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError as SchemaValidationError
from referencing import Registry
from referencing.exceptions import Unresolvable
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.database import Tool, db
from app.dependencies import validate_requirements
from app.scheduling import next_run_time, validate_folder_path

BUILTIN_NAMES = frozenset({'omniforge_instructions', 'omniforge_create_tool'})
EMPTY_SCHEMA = {'type': 'object', 'properties': {}, 'additionalProperties': False}


def validate_name(name: str) -> str:
    if not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,62}', name):
        raise ValueError('Invalid tool name: use a letter followed by up to 62 letters, digits, underscores or hyphens')
    if name in BUILTIN_NAMES:
        raise ValueError('Tool name is reserved for a built-in tool')
    return name


def validate_schema(schema: dict) -> dict:
    """Use the existing MCP dependency's validator; never fetch remote refs."""
    if not isinstance(schema, dict):
        raise ValueError('inputSchema must be a JSON object')
    if not schema:
        return dict(EMPTY_SCHEMA)
    if schema.get('type') != 'object':
        raise ValueError('inputSchema must declare type object')
    if schema.get('$schema', 'https://json-schema.org/draft/2020-12/schema') != 'https://json-schema.org/draft/2020-12/schema':
        raise ValueError('Only JSON Schema Draft 2020-12 is supported')

    def check_refs(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ('$ref', '$dynamicRef') and (not isinstance(item, str) or not item.startswith('#')):
                    raise ValueError('Only local inputSchema references are supported')
                check_refs(item)
        elif isinstance(value, list):
            for item in value:
                check_refs(item)

    try:
        json.dumps(schema, allow_nan=False)
        check_refs(schema)
        Draft202012Validator.check_schema(schema)
    except (SchemaError, TypeError, RecursionError) as exc:
        raise ValueError('Invalid inputSchema') from exc
    return schema


def validate_arguments(arguments: dict, schema: dict) -> None:
    if not isinstance(arguments, dict):
        raise ValueError('arguments must be a JSON object')
    try:
        json.dumps(arguments, allow_nan=False)
        Draft202012Validator(validate_schema(schema), registry=Registry()).validate(arguments)
    except SchemaValidationError as exc:
        # Do not echo submitted values, code or secrets in validation messages.
        raise ValueError('Arguments do not match inputSchema') from exc
    except (Unresolvable, TypeError, RecursionError) as exc:
        raise ValueError('Invalid arguments or unresolved local inputSchema reference') from exc


class ScheduleIn(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')

    enabled: bool = False
    cron: str = '0 2 * * *'
    timezone: str = 'UTC'
    arguments: dict = Field(default_factory=dict)

    @model_validator(mode='after')
    def check_schedule(self):
        self.cron = ' '.join(self.cron.split())
        next_run_time(self.cron, self.timezone)
        try:
            json.dumps(self.arguments, allow_nan=False)
        except (ValueError, TypeError, RecursionError) as exc:
            raise ValueError('Scheduled arguments must be a finite JSON object') from exc
        return self


class FolderAccessIn(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')

    enabled: bool = False
    path: str = ''

    @model_validator(mode='after')
    def check_folder(self):
        if self.path or self.enabled:
            self.path = str(validate_folder_path(self.path))
        return self


class ToolIn(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')

    name: str
    description: str = ''
    language: str = 'python3'
    code: str
    requirements: list[str] = Field(default_factory=list, max_length=50)
    json_schema: dict = Field(default_factory=dict)
    is_active: bool = True
    schedule: ScheduleIn | None = None
    folder_access: FolderAccessIn | None = None

    @field_validator('name')
    @classmethod
    def check_name(cls, value: str) -> str:
        return validate_name(value)

    @field_validator('language')
    @classmethod
    def check_language(cls, value: str) -> str:
        if value not in ('python', 'python3', 'node', 'js', 'javascript'):
            raise ValueError('language must be python, python3, node, js or javascript')
        return 'python3' if value in ('python', 'python3') else 'node'

    @field_validator('code')
    @classmethod
    def check_code(cls, value: str) -> str:
        if not value.strip() or '\x00' in value:
            raise ValueError('code must be a nonempty script without NUL characters')
        return value

    @field_validator('json_schema')
    @classmethod
    def check_schema(cls, value: dict) -> dict:
        return validate_schema(value)

    @model_validator(mode='after')
    def check_requirements(self):
        self.requirements = validate_requirements(self.requirements, self.language)
        if self.schedule and self.schedule.enabled:
            validate_arguments(self.schedule.arguments, self.json_schema)
        return self


def save_tool(body: ToolIn, existing: Tool | None = None, expected_revision: str | None = None) -> Tool:
    """Save metadata only. Never install dependencies or execute code."""
    schedule = body.schedule.model_dump() if body.schedule else None
    folder_access = body.folder_access.model_dump() if body.folder_access else None
    if existing:
        if 'schedule' not in body.model_fields_set:
            schedule = existing.schedule
        if 'folder_access' not in body.model_fields_set:
            folder_access = existing.folder_access
    if schedule and schedule.get('enabled'):
        validate_arguments(schedule.get('arguments', {}), body.json_schema)
    if folder_access and folder_access.get('enabled'):
        validate_folder_path(folder_access.get('path', ''))
    tool = Tool(
        id=existing.id if existing else db.next_id(),
        name=body.name,
        description=body.description,
        language=body.language,
        code=body.code,
        requirements_json=json.dumps(body.requirements),
        json_schema_json=json.dumps(validate_schema(body.json_schema)),
        is_active=body.is_active,
        created_at=existing.created_at if existing else None,
        updated_at=None,
        schedule=schedule,
        folder_access=folder_access,
    )
    return db.upsert(tool, create_only=existing is None, expected_revision=expected_revision)
