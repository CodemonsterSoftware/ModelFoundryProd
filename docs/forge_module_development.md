# ModelFoundry Forge Module Development Guide

This guide describes how to create new modules for the ModelFoundry Forge application. It is primarily written to inform AI agents and developers about the underlying architecture, data contracts, and integration points for Forge modules.

---

## Architecture Overview

ModelFoundry Forge is designed as a modular framework. Individual tools (like slicers, engravers, converters, etc.) are treated as **Modules** rather than hardcoded Django views.

Each module operates as an **isolated tool** that defines its own dependencies, user interface template, and execution backend. The Forge backend (`ModuleManager` and `ModuleRegistry`) discovers these modules dynamically, manages isolated environments (`.venv`), and orchestrates execution via decoupled backend hooks.

> **Note on Legacy Modules**: The built-in modules (Grid Slicer, Rune Etcher, Converter) predate the module framework and still use legacy hardcoded API routes (`/forge/api/slice/`, `/forge/api/etch-rune/`, etc.). All **new** modules should use the dynamic routing system described in this guide.

---

## 1. Directory Structure

Modules live in the Django app directory at `forge/modules/<module_id>/`. A folder without a valid `manifest.json` is silently skipped by the registry after logging a warning.

```
forge/modules/
└── my_module/
    ├── manifest.json       # REQUIRED: Module metadata and integration config
    ├── main.py             # Entrypoint (file name is configurable in manifest)
    ├── requirements.txt    # OPTIONAL: Pip dependencies (alternative to manifest deps)
    └── .venv/              # AUTO-GENERATED: Isolated virtual environment on install
```

---

## 2. The Manifest (`manifest.json`)

The `manifest.json` file is required for the `ModuleRegistry` to recognize and load your tool.

```json
{
    "id": "my_module",
    "name": "My Custom Module",
    "version": "1.0.0",
    "author": "Your Name",
    "description": "Short description of what this module does.",
    "icon": "bi-tools",
    "backend": "python",
    "template": "forge/my_module.html",
    "main": "main.py",
    "enabled": true,
    "download": "https://github.com/org/repo/archive/refs/heads/main.zip",
    "dependencies": {
        "pip": ["numpy", "trimesh"]
    }
}
```

### Manifest Field Reference

| Field | Required | Default | Description |
|---|---|---|---|
| `id` | Yes | — | Unique snake_case identifier. Must match the folder name. |
| `name` | No | Title-cased `id` | Human-readable display name shown in the Forge UI. |
| `version` | No | — | Semantic version string for the module. |
| `author` | No | — | Author attribution string. |
| `description` | No | `""` | Short description shown on the Forge index. |
| `icon` | No | `"bi-puzzle"` | Bootstrap Icon class displayed alongside module name. |
| `backend` | No | `"python"` | Execution engine: `"python"`, `"openscad"`, or `"blender"` (WIP). |
| `template` | No | `"forge/module_generic.html"` | Django template path for the module's UI page. |
| `main` | No | `"main.py"` | Entrypoint filename within the module directory. |
| `enabled` | No | `true` | Set to `false` to hide the module from the UI and block API calls. |
| `download` | No | — | URL to a `.zip` archive for remote installation via `ModuleManager`. |
| `dependencies.pip` | No | `[]` | Pip packages installed into the module's isolated `.venv` at install time. |

> **Important**: `"template"` must reference a real file that exists within the Django template search path. There is **no** bundled `module_generic.html` fallback — you must either create your own template or reuse an existing one like `forge/sizer.html` as a starting point.

---

## 3. URL Routes

Two URL patterns are available for every registered module. Both require an authenticated user (`@login_required`).

| Route | View | Description |
|---|---|---|
| `GET /forge/m/<module_id>/` | `module_view` | Renders the HTML UI defined by `template` in the manifest. |
| `POST /forge/api/m/<module_id>/run/` | `api_module_run` | Submits a job and executes the module's backend. |

### Shared Framework APIs (available to all module frontends)

| Route | Description |
|---|---|
| `GET /forge/api/job/<job_id>/` | Poll job status and retrieve the full `job.json` payload. |
| `GET /forge/api/download/<job_id>/` | Download the completed job's primary output file as an attachment. |
| `GET /forge/api/download/<job_id>/part/<int:index>/` | Download an individual part file by index. |
| `GET /forge/api/projects/` | List all projects belonging to the current user (id, name, groups). |
| `POST /forge/api/save-parts/` | Save output parts from a completed job into a Project/Group. |

### `POST /forge/api/save-parts/` Body

If your module produces sliced parts, you can persist them to the project library:
```json
{
  "job_id": "<uuid>",
  "project_id": 123,
  "group_name": "My Sliced Parts"
}
```

---

## 4. Execution: The `job.json` Contract

When `POST /forge/api/m/<module_id>/run/` is called, the framework:
1. Creates an isolated **Job Directory** at `MEDIA_ROOT/forge_jobs/<uuid>/`.
2. Saves any uploaded file named `input_file` into the job directory.
3. Dumps **all** POST parameters into a `params` dict as a flat `{key: string}` map.
4. Writes a `job.json` file to disk and passes its path to the backend.

> **Critical — All `params` values are strings.** `request.POST.dict()` coerces everything to `str`. Your module must explicitly cast numeric or boolean parameters:
> ```python
> threshold = float(config.get('threshold', '10.0'))
> enabled = config.get('do_repair', 'false').lower() == 'true'
> ```

### `job.json` Schema (input to your module)

```json
{
  "id": "d04a691b-6842-4de9-bfa2-...",
  "module": "my_module",
  "status": "queued",
  "input_file": "/absolute/path/to/media/forge_jobs/<uuid>/model.stl",
  "params": {
    "threshold": "10.5",
    "repair_mesh": "true",
    "custom_setting": "value"
  }
}
```

`input_file` will be `null` (JSON `null`) if no file was uploaded.

### HTTP Response from `api_module_run`

After your backend exits, the API returns this JSON to the frontend:

```json
{
  "success": true,
  "job_id": "<uuid>",
  "status": "completed",
  "message": "Execution completed",
  "payload": {
    "...all keys written back to job.json by your module..."
  }
}
```

The `payload` key contains the full merged `job.json` dict as returned by your backend. Your frontend JS can inspect `payload.parts`, `payload.output_file`, custom fields — anything you wrote back.

---

## 5. Python Backend (`"backend": "python"`)

The `PythonBackend` executes your module as an isolated subprocess using the module's `.venv`. On Linux/macOS the interpreter is `.venv/bin/python`; on Windows it is `.venv/Scripts/python.exe`. If neither exists (e.g., during local development without `ModuleManager`), it falls back to the global `python` executable with a logged warning.

**Subprocess invocation:**
```bash
python main.py /absolute/path/to/forge_jobs/<uuid>/job.json
```
The working directory (`cwd`) of the subprocess is set to the module's own directory (`forge/modules/my_module/`), so relative imports within your module work correctly.

### Python Entrypoint Contract

Your script receives exactly one positional argument: the path to `job.json`. It must:
1. Load `job.json`.
2. Read input configuration from `params` (remembering all values are strings).
3. Perform its work, writing output files into `job_dir` (the directory containing `job.json`).
4. Update the job dict with results.
5. **Write the updated dict back to `job.json`** before exiting.

The Forge backend re-reads `job.json` after your process exits and merges all keys into the HTTP response's `payload`. A non-zero exit code is treated as a failure.

### Minimal `main.py`

```python
import sys
import json
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python main.py <job.json_path>")

    job_json_path = Path(sys.argv[1])
    job_dir = job_json_path.parent  # All output files go here

    with open(job_json_path, 'r') as f:
        job = json.load(f)

    try:
        input_file = job.get('input_file')       # str path or None
        config = job.get('params', {})
        # IMPORTANT: all values from params are strings — cast explicitly
        threshold = float(config.get('threshold', '10.0'))

        output_name = "result.stl"
        output_path = job_dir / output_name

        # --- Do your actual work here ---
        # process(input_file, output_path, threshold)

        job['status'] = 'completed'
        job['output_file'] = str(output_path)
        # 'parts' is the standard list consumed by /forge/api/save-parts/
        job['parts'] = [
            {
                "filename": output_name,
                "path": str(output_path.relative_to(job_dir.parent))
            }
        ]
        # Add any extra keys you want accessible in the frontend's `payload`
        job['my_custom_result'] = {"items_processed": 42}

    except Exception as e:
        job['status'] = 'failed'
        job['error'] = str(e)

    # REQUIRED: write back before exit
    with open(job_json_path, 'w') as f:
        json.dump(job, f)

if __name__ == "__main__":
    main()
```

---

## 6. OpenSCAD Backend (`"backend": "openscad"`)

The `OpenSCADBackend` invokes the local `openscad` CLI directly. Your module's entrypoint must be a `main.scad` file. All values from `params` are automatically injected as `-D variable=value` flags.

**Generated command:**
```bash
openscad -o /path/to/forge_jobs/<uuid>/output.stl \
  -D custom_setting="value" \
  -D wall_thickness=2.5 \
  /path/to/my_module/main.scad
```

String values are quoted; numeric/boolean values are injected unquoted. The output is always written as `output.stl`. The framework automatically sets `status: completed` and builds the `parts` list on success.

---

## 7. Blender Backend (`"backend": "blender"`)

> **Status: Not yet implemented.** `BlenderBackend.run_task()` currently raises `NotImplementedError`. Do not use `"backend": "blender"` for new modules until this is resolved.

---

## 8. Building a Frontend Template

Your module's HTML template is rendered by `GET /forge/m/<module_id>/` with this context:

```python
{
    "module": { ...manifest dict... }
}
```

You have access to `{{ module.id }}`, `{{ module.name }}`, `{{ module.description }}`, etc.

The template must submit a job via `POST /forge/api/m/<module_id>/run/`. Use `multipart/form-data` encoding if you are uploading a file, otherwise standard form POST is fine.

**Minimal fetch call pattern:**
```javascript
const formData = new FormData();
formData.append('input_file', fileInput.files[0]);  // field name MUST be 'input_file'
formData.append('threshold', '10.5');
formData.append('csrfmiddlewaretoken', getCookie('csrftoken'));  // required for Django POST

const response = await fetch(`/forge/api/m/{{ module.id }}/run/`, {
    method: 'POST',
    body: formData
});
const data = await response.json();
// data.success, data.job_id, data.payload
```

---

## 9. Remote Installation via `ModuleManager`

Modules hosted on GitHub can be installed at runtime via:

```
POST /forge/install/
Body: manifest_url=https://raw.githubusercontent.com/.../manifest.json
```

The `ModuleManager` will:
1. Fetch the remote `manifest.json` and read the `download` URL.
2. Download the `.zip` archive to a temp file.
3. Strip the GitHub wrapper folder (e.g., `repo-name-main/`) and extract contents to `forge/modules/<id>/`.
4. Create an isolated `.venv` and pip-install `dependencies.pip`.
5. Also install `requirements.txt` if it exists.
6. Reload the `ModuleRegistry` singleton.

The `download` field in your manifest should point to the `.zip` archive of your module repository, e.g.:
```
https://github.com/org/repo/archive/refs/heads/main.zip
```

---

## 10. Checklist for Building a New Module

- [ ] Create `forge/modules/<my_module_id>/` directory with a valid `manifest.json`.
- [ ] The `id` in `manifest.json` must exactly match the directory name.
- [ ] Choose the correct `backend` (`python` recommended for new tools).
- [ ] Create a real Django template and reference it in `template`. There is no generic fallback template.
- [ ] In `main.py`: accept one CLI arg (path to `job.json`), cast all `params` values from string, write output to `job_dir`, and always rewrite `job.json` before exit.
- [ ] Set `job['status'] = 'completed'` on success, `'failed'` on error with `job['error'] = str(e)`.
- [ ] Populate `job['parts']` if producing files that should be downloadable or saveable to a Project.
- [ ] Use `float()` / `int()` / `.lower() == 'true'` to cast numeric and boolean params.
- [ ] Set `"enabled": false` in the manifest to safely park an incomplete module.
