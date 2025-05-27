import requests
import csv
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
from collections import defaultdict
import hashlib
import urllib3
from urllib3.exceptions import InsecureRequestWarning

# Deshabilitar warnings de SSL
urllib3.disable_warnings(InsecureRequestWarning)

def obtener_pagina(url, timeout=30, reintentos=3):
    """Obtener contenido de una página web"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
        'Accept-Encoding': 'gzip, deflate, br'
    }
    
    for intento in range(reintentos):
        try:
            print(f"Obteniendo: {url[:80]}...")
            response = requests.get(url, headers=headers, timeout=timeout, verify=False)
            response.raise_for_status()
            print(f"✓ Página obtenida ({response.status_code}) - {len(response.text)} caracteres")
            return response.text
        except Exception as e:
            print(f"Error intento {intento + 1}: {e}")
            if intento < reintentos - 1:
                time.sleep(5)
    
    print(f"❌ Error después de {reintentos} intentos")
    return None

def debug_estructura_pagina(soup, url):
    """Analizar la estructura de la página para entender mejor el HTML"""
    print(f"\n🔍 ANALIZANDO ESTRUCTURA DE: {url[:60]}...")
    
    # Buscar elementos comunes de productos
    elementos_sospechosos = []
    
    # Buscar por clases que contengan 'product'
    for elem in soup.find_all(class_=re.compile(r'product', re.I)):
        clase = elem.get('class', [])
        tag = elem.name
        texto = elem.get_text().strip()[:50]
        elementos_sospechosos.append((tag, clase, len(texto), texto))
    
    if elementos_sospechosos:
        print(f"📦 Elementos con 'product' en clase ({len(elementos_sospechosos)}):")
        for tag, clase, longitud, texto in elementos_sospechosos[:5]:
            print(f"  {tag}.{' '.join(clase)}: {longitud} chars - '{texto}'")
    
    # Buscar por IDs que contengan 'product'
    elementos_id = soup.find_all(id=re.compile(r'product', re.I))
    if elementos_id:
        print(f"🆔 Elementos con 'product' en ID ({len(elementos_id)}):")
        for elem in elementos_id[:3]:
            print(f"  {elem.name}#{elem.get('id')}")
    
    # Buscar divs con muchos elementos hijos (posibles grids de productos)
    divs_grandes = []
    for div in soup.find_all('div'):
        hijos = div.find_all(recursive=False)
        if len(hijos) > 5:  # Divs con más de 5 hijos directos
            clase = div.get('class', [])
            divs_grandes.append((div, len(hijos), clase))
    
    if divs_grandes:
        divs_grandes.sort(key=lambda x: x[1], reverse=True)
        print(f"📋 Divs con muchos hijos (posibles grids):")
        for div, num_hijos, clase in divs_grandes[:3]:
            print(f"  div.{' '.join(clase) if clase else 'sin-clase'}: {num_hijos} hijos")
    
    # Buscar enlaces con precios (RD$ o $)
    enlaces_precio = []
    for enlace in soup.find_all('a'):
        texto = enlace.get_text()
        if re.search(r'(RD\$|\$)\s*\d+', texto):
            href = enlace.get('href', '')
            enlaces_precio.append((texto.strip()[:40], href[:40]))
    
    if enlaces_precio:
        print(f"💰 Enlaces con precios ({len(enlaces_precio)}):")
        for texto, href in enlaces_precio[:3]:
            print(f"  '{texto}' -> {href}")
    
    # Buscar spans o elementos con precios
    elementos_precio = []
    for elem in soup.find_all(['span', 'div', 'p']):
        texto = elem.get_text().strip()
        if re.search(r'(RD\$|\$)\s*\d+', texto) and len(texto) < 50:
            clase = elem.get('class', [])
            elementos_precio.append((elem.name, clase, texto))
    
    if elementos_precio:
        print(f"💲 Elementos con precios ({len(elementos_precio)}):")
        for tag, clase, texto in elementos_precio[:5]:
            print(f"  {tag}.{' '.join(clase)}: '{texto}'")

def extraer_productos_pagina_debug(soup, url_categoria):
    """Extraer productos con debugging detallado"""
    print(f"\n🔍 EXTRAYENDO PRODUCTOS DE: {url_categoria[:60]}...")
    
    # Primero hacer debug de la estructura
    debug_estructura_pagina(soup, url_categoria)
    
    productos = []
    
    # Selectores más amplios y específicos para Super Bravo
    selectores_productos = [
        # Selectores específicos de productos
        'div[class*="product"]', 'li[class*="product"]', 'article[class*="product"]',
        'div[class*="item"]', 'li[class*="item"]', 'div[class*="card"]',
        
        # Selectores de grids comunes
        '.grid-item', '.list-item', '.catalog-item', '.shop-item',
        '.product-item', '.product-card', '.product-box', '.item-box',
        
        # Selectores genéricos
        '.item', '.card', '.box', 'article', '.entry',
        
        # Selectores por estructura
        'div[data-product]', 'div[data-item]', 'li[data-product]',
        
        # Enlaces de productos
        'a[href*="product"]', 'a[href*="item"]', 'a[href*="articulo"]'
    ]
    
    mejor_selector = None
    max_items = 0
    items_por_selector = {}
    
    print(f"\n🧪 PROBANDO SELECTORES...")
    
    for selector in selectores_productos:
        try:
            items = soup.select(selector)
            items_por_selector[selector] = len(items)
            
            if len(items) > max_items:
                max_items = len(items)
                mejor_selector = selector
                
            print(f"  {selector}: {len(items)} elementos")
            
        except Exception as e:
            print(f"  {selector}: ERROR - {e}")
    
    if not mejor_selector:
        print("❌ No se encontró ningún selector válido")
        return []
    
    print(f"\n✓ MEJOR SELECTOR: {mejor_selector} ({max_items} elementos)")
    
    # Usar el mejor selector
    items_productos = soup.select(mejor_selector)
    
    print(f"\n📦 PROCESANDO {len(items_productos)} ELEMENTOS...")
    
    for i, item in enumerate(items_productos[:20]):  # Limitar a 20 para debug
        try:
            print(f"\n--- ELEMENTO {i+1} ---")
            
            # Debug del elemento actual
            print(f"Tag: {item.name}")
            print(f"Clases: {item.get('class', [])}")
            print(f"ID: {item.get('id', 'sin-id')}")
            
            # Extraer nombre
            nombre = extraer_nombre_producto_debug(item, i+1)
            
            # Extraer precio
            precio = extraer_precio_producto_debug(item, i+1)
            
            print(f"RESULTADO -> Nombre: '{nombre}' | Precio: '{precio}'")
            
            if nombre and len(nombre.strip()) > 2 and nombre != "Sin nombre":
                producto = {
                    'nombre': nombre,
                    'precio': precio if precio != "Sin precio" else "No disponible"
                }
                productos.append(producto)
                print(f"✓ PRODUCTO AGREGADO")
            else:
                print(f"❌ PRODUCTO DESCARTADO (nombre inválido)")
                
        except Exception as e:
            print(f"❌ Error procesando elemento {i+1}: {e}")
            continue
    
    print(f"\n✅ TOTAL PRODUCTOS EXTRAÍDOS: {len(productos)}")
    return productos

def extraer_nombre_producto_debug(item, numero):
    """Extraer nombre del producto con debugging"""
    print(f"  🏷️  Buscando NOMBRE en elemento {numero}...")
    
    selectores_nombre = [
        # Títulos y encabezados
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        
        # Enlaces específicos
        'a[title]', 'a.product-link', 'a.item-link', 'a[href*="product"]',
        
        # Clases específicas de nombres
        '.product-name', '.item-name', '.product-title', '.item-title',
        '.name', '.title', '.product-info', '.item-info',
        
        # Elementos con texto largo (posibles nombres)
        'span', 'div', 'p', 'a'
    ]
    
    for selector in selectores_nombre:
        try:
            elementos = item.select(selector)
            for elemento in elementos:
                # Obtener texto
                texto = elemento.get_text().strip()
                
                if texto and 5 <= len(texto) <= 200:  # Longitud razonable para nombre
                    print(f"    {selector}: '{texto[:40]}...'")
                    return texto
                
                # Intentar atributos
                for attr in ['title', 'alt', 'data-name', 'data-title']:
                    valor = elemento.get(attr, '').strip()
                    if valor and 5 <= len(valor) <= 200:
                        print(f"    {selector}[{attr}]: '{valor[:40]}...'")
                        return valor
                        
        except:
            continue
    
    # Si no encuentra nada específico, usar todo el texto del elemento
    texto_completo = item.get_text().strip()
    if texto_completo:
        # Tomar la primera línea o las primeras palabras
        primera_linea = texto_completo.split('\n')[0].strip()
        if 5 <= len(primera_linea) <= 200:
            print(f"    texto-completo: '{primera_linea[:40]}...'")
            return primera_linea
    
    print(f"    ❌ No se encontró nombre válido")
    return "Sin nombre"

def extraer_precio_producto_debug(item, numero):
    """Extraer precio del producto con debugging"""
    print(f"  💰 Buscando PRECIO en elemento {numero}...")
    
    # Buscar elementos con clases de precio
    selectores_precio = [
        '.price', '.precio', '.cost', '.amount', '.money',
        'span[class*="price"]', 'div[class*="price"]', 'p[class*="price"]',
        '.product-price', '.item-price', '.price-current', '.price-now',
        '.sale-price', '.regular-price', '.precio-actual',
        'span[class*="pesos"]', 'span[class*="rd"]', '.currency'
    ]
    
    for selector in selectores_precio:
        try:
            elementos = item.select(selector)
            for elemento in elementos:
                precio_texto = elemento.get_text().strip()
                if precio_texto and re.search(r'(RD\$|\$|₱)\s*\d+', precio_texto):
                    print(f"    {selector}: '{precio_texto}'")
                    return precio_texto
        except:
            continue
    
    # Buscar patrones de precio en todo el texto del elemento
    texto_completo = item.get_text()
    
    patrones_precio = [
        r'RD\$\s*[\d,]+\.?\d*',  # RD$ 1,500.00
        r'\$\s*[\d,]+\.?\d*',    # $ 1,500.00
        r'₱\s*[\d,]+\.?\d*',     # ₱ 1,500.00
        r'[\d,]+\.?\d*\s*(RD\$|\$|₱)',  # 1,500.00 RD$
        r'\b\d{1,6}[.,]\d{2}\b', # 1500.00 o 1500,00
        r'\b\d{2,6}\b(?=\s|$)'   # Números de 2-6 dígitos al final
    ]
    
    for patron in patrones_precio:
        matches = re.findall(patron, texto_completo)
        if matches:
            precio = matches[0] if isinstance(matches[0], str) else matches[0]
            print(f"    patrón '{patron}': '{precio}'")
            return precio
    
    print(f"    ❌ No se encontró precio válido")
    return "Sin precio"

def procesar_categoria_debug(url_categoria, nombre_categoria):
    """Procesar categoría con debugging detallado"""
    print(f"\n{'='*60}")
    print(f"PROCESANDO CATEGORÍA: {nombre_categoria}")
    print(f"URL: {url_categoria}")
    print(f"{'='*60}")
    
    productos_categoria = []
    
    # Obtener página de la categoría
    html = obtener_pagina(url_categoria)
    if not html:
        print("❌ No se pudo obtener la página")
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Extraer productos con debugging
    productos = extraer_productos_pagina_debug(soup, url_categoria)
    
    for producto in productos:
        productos_categoria.append({
            'Nombre': producto['nombre'],
            'Precio': producto['precio'],
            'Categoria': nombre_categoria,
            'URL_Categoria': url_categoria
        })
    
    print(f"\n✅ RESUMEN CATEGORÍA '{nombre_categoria}':")
    print(f"   - {len(productos_categoria)} productos extraídos")
    
    # Mostrar algunos ejemplos
    if productos_categoria:
        print(f"   - Ejemplos:")
        for i, prod in enumerate(productos_categoria[:3], 1):
            print(f"     {i}. {prod['Nombre'][:50]}... | {prod['Precio']}")
    
    return productos_categoria

# Resto de funciones (mantener las originales)
def normalizar_texto(texto):
    """Normalizar texto para comparación"""
    if not texto:
        return ""
    
    texto = re.sub(r'\s+', ' ', texto.lower().strip())
    
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'ñ': 'n', 'ü': 'u'
    }
    for old, new in replacements.items():
        texto = texto.replace(old, new)
    
    return texto

def es_categoria_valida(url, texto):
    """Determinar si es una categoría válida de supermercado"""
    texto_lower = texto.lower().strip()
    url_lower = url.lower()
    
    excluir = [
        'ver todo', 'ver mas', 'mi cuenta', 'mi carrito', 'mis listas', 
        'mis ordenes', 'cerrar sesión', 'iniciar sesión', 'crear cuenta', 
        'nuestras tiendas', 'políticas', 'retiro en tienda', 'ayuda', 'contacto',
        'inicio', 'soporte', 'trabaja con nosotros', 'sucursales', 'home',
        'javascript:', '#', 'mailto:', 'tel:', 'login', 'register', 'cart', 
        'checkout', 'search', 'buscar', 'facebook', 'instagram', 'twitter'
    ]
    
    for termino in excluir:
        if termino in texto_lower or termino in url_lower:
            return False
    
    if len(texto.strip()) < 2 or len(texto.strip()) > 80:
        return False
    
    categorias_validas = [
        'carne', 'res', 'pollo', 'cerdo', 'pescado', 'mariscos', 'embutidos',
        'leche', 'queso', 'yogurt', 'lácteos', 'huevos', 'mantequilla',
        'fruta', 'vegetal', 'verdura', 'hortalizas', 'vegetales', 'frutas',
        'pan', 'panadería', 'cereales', 'arroz', 'pasta', 'granos',
        'bebida', 'agua', 'jugo', 'café', 'té', 'vino', 'cerveza', 'licores',
        'limpieza', 'detergente', 'jabón', 'hogar', 'aseo', 'lavandería',
        'shampoo', 'cuidado personal', 'higiene', 'pañal', 'farmacia',
        'sal', 'azúcar', 'aceite', 'condimento', 'especias', 'salsa',
        'conserva', 'enlatado', 'mermelada', 'congelado', 'helado',
        'mascota', 'gato', 'perro', 'alimento', 'comida para mascota',
        'despensa', 'abarrotes', 'snacks', 'dulces', 'chocolate',
        'categoria', 'category', 'departamento', 'seccion', 'productos'
    ]
    
    for termino in categorias_validas:
        if termino in texto_lower:
            return True
    
    return False

def encontrar_categorias(soup, base_url):
    """Encontrar categorías de productos válidas"""
    categorias = set()
    
    selectores = [
        '.main-menu a[href]', '.navbar a[href]', '.nav-menu a[href]',
        '.category-menu a[href]', '.categories a[href]', 'nav a[href]',
        'header a[href]', '.navigation a[href]', '.menu a[href]',
        'ul li a[href]', '.dropdown-menu a[href]', '.submenu a[href]',
        'a[href*="categoria"]', 'a[href*="category"]', 'a[href*="productos"]',
        'a[href]'
    ]
    
    for selector in selectores:
        try:
            enlaces = soup.select(selector)
            for enlace in enlaces:
                href = enlace.get('href', '').strip()
                texto = enlace.get_text().strip()
                
                if href and href not in ['#', '/', 'javascript:void(0)', '']:
                    if href.startswith('http'):
                        url_completa = href
                    else:
                        url_completa = urljoin(base_url, href)
                    
                    if 'superbravo.com.do' in url_completa and es_categoria_valida(url_completa, texto):
                        categorias.add((url_completa, texto))
        except:
            continue
    
    return list(categorias)

def main():
    base_url = 'https://www.superbravo.com.do/'
    todos_productos = []
    
    print("🚀 INICIANDO SCRAPING DE SUPER BRAVO (VERSIÓN DEBUG)")
    print("=" * 70)
    
    # Obtener página principal
    html_principal = obtener_pagina(base_url)
    if not html_principal:
        print("❌ No se pudo obtener la página principal")
        return
    
    soup_principal = BeautifulSoup(html_principal, 'html.parser')
    
    # Encontrar categorías
    categorias = encontrar_categorias(soup_principal, base_url)
    
    if not categorias:
        print("❌ No se encontraron categorías válidas")
        return
    
    categorias_unicas = list(set(categorias))
    print(f"\n✓ {len(categorias_unicas)} categorías encontradas")
    
    # Para debugging, procesar solo las primeras 3 categorías
    categorias_debug = categorias_unicas[:3]
    
    for i, (url_categoria, nombre_categoria) in enumerate(categorias_debug, 1):
        try:
            print(f"\n[{i}/{len(categorias_debug)}] Procesando: {nombre_categoria}")
            
            productos_categoria = procesar_categoria_debug(url_categoria, nombre_categoria)
            
            if productos_categoria:
                todos_productos.extend(productos_categoria)
            
            time.sleep(3)  # Pausa más larga para debugging
            
        except Exception as e:
            print(f"❌ Error procesando {nombre_categoria}: {e}")
            continue
    
    # Guardar resultados
    if todos_productos:
        timestamp = int(time.time())
        archivo = f'debug_superbravo_{timestamp}.csv'
        
        with open(archivo, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['Nombre', 'Precio', 'Categoria', 'URL_Categoria'])
            writer.writeheader()
            writer.writerows(todos_productos)
        
        print(f'\n🎉 DEBUG COMPLETADO')
        print(f'✓ {len(todos_productos)} productos guardados en {archivo}')
        
    else:
        print('\n❌ No se extrajo ningún producto')

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹ Proceso interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()