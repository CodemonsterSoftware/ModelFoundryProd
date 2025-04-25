from django.db import models
from django.utils import timezone
from django.db.models import Sum
from django.contrib.auth.models import User
from stl import mesh
import os
import numpy as np
from decimal import Decimal

class Designer(models.Model):
    name = models.CharField(max_length=100)
    logo = models.ImageField(upload_to='designer_logos/', null=True, blank=True)
    mmf_url = models.URLField(max_length=200, blank=True, null=True)
    patreon_url = models.URLField(max_length=200, blank=True, null=True)
    cults3d_url = models.URLField(max_length=200, blank=True, null=True)
    website_url = models.URLField(max_length=200, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class Project(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    designer = models.ForeignKey(Designer, on_delete=models.SET_NULL, null=True, blank=True, related_name='projects')
    tags = models.ManyToManyField(Tag, blank=True, related_name='projects')

    @property
    def total_parts(self):
        return self.parts.aggregate(total=Sum('quantity'))['total'] or 0

    @property
    def material_counts(self):
        counts = {}
        for part in self.parts.all():
            if part.material:
                counts[part.material] = counts.get(part.material, 0) + part.quantity
        return counts

    @property
    def total_cost(self):
        """
        Calculate the total cost of the project including both printed and purchased parts.
        Returns the total cost as a float.
        """
        total = Decimal('0')
        
        # Add costs of printed parts
        for part in self.parts.all():
            if part.material_cost:
                total += Decimal(str(part.material_cost)) * part.quantity
        
        # Add costs of purchased parts
        for purchased_part in self.purchased_parts.all():
            total += purchased_part.price * purchased_part.quantity
            
        return float(total)

    def __str__(self):
        return self.name

class Group(models.Model):
    name = models.CharField(max_length=200)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='groups')

    def __str__(self):
        return self.name

class Material(models.Model):
    MATERIAL_TYPES = [
        ('PLA', 'PLA'),
        ('ABS', 'ABS'),
        ('PETG', 'PETG'),
        ('TPU', 'TPU'),
        ('Nylon', 'Nylon'),
        ('PC', 'Polycarbonate'),
        ('ASA', 'ASA'),
        ('HIPS', 'HIPS'),
        ('PVA', 'PVA'),
        ('Resin', 'Resin'),
        ('Other', 'Other'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=20, choices=MATERIAL_TYPES, default='PLA')
    description = models.TextField(blank=True)
    density = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, help_text='Density in grams per cubic centimeter (g/cm³)')
    color = models.CharField(max_length=50, blank=True, help_text='Default color for this material (optional)')
    is_active = models.BooleanField(default=True)
    brand = models.CharField(max_length=100, blank=True, help_text='Manufacturer or brand name')
    link = models.URLField(max_length=200, blank=True, help_text='Link to purchase or product page')
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text='Total cost of the material')
    weight = models.DecimalField(max_digits=10, decimal_places=2, help_text='Total weight in grams')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def cost_per_kg(self):
        if self.weight and self.cost:
            # Convert weight from grams to kilograms and calculate cost per kg
            return (self.cost / self.weight) * 1000
        return None

    @property
    def total_used(self):
        """Calculate total material used in grams based on completed parts and density"""
        total_volume = Decimal('0')
        
        # Get all completed parts that use this material
        completed_parts = Part.objects.filter(material=self, completed=True)
        
        for part in completed_parts:
            if part.volume:
                # Convert volume from mm³ to cm³ (divide by 1000)
                volume_cm3 = Decimal(str(part.volume)) / Decimal('1000')
                total_volume += volume_cm3 * part.quantity
        
        # Convert volume to grams using density
        if self.density and total_volume:
            return total_volume * self.density
        return Decimal('0')

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"

    class Meta:
        ordering = ['name']

class Part(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='parts')
    name = models.CharField(max_length=200)
    quantity = models.IntegerField(default=1)
    material = models.ForeignKey(Material, on_delete=models.SET_NULL, null=True, blank=True, related_name='parts')
    material_name = models.CharField(max_length=100, blank=True)  # Keep for backward compatibility
    color = models.CharField(max_length=50, blank=True)
    completed = models.IntegerField(default=0)
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, related_name='parts')
    stl_file = models.FileField(upload_to='stl_files/', blank=True)
    thumbnail = models.ImageField(upload_to='thumbnails/', blank=True)
    volume = models.FloatField(null=True, blank=True, help_text="Volume in cubic millimeters")

    def __str__(self):
        return self.name

    @property
    def material_cost(self):
        """
        Calculate the material cost for this part.
        
        Units:
        - Volume: stored in mm³, converted to cm³ (divide by 1000)
        - Density: stored in g/cm³
        - Cost: stored in $/kg
        
        Calculation steps:
        1. Convert volume from mm³ to cm³ (divide by 1000)
        2. Calculate mass in grams: volume_cm³ × density_g/cm³
        3. Convert mass to kg (divide by 1000)
        4. Calculate cost: mass_kg × cost_$/kg
        """
        if not self.volume or not self.material:
            return None
            
        try:
            # Convert volume from mm³ to cm³ (1 cm³ = 1000 mm³)
            volume_cm3 = Decimal(str(self.volume)) / Decimal('1000')
            
            # Calculate mass in grams: volume (cm³) × density (g/cm³)
            mass_g = volume_cm3 * self.material.density
            
            # Convert mass to kg (1 kg = 1000 g) and calculate cost
            mass_kg = mass_g / Decimal('1000')
            cost = mass_kg * self.material.cost_per_kg
            
            return float(cost)  # Convert back to float for JSON serialization
        except (TypeError, ValueError, InvalidOperation):
            return None

    def calculate_volume(self):
        """Calculate the volume of the STL file in cubic millimeters."""
        if not self.stl_file:
            print(f"No STL file for part {self.name}")
            return None
            
        try:
            # Get the absolute path of the STL file
            stl_path = self.stl_file.path
            print(f"Calculating volume for {self.name} using file: {stl_path}")
            
            # Check if file exists
            if not os.path.exists(stl_path):
                print(f"STL file not found at path: {stl_path}")
                return None
                
            # Read the STL file
            mesh_data = mesh.Mesh.from_file(stl_path)
            
            # Calculate volume using the mesh's vertices and faces
            volume = 0
            for triangle in mesh_data.vectors:
                # Calculate the signed volume of the tetrahedron formed by the triangle and the origin
                v1, v2, v3 = triangle
                volume += np.dot(v1, np.cross(v2, v3)) / 6.0
            
            # Convert to cubic millimeters (assuming the STL is in millimeters)
            volume_mm3 = abs(volume)  # Volume can be negative depending on face orientation
            
            print(f"Volume calculated for {self.name}: {volume_mm3} mm³")
            return volume_mm3
            
        except Exception as e:
            print(f"Error calculating volume for part {self.name}: {str(e)}")
            return None

    def save(self, *args, **kwargs):
        # Calculate volume before saving if there's an STL file
        if self.stl_file and (not self.volume or self._state.adding):
            print(f"Calculating volume for part {self.name}")
            self.volume = self.calculate_volume()
        super().save(*args, **kwargs)

class PurchasedPart(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('ordered', 'Ordered'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='purchased_parts')
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField(default=1)
    link = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return self.name

class ProjectImage(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='project_images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.project.name}"

class Instructions(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='instructions')
    image = models.ImageField(upload_to='instructions/', help_text='Image for this instruction step')
    description = models.TextField(blank=True, help_text='Description of this instruction step')
    order = models.PositiveIntegerField(default=0, help_text='Order in which this instruction should be displayed')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']
        verbose_name_plural = 'Instructions'

    def __str__(self):
        return f"Step {self.order} - {self.project.name}"
