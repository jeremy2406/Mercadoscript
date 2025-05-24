import time
import csv
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

def configurar_driver():
    """Configurar el driver de Chrome con opciones optimizadas"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-logging')
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-backgrounding-occluded-windows')
    options.add_argument('--disable-renderer-backgrounding')
    options.add_argument('--disable-features=TranslateUI')
    options.add_argument('--disable-ipc-flooding-protection')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Configuraciones adicionales para estabilidad
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_experimental_option('prefs', {
        'profile.default_content_setting_values.notifications': 2,
        'profile.default_content_settings.popups': 0,
        'profile.managed_default_content_settings.images': 2
    })
    
    try:
        return webdriver.Chrome(options=options)
    except Exception as e:
        print(f"⚠ Error creando driver con servicio personalizado: {e}")
        print("🔄 Intentando con configuración básica...")
        return webdriver.Chrome(options=options)

def buscar_categorias(driver):
    """Buscar categorías usando múltiples selectores"""
    selectores_categorias = [
        'ul.menu-categorias li a',
        '.menu-categorias a',
        'nav ul li a',
        '.category-menu a',
        '.main-menu a',
        'ul li a[href*="category"]',
        'a[href*="categoria"]',
        '.navbar a',
        '.navigation a'
    ]
    
    enlaces_categorias = []
    
    for selector in selectores_categorias:
        try:
            elementos = driver.find_elements(By.CSS_SELECTOR, selector)
            enlaces = [elem.get_attribute('href') for elem in elementos 
                      if elem.get_attribute('href') and 
                      ('categoria' in elem.get_attribute('href').lower() or 
                       'category' in elem.get_attribute('href').lower())]
            
            if enlaces:
                enlaces_categorias.extend(enlaces)
                print(f'✔ Encontradas {len(enlaces)} categorías con selector: {selector}')
                break
        except Exception as e:
            continue
    
    # Eliminar duplicados manteniendo el orden
    enlaces_unicos = list(dict.fromkeys(enlaces_categorias))
    return enlaces_unicos

def buscar_productos(driver):
    """Buscar productos usando múltiples selectores"""
    selectores_productos = [
        'li.product-item',
        '.product-item',
        '.product',
        '.item-product',
        'div[class*="product"]',
        '.grid-item',
        '.product-card',
        '[data-product-id]'
    ]
    
    productos_encontrados = []
    
    for selector in selectores_productos:
        try:
            items = driver.find_elements(By.CSS_SELECTOR, selector)
            if items:
                productos_encontrados = items
                print(f'✔ Encontrados {len(items)} productos con selector: {selector}')
                break
        except Exception:
            continue
    
    return productos_encontrados

def extraer_info_producto(item):
    """Extraer información del producto usando múltiples selectores"""
    # Selectores para nombres
    selectores_nombre = [
        'a.product-item-link',
        '.product-name a',
        '.product-title',
        'h2 a',
        'h3 a',
        '.name a',
        'a[title]'
    ]
    
    # Selectores para precios
    selectores_precio = [
        'span.price',
        '.price',
        '.precio',
        '[class*="price"]',
        '.cost',
        '.amount'
    ]
    
    nombre = 'Nombre no disponible'
    precio = 'Precio no disponible'
    
    # Buscar nombre
    for selector in selectores_nombre:
        try:
            elemento = item.find_element(By.CSS_SELECTOR, selector)
            nombre = elemento.text.strip() or elemento.get_attribute('title') or elemento.get_attribute('alt')
            if nombre and nombre != '':
                break
        except:
            continue
    
    # Buscar precio
    for selector in selectores_precio:
        try:
            elemento = item.find_element(By.CSS_SELECTOR, selector)
            precio_texto = elemento.text.strip()
            if precio_texto and precio_texto != '':
                precio = precio_texto
                break
        except:
            continue
    
    return nombre, precio

def main():
    driver = None
    productos = []
    
    try:
        print("🔧 Configurando WebDriver...")
        driver = configurar_driver()
        
        # Configurar timeouts más largos
        driver.set_page_load_timeout(60)
        driver.implicitly_wait(10)
        
        print("🌐 Accediendo al sitio web...")
        try:
            driver.get('https://supermercadosnacional.com/')
        except Exception as e:
            print(f"❌ Error accediendo al sitio: {e}")
            print("🔄 Intentando con timeout extendido...")
            driver.set_page_load_timeout(120)
            driver.get('https://supermercadosnacional.com/')
        
        # Esperar a que la página cargue completamente
        wait = WebDriverWait(driver, 30)
        try:
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            print("✔ Página cargada correctamente")
        except TimeoutException:
            print("⚠ Timeout esperando la página, continuando...")
        
        time.sleep(3)
        
        print("🔍 Buscando categorías...")
        enlaces_categorias = buscar_categorias(driver)
        
        if not enlaces_categorias:
            print("⚠ No se encontraron categorías específicas. Buscando productos en la página principal...")
            enlaces_categorias = [driver.current_url]
        else:
            print(f'✔ Se encontraron {len(enlaces_categorias)} categorías.')
        
        # Limitar a las primeras 10 categorías para evitar timeout
        enlaces_categorias = enlaces_categorias[:10]
        
        for i, enlace in enumerate(enlaces_categorias, 1):
            print(f"\n📂 Procesando categoría {i}/{len(enlaces_categorias)}: {enlace}")
            
            try:
                driver.get(enlace)
                time.sleep(3)
                
                # Intentar obtener el nombre de la categoría
                selectores_titulo = ['h1.page-title', 'h1', '.page-title', '.category-title', 'title']
                categoria_nombre = f'Categoría_{i}'
                
                for selector in selectores_titulo:
                    try:
                        elemento = driver.find_element(By.CSS_SELECTOR, selector)
                        categoria_nombre = elemento.text.strip()
                        if categoria_nombre:
                            break
                    except:
                        continue
                
                print(f"📁 Categoría: {categoria_nombre}")
                
                # Buscar productos
                items = buscar_productos(driver)
                
                if not items:
                    print(f"⚠ No se encontraron productos en {categoria_nombre}")
                    continue
                
                print(f'🔍 {len(items)} productos encontrados en: {categoria_nombre}')
                
                # Extraer información de cada producto
                for j, item in enumerate(items[:50]):  # Limitar a 50 productos por categoría
                    try:
                        nombre, precio = extraer_info_producto(item)
                        
                        if nombre != 'Nombre no disponible':
                            productos.append({
                                'Nombre': nombre,
                                'Precio': precio,
                                'Categoría': categoria_nombre
                            })
                        
                        if (j + 1) % 10 == 0:
                            print(f"   ✔ Procesados {j + 1}/{len(items[:50])} productos...")
                            
                    except Exception as e:
                        print(f"   ⚠ Error procesando producto {j + 1}: {e}")
                        continue
                
            except Exception as e:
                print(f"❌ Error procesando categoría {enlace}: {e}")
                continue
        
        # Guardar resultados
        if productos:
            # Crear nombre de archivo con timestamp
            timestamp = int(time.time())
            nombre_archivo = f'inventario_supermercado_{timestamp}.csv'
            
            with open(nombre_archivo, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['Nombre', 'Precio', 'Categoría'])
                writer.writeheader()
                for producto in productos:
                    writer.writerow(producto)
            
            print(f'\n✅ {len(productos)} productos guardados en {nombre_archivo}')
            
            # Mostrar resumen por categoría
            categorias_resumen = {}
            for producto in productos:
                cat = producto['Categoría']
                categorias_resumen[cat] = categorias_resumen.get(cat, 0) + 1
            
            print("\n📊 Resumen por categoría:")
            for categoria, cantidad in categorias_resumen.items():
                print(f"   • {categoria}: {cantidad} productos")
                
        else:
            print('❗ No se extrajo ningún producto.')
            
            # Diagnóstico adicional
            print("\n🔧 Diagnóstico:")
            print("   • Verificando estructura de la página...")
            
            # Mostrar algunos elementos disponibles para debug
            try:
                all_links = driver.find_elements(By.TAG_NAME, "a")[:10]
                print(f"   • Se encontraron {len(all_links)} enlaces en total")
                
                for link in all_links:
                    href = link.get_attribute('href')
                    text = link.text.strip()[:50]
                    if href and text:
                        print(f"     - {text}: {href}")
                        
            except Exception as e:
                print(f"   • Error en diagnóstico: {e}")
    
    except Exception as e:
        print(f"❌ Error general: {e}")
        import traceback
        print("🔍 Detalles del error:")
        print(traceback.format_exc())
    
    finally:
        if driver:
            try:
                driver.quit()
                print("🔧 WebDriver cerrado correctamente")
            except Exception as e:
                print(f"⚠ Error cerrando WebDriver: {e}")
        print("\n🏁 Script completado.")

if __name__ == "__main__":
    main()