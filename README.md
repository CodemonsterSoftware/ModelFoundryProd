# ModelFoundry
![image](https://github.com/user-attachments/assets/73d357c7-1b15-4aa8-8b08-127df74ceef1)

ModelFoundry is a Django-based web application designed to help users manage their 3D printing projects. It provides a comprehensive solution for tracking parts, materials, costs, and project progress.


## Features
![image](https://github.com/user-attachments/assets/3a2f6a06-22d4-43ea-907f-5dec1a2ea6ab)

- **Project Management**
  - Create and organize 3D printing projects
  - Track project progress and completion status
  - Export and import projects for backup or sharing
  - Manage project images and documentation
    
![image](https://github.com/user-attachments/assets/96cab528-10e5-4bf1-8c33-f4d51ded43b0)

- **Part Management**
  - Add and organize 3D printed parts
  - Upload and manage STL files
  - Track part quantities and completion status
  - Group parts for better organization
  - Calculate material costs and volumes
    
![image](https://github.com/user-attachments/assets/7aca590d-3901-4fbc-84b5-ba1bc400cfb0)

- **Material Management**
  - Create and manage material profiles
  - Track material costs and usage
  - Monitor material inventory
  - Set material properties (density, cost, color)
    
![image](https://github.com/user-attachments/assets/36b246d7-a323-420f-8abe-65c087d75b10)


- **Purchased Parts**
  - Track purchased components
  - Monitor order status
  - Link to product pages
  - Track costs and quantities
    
![image](https://github.com/user-attachments/assets/543be7d3-d972-4dea-9702-bbd1f43ff8c9)


- **Instructions**
  - Add step-by-step assembly instructions
  - Include images for each step
  - Organize instructions in order
    
![image](https://github.com/user-attachments/assets/43ed55e7-5dec-42a5-a90c-865fe95df8e0)


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

## Docker Deployment

ModelFoundry can be easily deployed using Docker. Here's how to get started:

1. **Build the Docker image**:
```bash
docker build -t modelfoundry .
```

2. **Create a Docker volume for persistent data**:
```bash
docker volume create modelfoundry_data
```

3. **Run the container**:
```bash
docker run -d \
  --name modelfoundry \
  -p 8000:8000 \
  -v modelfoundry_data:/app/data \
  -e DJANGO_SECRET_KEY=your-secret-key \
  -e DJANGO_DEBUG=False \
  -e DJANGO_ALLOWED_HOSTS=your-domain.com \
  modelfoundry
```

4. **Create a superuser**:
```bash
docker exec -it modelfoundry python manage.py createsuperuser
```

5. **Run migrations**:
```bash
docker exec -it modelfoundry python manage.py migrate
```

### Environment Variables

The following environment variables can be configured:

- `DJANGO_SECRET_KEY`: Django secret key for security
- `DJANGO_DEBUG`: Set to False in production
- `DJANGO_ALLOWED_HOSTS`: Comma-separated list of allowed hostnames
- `DATABASE_URL`: Database connection URL (if using external database)
- `MEDIA_ROOT`: Path to store uploaded files (default: /app/data/media)
- `STATIC_ROOT`: Path to store static files (default: /app/data/static)

### Docker Compose

For a more complete setup with a database, you can use Docker Compose:

```yaml
version: '3'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - modelfoundry_data:/app/data
    environment:
      - DJANGO_SECRET_KEY=your-secret-key
      - DJANGO_DEBUG=False
      - DJANGO_ALLOWED_HOSTS=your-domain.com
      - DATABASE_URL=postgres://postgres:postgres@db:5432/modelfoundry
    depends_on:
      - db

  db:
    image: postgres:13
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=modelfoundry
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres

volumes:
  modelfoundry_data:
  postgres_data:
```

To start the services:
```bash
docker-compose up -d
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
