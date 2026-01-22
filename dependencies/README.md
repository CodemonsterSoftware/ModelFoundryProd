# Local Dependencies

This folder is used to provide pre-downloaded Python wheels for packages that are not available on PyPI or are difficult to compile, specifically `pythonocc-core`.

## Instructions

1.  **Download the Wheel:**
    You need to find a compatible wheel for `pythonocc-core`.
    *   **For Docker (Linux/Python 3.11):** Look for a file named like `pythonocc_core-7.8.1-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`.
    *   **For Local (Windows/Python 3.13):** You likely need `pythonocc_core-7.8.1-cp313-win_amd64.whl`. (Note: Python 3.13 support might be experimental or unavailable; 3.11/3.12 is safer).

    *Download Source:* Official wheels are rare. You may need to look for community builds or use `conda build` to convert a conda package to a wheel. If you cannot find a wheel, consider switching to a Conda-based Docker image.

2.  **Place the file here:**
    Drop the `.whl` file directly into this `dependencies/` folder.

3.  **Build/Run:**
    The `Dockerfile` has been updated to copy this folder and look for wheels inside it during `pip install`.
