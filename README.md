# ModelFoundry

ModelFoundry is a Django-based web application designed to help users manage their 3D printing projects. It provides a comprehensive solution for tracking parts, materials, costs, and project progress.

## Features

- **Project Management**
  - Create and organize 3D printing projects
  - Track project progress and completion status
  - Export and import projects for backup or sharing
  - Manage project images and documentation

- **Part Management**
  - Add and organize 3D printed parts
  - Upload and manage STL files
  - Track part quantities and completion status
  - Group parts for better organization
  - Calculate material costs and volumes

- **Material Management**
  - Create and manage material profiles
  - Track material costs and usage
  - Monitor material inventory
  - Set material properties (density, cost, color)

- **Purchased Parts**
  - Track purchased components
  - Monitor order status
  - Link to product pages
  - Track costs and quantities

- **Instructions**
  - Add step-by-step assembly instructions
  - Include images for each step
  - Organize instructions in order

- **Designer Management**
  - Create designer profiles
  - Track projects by designer
  - Add designer logos and information

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ModelFoundry.git
cd ModelFoundry
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up the database:
```bash
python manage.py migrate
```

5. Create a superuser:
```bash
python manage.py createsuperuser
```

6. Run the development server:
```bash
python manage.py runserver
```

## Project Structure

```
ModelFoundry/
├── modelfoundry/          # Main project configuration
├── projects/              # Main application
│   ├── migrations/        # Database migrations
│   ├── static/           # Static files (CSS, JS, images)
│   ├── templates/        # HTML templates
│   ├── models.py         # Database models
│   ├── views.py          # View functions
│   ├── urls.py           # URL routing
│   └── forms.py          # Form definitions
├── requirements.txt      # Project dependencies
└── manage.py            # Django management script
```

## Usage

1. **Creating a Project**
   - Click "Create Project" on the home page
   - Fill in project details (name, description, designer)
   - Upload project images

2. **Adding Parts**
   - Navigate to your project
   - Click "Add Parts"
   - Enter part details (name, quantity, material)
   - Upload STL files
   - Assign parts to groups

3. **Managing Materials**
   - Go to the Materials page
   - Add new materials with their properties
   - Track material usage and costs

4. **Tracking Progress**
   - Update part completion status
   - Monitor project costs
   - Track purchased parts status

## Exporting and Importing Projects

- **Export**: Click the "Export Project" button to download a ZIP file containing all project data and files
- **Import**: Use the "Import Project" button to upload a previously exported project

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
- Bootstrap for frontend styling
- Font Awesome for icons
- STL library for 3D file handling 