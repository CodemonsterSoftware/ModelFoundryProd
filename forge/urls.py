from django.urls import path
from . import views

app_name = 'forge'

urlpatterns = [
    # Core framework views
    path('', views.forge_index, name='index'),
    path('install/', views.install_module, name='install_module'),
    path('uninstall/<str:module_id>/', views.uninstall_module, name='uninstall_module'),
    
    # Common job APIs used by all modules
    path('api/job/<str:job_id>/', views.api_job_status, name='api_job_status'),
    path('api/download/<str:job_id>/', views.api_download, name='api_download'),
    path('api/download/<str:job_id>/part/<int:part_index>/', views.api_download_part, name='api_download_part'),
    path('api/projects/', views.api_projects, name='api_projects'),
    path('api/save-parts/', views.api_save_job_parts, name='api_save_job_parts'),
    
    

    # Dynamic Module routing catch-all
    # e.g., /forge/m/grid_slicer/
    path('m/<str:module_id>/', views.module_view, name='module_view'),
    path('api/m/<str:module_id>/run/', views.api_module_run, name='api_module_run'),
]
