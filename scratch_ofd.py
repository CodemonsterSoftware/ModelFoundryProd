import urllib.request
import json

req = urllib.request.Request('https://raw.githubusercontent.com/OpenFilamentCollective/open-filament-database/main/data/3dxtech/ABS/3dxmax/filament.json', headers={'User-Agent': 'Mozilla/5.0'})
print(urllib.request.urlopen(req).read().decode('utf-8'))
