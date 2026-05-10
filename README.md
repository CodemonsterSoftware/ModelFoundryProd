# ModelFoundry v2.0

<img width="1486" height="813" alt="image" src="https://github.com/user-attachments/assets/8bd36c10-a5c7-4eb7-b946-628161b3ad59" />


ModelFoundry is a premium, Django-based web application designed to help users manage, visualize, and track their 3D printing projects. Version 2.0 introduces a massive architectural overhaul featuring a highly modular 3D utility ecosystem, immersive media galleries, and a more polished "Bento Box" glassmorphic UI.

## What's New in v2.0?

- **The Forge Module Ecosystem:** We've decoupled our 3D utilities into standalone, dynamic GitHub repositories. Modules like the Grid Slicer, Etcher, and Converter can now be installed and run locally via isolated Docker virtual environments. This allows you to add modules and functionality you want without dragging along the ones you don't
- **Premium Glassmorphic UI:** A complete design overhaul utilizing modern "Bento Box" grid layouts, dynamic theming (Midnight Blue, Sunset Ember, Modern Mocha), and responsive `backdrop-filter` effects.
- **Immersive Media:** Hero layouts now feature full-bleed, edge-to-edge `SplideJS` carousels with seamless gradient fades and `GLightbox` integration for cinematic project and assembly viewing.
- **Advanced Bulk Actions:** Parts tables have been upgraded with tactile stepper trackers, live BOM (Bill of Materials) calculations, and scoped bulk Edit/Complete/Delete operations.

---

## Core Features

### Project Management
- Create and organize large 3D printing projects to get a comprehensive Bill of Materials and cost estimate before you print.
- Export and import projects for backup or sharing (now fully syncing designer metadata).
<img width="1459" height="185" alt="image" src="https://github.com/user-attachments/assets/ce381ed0-1eee-472a-8158-5afe016b6daa" />


### Advanced Part Tracking
- Add, organize, and group 3D printed parts.
- Track completion status using interactive "one-tap" progress steppers.
- Real-time BOM calculations (costs and volumes) automatically updated in the UI.
- Integrated 3D STL viewer with quick "Forge Actions" dropdowns.
<img width="1472" height="692" alt="image" src="https://github.com/user-attachments/assets/7905634a-d832-41c2-98a5-da255e4db840" />


### The Forge Ecosystem
- Install standalone 3D utilities directly from GitHub via our new `manifest.json` architecture.
- Run compute-heavy tasks safely in isolated virtual environments managed by Docker.
<img width="1482" height="805" alt="image" src="https://github.com/user-attachments/assets/e00e125b-15a4-4f71-85b4-43a1cd5f3df9" />


### Dynamic Material & Designer Management
- Create material profiles tracking cost, density, and color.
- Create designer profiles, filtering projects by creator.
- Instantly search projects and designers via real-time global search.

### Interactive Assembly Instructions
- Build step-by-step assembly guides with embedded photos and videos.
- Cinematic viewing experience via `GLightbox` with custom neon-flicker hover effects.
<img width="1459" height="568" alt="image" src="https://github.com/user-attachments/assets/2a8ba44f-57b0-4a52-bad6-ccf08b2ee758" />


---

## Installation & Deployment

**ModelFoundry v2.0 requires Docker Compose as the preferred and officially supported deployment method.** Due to the complex, multi-service architecture (which includes the core Django app, a PostgreSQL database, and a dedicated background Blender geometry processing service), running the app manually via python is only recommended for advanced module development.

### Quick Start (Docker Compose)

1. Clone the repository:
```bash
git clone https://github.com/CodemonsterSoftware/ModelFoundry.git
cd ModelFoundry
```

2. Build and start the entire stack:
```bash
docker compose up --build -d
```
*Note: This command will automatically spin up the Web App, PostgreSQL database, and Blender background service.*

3. Create your admin account (while the containers are running):
```bash
docker compose exec web python manage.py createsuperuser
```

That's it! Access ModelFoundry at `http://localhost`.

---

### Local Development (Advanced)

If you are actively developing Forge modules or modifying core Django views, you may want to run the web application locally without Docker to take advantage of your IDE's debugger.

1. Start the backend services via Docker:
```bash
docker compose up db blender -d
```
2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```
3. Install dependencies:
```bash
pip install -r requirements.txt
```
4. Run migrations and start the server:
```bash
python manage.py migrate
python manage.py runserver
```

### Upgrading ModelFoundry

**Important:** Your data is stored in Docker volumes and will persist when you upgrade, as long as you don't use the `-v` flag.

#### Safe Upgrade Process (Preserves All Data):

1. **Pull the latest code:**
   ```bash
   git pull origin main
   ```

2. **Stop the containers (data is safe - volumes persist):**
   ```bash
   docker-compose down
   ```

3. **Rebuild the images:**
   ```bash
   docker-compose build
   ```

4. **Start the services (migrations run automatically):**
   ```bash
   docker-compose up -d
   ```

5. **Verify everything is working:**
   ```bash
   docker-compose logs -f web
   ```


#### Data Backup (Recommended Before Upgrades):

Before upgrading, consider backing up your data:

```bash
# Backup database (creates a SQL dump file)
docker-compose exec db pg_dump -U postgres modelfoundry > backup_$(date +%Y%m%d_%H%M%S).sql

# List your volumes to find the exact names (project name prefix may vary)
docker volume ls | grep postgres_data

# Backup database volume (replace 'modelfoundry' with your actual project name if different)
# The volume name format is: <project_name>_postgres_data
docker run --rm \
  -v modelfoundry_postgres_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/postgres_backup_$(date +%Y%m%d_%H%M%S).tar.gz /data

# Backup media volume (uploaded files)
docker run --rm \
  -v modelfoundry_media_volume:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/media_backup_$(date +%Y%m%d_%H%M%S).tar.gz /data
```

## Project Structure

```
ModelFoundry/
├── modelfoundry/         # Main project configuration
├── forge/                # Forge Module Framework
│   ├── modules/          # Standalone module repositories
│   └── module_registry.py # Dynamic module loader
├── projects/             # Main application (Project Management)
│   ├── migrations/       # Database migrations
│   ├── static/           # Static files (CSS, JS, images)
│   ├── templates/        # HTML templates
│   ├── models.py         # Database models
│   ├── views.py          # View functions
│   ├── urls.py           # URL routing
│   └── forms.py          # Form definitions
├── blender_service/      # Background 3D geometry processing service
├── logs/                 # Application logs (automatically created)
├── requirements.txt      # Project dependencies
└── manage.py             # Django management script
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Django framework
- Bootstrap & Tailwind-inspired Layouts
- SplideJS & GLightbox for Media
- Font Awesome for icons
- THREE.js / STL library for 3D file handling
