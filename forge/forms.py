from django import forms


class STLUploadForm(forms.Form):
    """Form for STL file upload (used by both conversion and slicing)."""
    stl_file = forms.FileField(
        label='STL File',
        help_text='Upload an STL file to process'
    )


class ConvertForm(STLUploadForm):
    """Form for STL to STEP conversion."""
    repair_mesh = forms.BooleanField(
        required=False,
        initial=True,
        label='Repair mesh before conversion',
        help_text='Fix holes and inconsistent normals'
    )
    tolerance = forms.FloatField(
        required=False,
        initial=0.1,
        min_value=0.001,
        max_value=1.0,
        label='Sewing tolerance (mm)',
        help_text='Tolerance for joining mesh faces'
    )


class SliceForm(STLUploadForm):
    """Form for grid-based slicing with joint options."""
    
    # Mode selection
    MODE_CHOICES = [
        ('uniform', 'Uniform Grid'),
        ('freeform', 'Freeform Planes'),
    ]
    slice_mode = forms.ChoiceField(
        choices=MODE_CHOICES,
        initial='uniform',
        widget=forms.HiddenInput
    )

    # Freeform plane data (JSON string of plane objects)
    freeform_planes = forms.CharField(required=False, widget=forms.HiddenInput)

    # Grid configuration
    grid_x = forms.IntegerField(
        initial=2,
        min_value=0,
        max_value=10,
        label='X divisions'
    )
    grid_y = forms.IntegerField(
        initial=2,
        min_value=0,
        max_value=10,
        label='Y divisions'
    )
    grid_z = forms.IntegerField(
        initial=1,
        min_value=0,
        max_value=10,
        label='Z divisions'
    )
    
    # Joint type selection
    JOINT_CHOICES = [
        ('none', 'No joints'),
        ('pins', 'Alignment Pins (peg + hole)'),
        ('dowels', 'Dowel Holes (hole + hole)'),
        ('dovetails', 'Dovetail Joints'),
    ]
    joint_type = forms.ChoiceField(
        choices=JOINT_CHOICES,
        initial='pins',
        label='Joint type',
        widget=forms.RadioSelect
    )
    
    # Pin/Dowel parameters
    joint_diameter = forms.FloatField(
        required=False,
        initial=4.0,
        min_value=1.0,
        max_value=20.0,
        label='Pin/Dowel diameter (mm)'
    )
    joint_height = forms.FloatField(
        required=False,
        initial=5.0,
        min_value=2.0,
        max_value=30.0,
        label='Pin height / Dowel hole depth (mm)'
    )
    joint_clearance = forms.FloatField(
        required=False,
        initial=0.2,
        min_value=0.05,
        max_value=1.0,
        label='Clearance (mm)'
    )
    joint_count = forms.IntegerField(
        required=False,
        initial=0,
        min_value=0,
        max_value=20,
        label='Joints per edge (0 = auto)'
    )
    
    # Dovetail parameters
    dovetail_angle = forms.FloatField(
        required=False,
        initial=14.0,
        min_value=5.0,
        max_value=30.0,
        label='Dovetail angle (degrees)'
    )
    dovetail_width = forms.FloatField(
        required=False,
        initial=15.0,
        min_value=5.0,
        max_value=50.0,
        label='Dovetail width (mm)'
    )
    dovetail_depth = forms.FloatField(
        required=False,
        initial=10.0,
        min_value=3.0,
        max_value=30.0,
        label='Dovetail depth (mm)'
    )
    dovetail_count = forms.IntegerField(
        required=False,
        initial=0,
        min_value=0,
        max_value=10,
        label='Dovetails per edge (0 = auto)'
    )
