from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import io
import logging
import zipfile
from email.parser import Parser
from pathlib import Path

from pip._vendor.cachecontrol.serialize import Serializer as CCSerializer

logger = logging.getLogger(__name__)


class Deserializer(CCSerializer):
    def prepare_response(self, request, cached, body_file=None):
        return cached


@dataclasses.dataclass(frozen=True)
class WheelInfo:
    cache_path: Path
    pypi_headers: dict
    wheel_meta: dict
    contents: io.BytesIO

    @property
    def wheel_name(self) -> str:
        try:
            tag = self.wheel_meta["tag"]
        except KeyError:
            logger.warning("Synthesizing tag for %s==%s", self.project, self.version)
            tag = self.pypi_headers["python-version"] + "-none-any"
        project_u = self.project.replace("-", "_")
        return f"{project_u}-{self.version}-{tag}.whl"

    @property
    def project(self) -> str:
        return self.pypi_headers["project"]

    @property
    def version(self) -> str:
        return self.pypi_headers["version"]

    @classmethod
    def from_cache_path(cls, file: Path) -> WheelInfo | None:
        dt = Deserializer().loads(None, file.read_bytes())
        response = dt.pop("response")
        headers = response["headers"]
        ctype = headers.get("Content-Type")
        if ctype == "application/vnd.pypi.simple.v1+json":
            return None
        pypi_headers = {
            k.removeprefix("x-pypi-file-"): v
            for k, v in headers.items()
            if k.startswith("x-pypi-file-")
        }
        if pypi_headers.get("package-type") != "bdist_wheel":
            return None
        bio = io.BytesIO(response["body"])
        try:
            with zipfile.ZipFile(bio, "r") as zf:
                wheel_file = next(
                    n for n in zf.namelist() if n.endswith(".dist-info/WHEEL")
                )
                wheel_meta = {
                    k.lower(): v
                    for k, v in dict(
                        Parser().parsestr(zf.read(wheel_file).decode())
                    ).items()
                }
        except zipfile.BadZipfile:
            # logger.warning("Bad ZIP file: %s", file)
            return None
        bio.seek(0)
        return WheelInfo(
            cache_path=file,
            pypi_headers=pypi_headers,
            wheel_meta=wheel_meta,
            contents=bio,
        )


def process_cache(dest_path, cache_root, select) -> None:
    for file in (cache_root / "http").rglob("*"):
        if not file.is_file():
            continue
        wi = WheelInfo.from_cache_path(file)
        if not wi:
            continue
        wheel_name = wi.wheel_name
        if not select or any(fnmatch.fnmatch(wheel_name, pat) for pat in select):
            print(wheel_name)
            if dest_path:
                dest_name = dest_path / wheel_name
                dest_name.write_bytes(wi.contents.read())
                print("=>", dest_name)


def main():
    logging.basicConfig()
    try:
        from pip._internal.locations import USER_CACHE_DIR

        pip_cache_dir = USER_CACHE_DIR
    except Exception:
        pip_cache_dir = None
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", default=pip_cache_dir, required=(not pip_cache_dir))
    ap.add_argument("--dest-dir", default=None)
    ap.add_argument("--select", nargs="*")
    args = ap.parse_args()
    select = set(args.select or [])
    cache_root = Path(args.cache_dir)
    dest_path = Path(args.dest_dir) if args.dest_dir else None
    if dest_path:
        dest_path.mkdir(parents=True, exist_ok=True)

    process_cache(dest_path, cache_root, select)


if __name__ == "__main__":
    main()
