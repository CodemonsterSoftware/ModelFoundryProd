from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, ButtonHolder, Div
from .models import Project, Part, Group, PurchasedPart, ProjectImage, Designer, Material, Tag

class MultipleFileInput(forms.ClearableFileInput):
    def __init__(self, attrs=None):
        super().__init__(attrs)
        if attrs is None:
            attrs = {}
        attrs['multiple'] = True
        self.attrs = attrs

    def value_from_datadict(self, data, files, name):
        if hasattr(files, 'getlist'):
            return files.getlist(name)
        return None

class TagsInput(forms.TextInput):
    template_name = 'projects/widgets/tags_input.html'

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['attrs'].update({
            'class': 'form-control',
            'data-role': 'tagsinput',
            'placeholder': 'Add tags...'
        })
        return context

class ProjectForm(forms.ModelForm):
    tags = forms.CharField(
        required=False,
        widget=TagsInput()
    )

    class Meta:
        model = Project
        fields = ['name', 'description', 'designer', 'tags']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            'name',
            'description',
            'designer',
            Div(
                'tags',
                css_class='form-group'
            )
        )
        self.fields['designer'].queryset = Designer.objects.all().order_by('name')
        if self.instance.pk:
            self.initial['tags'] = ', '.join(tag.name for tag in self.instance.tags.all())

    def clean_tags(self):
        tags = self.cleaned_data.get('tags', '')
        return [tag.strip() for tag in tags.split(',') if tag.strip()]

    def save(self, commit=True):
        instance = super().save(commit=False)  # Don't commit yet to handle m2m
        if commit:
            instance.save()
            
            # Handle tags
            tags_string = self.cleaned_data.get('tags', '')
            if isinstance(tags_string, str):
                tag_names = [name.strip().lower() for name in tags_string.split(',') if name.strip()]
            else:
                tag_names = [tag.strip().lower() for tag in tags_string if tag.strip()]
            
            # Clear existing tags
            instance.tags.clear()
            
            # Create or get tags and add them to the instance
            for tag_name in tag_names:
                if tag_name:  # Only process non-empty tags
                    tag, _ = Tag.objects.get_or_create(name=tag_name)
                    instance.tags.add(tag)
                
        return instance

class PartForm(forms.ModelForm):
    class Meta:
        model = Part
        fields = ['name', 'quantity', 'material', 'color', 'group', 'stl_file', 'thumbnail']

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        if project:
            self.fields['group'].queryset = project.groups.all()

class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name']

class PurchasedPartForm(forms.ModelForm):
    class Meta:
        model = PurchasedPart
        fields = ['name', 'price', 'quantity', 'link', 'status']

class ProjectImageForm(forms.ModelForm):
    class Meta:
        model = ProjectImage
        fields = ['image']

class BulkUploadForm(forms.Form):
    zip_file = forms.FileField(
        help_text='Upload a ZIP file containing STL files to create multiple parts at once.'
    )

class DesignerForm(forms.ModelForm):
    class Meta:
        model = Designer
        fields = ['name', 'logo', 'mmf_url', 'patreon_url', 'cults3d_url', 'website_url']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'mmf_url': forms.URLInput(attrs={'class': 'form-control'}),
            'patreon_url': forms.URLInput(attrs={'class': 'form-control'}),
            'cults3d_url': forms.URLInput(attrs={'class': 'form-control'}),
            'website_url': forms.URLInput(attrs={'class': 'form-control'}),
        }

class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['name', 'type', 'description', 'density', 'color', 'is_active', 'brand', 'link', 'cost', 'weight']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'density': forms.NumberInput(attrs={'step': '0.001'}),
            'cost': forms.NumberInput(attrs={'step': '0.01'}),
            'weight': forms.NumberInput(attrs={'step': '0.01'}),
            'color': forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
        }
        help_texts = {
            'name': 'Enter a unique name for this material',
            'description': 'Describe the material and its properties',
            'density': 'Density in grams per cubic centimeter (g/cm³) (optional)',
            'color': 'Default color for this material (optional)',
            'is_active': 'Uncheck to hide this material from selection',
            'brand': 'Manufacturer or brand name',
            'link': 'Link to purchase or product page',
            'cost': 'Total cost of the material (optional)',
            'weight': 'Total weight in grams'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='col-md-6'),
                Column('brand', css_class='col-md-6'),
            ),
            'description',
            Row(
                Column('density', css_class='col-md-6'),
                Column('color', css_class='col-md-6'),
            ),
            Row(
                Column('cost', css_class='col-md-6'),
                Column('weight', css_class='col-md-6'),
            ),
            'link',
            'is_active',
        )
        
        # Add dark mode styling to help text
        for field_name, field in self.fields.items():
            field.help_text = f'<small class="text-muted">{field.help_text}</small>'
            # Make density and cost optional
            if field_name in ['density', 'cost']:
                field.required = False 