"""Point every packaged version and release url at the tag being built.

config.json and the plugin catalogue both name wheels by url, and those urls carry a
version twice - once in the release tag, once in the wheel filename. Editing them by hand
is how a release ends up installing the previous one, so the tag is stamped in instead.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PYPROJECTS = (
	"api", "core", "ui",
	"plugins/avatar", "plugins/kanban", "plugins/calendar",
	"plugins/pomodoro", "plugins/stats", "plugins/manager",
)

CARRY_URLS = (
	"supervisor/samples/config.json",
	"plugins/manager/src/avatar_manager/registry.json",
)


def stamp(tag: str) -> int:
	version = tag.lstrip("v")
	if not re.fullmatch(r"\d+\.\d+\.\d+", version):
		print(f"not a version tag: {tag}", file=sys.stderr)
		return 2

	touched = 0

	for name in PYPROJECTS:
		path = ROOT / name / "pyproject.toml"
		text = path.read_text(encoding="utf-8")
		fixed = re.sub(r'^version = "\d+\.\d+\.\d+"',
		               f'version = "{version}"', text, count=1, flags=re.M)
		if fixed != text:
			path.write_text(fixed, encoding="utf-8")
			touched += 1

	for name in CARRY_URLS:
		path = ROOT / name
		text = path.read_text(encoding="utf-8")
		fixed = re.sub(r"/download/v\d+\.\d+\.\d+/", f"/download/v{version}/", text)
		fixed = re.sub(r"-\d+\.\d+\.\d+-py3-none-any\.whl",
		               f"-{version}-py3-none-any.whl", fixed)
		fixed = re.sub(r'"version": "\d+\.\d+\.\d+"', f'"version": "{version}"', fixed)
		if fixed != text:
			path.write_text(fixed, encoding="utf-8")
			touched += 1

	print(f"stamped {version} into {touched} file(s)")
	return 0


if __name__ == "__main__":
	if len(sys.argv) != 2:
		print("usage: stamp_version.py <tag>", file=sys.stderr)
		raise SystemExit(2)
	raise SystemExit(stamp(sys.argv[1]))
