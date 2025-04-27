# Clean __pycache__ directories and .pyc files
# Run this script from the project root directory

# Print banner
Write-Host "Cleaning Python cache files from ModelFoundry..." -ForegroundColor Green

# Remove __pycache__ directories
Write-Host "Removing __pycache__ directories..." -ForegroundColor Cyan
$pycache_dirs = Get-ChildItem -Path . -Include "__pycache__" -Recurse -Directory | Where-Object { $_.FullName -notlike "*\venv\*" }
$count = 0

foreach ($dir in $pycache_dirs) {
    Write-Host "Removing: $($dir.FullName)" -ForegroundColor Yellow
    Remove-Item -Path $dir.FullName -Recurse -Force
    $count++
}

Write-Host "Removed $count __pycache__ directories" -ForegroundColor Green

# Remove .pyc files
Write-Host "Removing .pyc files..." -ForegroundColor Cyan
$pyc_files = Get-ChildItem -Path . -Include "*.pyc" -Recurse -File | Where-Object { $_.FullName -notlike "*\venv\*" }
$count = 0

foreach ($file in $pyc_files) {
    Write-Host "Removing: $($file.FullName)" -ForegroundColor Yellow
    Remove-Item -Path $file.FullName -Force
    $count++
}

Write-Host "Removed $count .pyc files" -ForegroundColor Green

# Remove .pyo files
Write-Host "Removing .pyo files..." -ForegroundColor Cyan
$pyo_files = Get-ChildItem -Path . -Include "*.pyo" -Recurse -File | Where-Object { $_.FullName -notlike "*\venv\*" }
$count = 0

foreach ($file in $pyo_files) {
    Write-Host "Removing: $($file.FullName)" -ForegroundColor Yellow
    Remove-Item -Path $file.FullName -Force
    $count++
}

Write-Host "Removed $count .pyo files" -ForegroundColor Green

Write-Host "Cleanup complete!" -ForegroundColor Green 