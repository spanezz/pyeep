import importlib
import importlib.util
import zipimport
from pathlib import Path


def get_package_path(package_name: str) -> Path:
    """Get the filesystem directory for a Python package name."""
    # Code adapted from jinja2 PackageLoader

    # Make sure the package exists. This also makes namespace
    # packages work, otherwise get_loader returns None.
    importlib.import_module(package_name)
    if (spec := importlib.util.find_spec(package_name)) is None:
        raise AssertionError("An import spec was not found for the package.")
    if (loader := spec.loader) is None:
        raise AssertionError("A loader was not found for the package.")

    if isinstance(loader, zipimport.zipimporter):
        raise AssertionError("zip packages are not supported")

    roots: list[Path] = []

    # One element for regular packages, multiple for namespace
    # packages, or None for single module file.
    if spec.submodule_search_locations:
        roots.extend(Path(p) for p in spec.submodule_search_locations)
    # A single module file, use the parent directory instead.
    elif spec.origin is not None:
        roots.append(Path(spec.origin).parent)

    if not roots:
        raise ValueError(
            f"Cannot find search locations for package {package_name!r}"
        )

    if len(roots) > 1:
        raise ValueError(
            f"Multiple search locations found for {package_name}:"
            f" {', '.join(str(r) for r in roots)}"
        )

    return roots[0]
