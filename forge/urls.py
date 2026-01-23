from django.urls import path
from . import views

app_name = 'forge'

urlpatterns = [
    path('', views.forge_index, name='index'),
    path('convert/', views.convert_stl, name='convert'),
    path('slice/', views.slice_model, name='slice'),
    path('rune/', views.rune_etcher, name='rune_etcher'),
    
    # API endpoints
    path('api/convert/', views.api_convert, name='api_convert'),
    path('api/slice/', views.api_slice, name='api_slice'),
    path('api/etch/', views.api_etch_rune, name='api_etch_rune'),
    path('api/read-rune/', views.api_read_rune, name='api_read_rune'),
    path('api/projects/', views.api_projects, name='api_projects'),
    path('api/save-parts/', views.api_save_job_parts, name='api_save_job_parts'),
    path('api/job/<str:job_id>/', views.api_job_status, name='api_job_status'),
    path('api/download/<str:job_id>/', views.api_download, name='api_download'),
    path('api/download/<str:job_id>/part/<int:part_index>/', views.api_download_part, name='api_download_part'),
]
