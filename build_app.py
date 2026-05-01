"""
build_app.py
Lee data.json y lo inyecta en index.html (template).
Ejecutado por GitHub Actions después de generate_data.py
"""
import json, re, sys, os

import os; TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'template.html')
OUTPUT   = 'index.html'
DATA_FILE= 'data.json'

if not os.path.exists(TEMPLATE):
    print(f"Error: {TEMPLATE} no encontrado")
    sys.exit(1)

if not os.path.exists(DATA_FILE):
    print(f"Error: {DATA_FILE} no encontrado")
    sys.exit(1)

with open(TEMPLATE, 'r', encoding='utf-8') as f:
    html = f.read()

with open(DATA_FILE, 'r', encoding='utf-8') as f:
    data_str = f.read()

# Replace DATA placeholder
html = re.sub(r'const DATA = \{.*?\};',
              f'const DATA = {data_str};',
              html, count=1, flags=re.DOTALL)

with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write(html)

data = json.loads(data_str)
print(f"✅ {OUTPUT} generado")
print(f"   Equipos: {data.get('n_equipos','?')}")
print(f"   Partidos: {data.get('n_partidos','?')}")
print(f"   Actualizado: {data.get('updated','?')}")
print(f"   Tamaño HTML: {len(html)//1024} KB")
