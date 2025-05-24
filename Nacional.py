import time
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# Configurar navegador (sin interfaz)
options = Options()
options.add_argument('--headless')
options.add_argument('--disable-gpu')
driver = webdriver.Chrome(options=options)

# Ir al sitio web
driver.get('https://supermercadosnacional.com/')
time.sleep(5)  # Esperar carga inicial

# Intentar extraer las categorías
try:
    categorias = driver.find_elements(By.CSS_SELECTOR, 'ul.menu-categorias li a')
    enlaces_categorias = [a.get_attribute('href') for a in categorias if a.get_attribute('href')]
    print(f'✔ Se encontraron {len(enlaces_categorias)} categorías.')
except Exception as e:
    print(f'❌ Error extrayendo categorías: {e}')
    enlaces_categorias = []

productos = []

for enlace in enlaces_categorias:
    driver.get(enlace)
    time.sleep(5)

    try:
        categoria_nombre = driver.find_element(By.CSS_SELECTOR, 'h1.page-title').text.strip()
    except:
        categoria_nombre = 'Categoría Desconocida'

    # Intentar encontrar productos
    try:
        items = driver.find_elements(By.CSS_SELECTOR, 'li.product-item')
        print(f'🔍 {len(items)} productos encontrados en: {categoria_nombre}')
    except Exception as e:
        print(f'⚠ No se pudieron obtener productos de {categoria_nombre}: {e}')
        items = []

    for item in items:
        try:
            nombre = item.find_element(By.CSS_SELECTOR, 'a.product-item-link').text.strip()
        except:
            nombre = 'Nombre no disponible'
        try:
            precio = item.find_element(By.CSS_SELECTOR, 'span.price').text.strip()
        except:
            precio = 'Precio no disponible'

        productos.append({
            'Nombre': nombre,
            'Precio': precio,
            'Categoría': categoria_nombre
        })

driver.quit()

# Guardar en CSV
if productos:
    with open('inventario_supermercado.csv', mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Nombre', 'Precio', 'Categoría'])
        writer.writeheader()
        for p in productos:
            writer.writerow(p)
    print(f'✅ {len(productos)} productos guardados en inventario_supermercado.csv')
else:
    print('❗ No se extrajo ningún producto.')

