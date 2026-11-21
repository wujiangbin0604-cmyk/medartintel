"""Resolve portable registry paths, including older Windows-generated entries."""
from pathlib import PurePosixPath, PureWindowsPath


def relative_artifact_path(value):
    if not isinstance(value, str) or not value:
        raise ValueError('Artifact path must be a nonempty relative string')
    relative = PurePosixPath(value.replace('\\', '/'))
    if (relative.is_absolute() or PureWindowsPath(value).drive
            or not relative.parts or '..' in relative.parts):
        raise ValueError('Artifact path must stay relative to its package')
    return relative


def artifact_path(base, value):
    base = base.resolve()
    relative = relative_artifact_path(value)
    path = base.joinpath(*relative.parts).resolve()
    if not path.is_relative_to(base):
        raise ValueError('Artifact resolves outside its package')
    return path
