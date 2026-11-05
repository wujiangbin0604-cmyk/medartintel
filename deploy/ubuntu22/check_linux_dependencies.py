"""Read-only verification of CPython 3.12 amd64 Linux wheels at official indexes."""
from __future__ import annotations

import concurrent.futures
import email
import html.parser
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit
from urllib.request import urlopen

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.tags import compatible_tags, cpython_tags
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version

HERE = Path(__file__).resolve().parent
PLATFORMS = [f"manylinux_2_{n}_x86_64" for n in range(36, 4, -1)] + ["manylinux2014_x86_64", "manylinux2010_x86_64", "manylinux1_x86_64", "linux_x86_64"]
TAGS = set(cpython_tags((3, 12), abis=["cp312"], platforms=PLATFORMS)) | set(compatible_tags((3, 12), interpreter="cp312", platforms=PLATFORMS))


def get(url):
    with urlopen(url, timeout=45) as response:
        return response.read()


def inspect_requirement(pair):
    name, version = pair
    document = json.loads(get(f"https://pypi.org/pypi/{name}/{version}/json"))
    wheels = []
    for file in document["urls"]:
        if file["filename"].endswith(".whl") and not file.get("yanked"):
            _, _, _, tags = parse_wheel_filename(file["filename"])
            if tags & TAGS:
                wheels.append(file["filename"])
    if not wheels:
        raise RuntimeError(f"No compatible Linux CPython 3.12 wheel: {name}=={version}")
    return name, {"version": version, "compatible_wheel": sorted(wheels)[0], "requires_dist": document["info"].get("requires_dist") or []}


class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for key, value in attrs:
                if key == "href": self.links.append(value)


def main():
    requirements = {}
    for line in (HERE / "requirements-runtime.txt").read_text().splitlines():
        if line and not line.startswith("#"):
            requirement = Requirement(line)
            requirements[canonicalize_name(requirement.name)] = str(next(iter(requirement.specifier)).version)
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        for name, detail in executor.map(inspect_requirement, requirements.items()):
            results[name] = detail
    parser = Links(); parser.feed(get("https://download.pytorch.org/whl/cpu/torch/").decode())
    selected = [link for link in parser.links if unquote(urlsplit(link).path).endswith("torch-2.14.1+cpu-cp312-cp312-manylinux_2_28_x86_64.whl")]
    if len(selected) != 1:
        raise RuntimeError("Expected official CPU torch 2.14.1 CPython 3.12 amd64 wheel")
    target = urlsplit(selected[0]); metadata_url = urlunsplit((target.scheme, target.netloc, target.path + ".metadata", target.query, ""))
    metadata = email.message_from_bytes(get(metadata_url))
    results["torch"] = {"version": "2.14.1+cpu", "compatible_wheel": unquote(target.path.rsplit("/", 1)[-1]), "requires_dist": metadata.get_all("Requires-Dist") or []}
    requirements["torch"] = "2.14.1+cpu"
    environment = default_environment()
    environment.update(sys_platform="linux", platform_system="Linux", os_name="posix", platform_machine="x86_64", python_version="3.12", python_full_version="3.12.10", extra="")
    for name, detail in results.items():
        for value in detail["requires_dist"]:
            req = Requirement(value)
            if req.marker and not req.marker.evaluate(environment): continue
            key = canonicalize_name(req.name)
            if key not in requirements or Version(requirements[key]) not in req.specifier:
                raise RuntimeError(f"Unresolved Linux dependency: {name} needs {req}; pinned={requirements.get(key)}")
    document = {"target": "Linux amd64 / CPython 3.12 / Debian bookworm container on Ubuntu 22.04", "compatible": True,
                "package_count": len(results), "torch_cuda_dependencies": False, "packages": dict(sorted(results.items()))}
    (HERE / "linux_dependency_check.json").write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in document.items() if k != "packages"}, indent=2))


if __name__ == "__main__": main()
