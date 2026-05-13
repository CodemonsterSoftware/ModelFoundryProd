import math

def hex_to_rgb(hex_code):
    hex_code = hex_code.lstrip('#')
    if len(hex_code) != 6:
        return (0, 0, 0)
    return tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))

def get_closest_color_name(hex_code):
    if not hex_code or not hex_code.startswith('#'):
        return hex_code
        
    try:
        rgb = hex_to_rgb(hex_code)
    except ValueError:
        return hex_code
    
    # Basic dictionary of common 3D printing filament colors
    colors = {
        "Black": (0, 0, 0),
        "White": (255, 255, 255),
        "Red": (255, 0, 0),
        "Green": (0, 128, 0),
        "Blue": (0, 0, 255),
        "Yellow": (255, 255, 0),
        "Cyan": (0, 255, 255),
        "Magenta": (255, 0, 255),
        "Silver": (192, 192, 192),
        "Gray": (128, 128, 128),
        "Maroon": (128, 0, 0),
        "Olive Green": (128, 128, 0),
        "Dark Green": (0, 100, 0),
        "Purple": (128, 0, 128),
        "Teal": (0, 128, 128),
        "Navy": (0, 0, 128),
        "Orange": (255, 165, 0),
        "Pink": (255, 192, 203),
        "Brown": (165, 42, 42),
        "Gold": (255, 215, 0),
        "Beige": (245, 245, 220),
        "Natural": (255, 250, 240)
    }
    
    min_dist = float('inf')
    closest_name = hex_code
    
    for name, c_rgb in colors.items():
        # Euclidean distance
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(rgb, c_rgb)))
        if dist < min_dist:
            min_dist = dist
            closest_name = name
            
    return closest_name
