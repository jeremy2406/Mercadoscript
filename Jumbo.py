import requests
import csv
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
from collections import defaultdict
import hashlib
import json

def obtener_pagina(url, timeout=30, reintentos=3):
    """Obtener contenido de una página web"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0'
    }
    
    for intento in range(reintentos):
        try:
            print(f"Obteniendo: {url[:80]}...")
            response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            print(f"✓ Página obtenida ({response.status_code}) - {len(response.text)} caracteres")
            return response.text
        except requests.exceptions.Timeout:
            print(f"⏱ Timeout en intento {intento + 1}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Error intento {intento + 1}: {e}")
        except Exception as e:
            print(f"❌ Error inesperado intento {intento + 1}: {e}")
        
        if intento < reintentos - 1:
            print(f"⏳ Esperando 5 segundos antes del siguiente intento...")
            time.sleep(5)
    
    print(f"❌ Error después de {reintentos} intentos para {url}")
    return None

def normalizar_texto(texto):
    """Normalizar texto para comparación (quitar espacios, acentos, mayúsculas)"""
    if not texto:
        return ""
    
    # Convertir a minúsculas y quitar espacios extra
    texto = re.sub(r'\s+', ' ', texto.lower().strip())
    
    # Quitar acentos básicos
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'ñ': 'n', 'ü': 'u', 'à': 'a', 'è': 'e', 'ì': 'i', 'ò': 'o', 'ù': 'u'
    }
    for old, new in replacements.items():
        texto = texto.replace(old, new)
    
    return texto

def normalizar_precio(precio):
    """Normalizar precio para comparación"""
    if not precio or precio == "Sin precio":
        return ""
    
    # Extraer solo números y puntos/comas
    precio_limpio = re.sub(r'[^\d.,]', '', precio)
    # Normalizar separadores decimales (usar punto como decimal)
    if ',' in precio_limpio and '.' in precio_limpio:
        # Si tiene ambos, asumir que coma es separador de miles
        precio_limpio = precio_limpio.replace(',', '')
    elif ',' in precio_limpio:
        # Si solo tiene coma, podría ser decimal
        partes = precio_limpio.split(',')
        if len(partes) == 2 and len(partes[1]) <= 2:
            precio_limpio = precio_limpio.replace(',', '.')
    
    return precio_limpio

def generar_hash_producto(nombre, precio):
    """Generar hash único basado en nombre y precio normalizados"""
    nombre_norm = normalizar_texto(nombre)
    precio_norm = normalizar_precio(precio)
    
    # Crear string único
    texto_unico = f"{nombre_norm}|{precio_norm}"
    
    # Generar hash
    return hashlib.md5(texto_unico.encode('utf-8')).hexdigest()

def productos_son_similares(prod1, prod2, umbral_similitud=0.85):
    """Verificar si dos productos son similares usando diferentes criterios"""
    
    # Criterio 1: Hash exacto
    hash1 = generar_hash_producto(prod1['nombre'], prod1['precio'])
    hash2 = generar_hash_producto(prod2['nombre'], prod2['precio'])
    
    if hash1 == hash2:
        return True
    
    # Criterio 2: Nombres muy similares
    nombre1_norm = normalizar_texto(prod1['nombre'])
    nombre2_norm = normalizar_texto(prod2['nombre'])
    
    # Verificar si un nombre está contenido en el otro
    if len(nombre1_norm) > 5 and len(nombre2_norm) > 5:
        if nombre1_norm in nombre2_norm or nombre2_norm in nombre1_norm:
            # Si los nombres son similares, verificar precios
            precio1_norm = normalizar_precio(prod1['precio'])
            precio2_norm = normalizar_precio(prod2['precio'])
            
            if precio1_norm == precio2_norm or (not precio1_norm and not precio2_norm):
                return True
    
    # Criterio 3: Similitud de Jaccard para nombres
    palabras1 = set(nombre1_norm.split())
    palabras2 = set(nombre2_norm.split())
    
    if palabras1 and palabras2:
        interseccion = len(palabras1.intersection(palabras2))
        union = len(palabras1.union(palabras2))
        similitud = interseccion / union if union > 0 else 0
        
        if similitud >= umbral_similitud:
            precio1_norm = normalizar_precio(prod1['precio'])
            precio2_norm = normalizar_precio(prod2['precio'])
            
            if precio1_norm == precio2_norm or (not precio1_norm and not precio2_norm):
                return True
    
    return False

def eliminar_duplicados_avanzado(productos):
    """Eliminar duplicados usando múltiples criterios"""
    print(f"\n🔍 ELIMINANDO DUPLICADOS...")
    print(f"Productos originales: {len(productos)}")
    
    productos_unicos = []
    productos_procesados = set()
    
    for i, producto_actual in enumerate(productos):
        if i % 100 == 0:
            print(f"   Procesando producto {i+1}/{len(productos)}")
        
        # Generar hash único
        hash_actual = generar_hash_producto(producto_actual['Nombre'], producto_actual['Precio'])
        
        # Si ya procesamos este hash exacto, saltar
        if hash_actual in productos_procesados:
            continue
        
        # Verificar similitud con productos ya agregados
        es_duplicado = False
        for producto_unico in productos_unicos:
            if productos_son_similares(
                {'nombre': producto_actual['Nombre'], 'precio': producto_actual['Precio']},
                {'nombre': producto_unico['Nombre'], 'precio': producto_unico['Precio']}
            ):
                es_duplicado = True
                # Combinar categorías si es duplicado
                if producto_actual['Categoria'] not in producto_unico['Categorias']:
                    producto_unico['Categorias'].append(producto_actual['Categoria'])
                break
        
        if not es_duplicado:
            # Crear nuevo producto único con lista de categorías
            producto_unico = producto_actual.copy()
            producto_unico['Categorias'] = [producto_actual['Categoria']]
            productos_unicos.append(producto_unico)
            productos_procesados.add(hash_actual)
    
    print(f"Productos únicos: {len(productos_unicos)}")
    print(f"Duplicados eliminados: {len(productos) - len(productos_unicos)}")
    
    return productos_unicos

def es_categoria_valida_jumbo(url, texto):
    """Determinar si es una categoría válida para Jumbo"""
    texto_lower = texto.lower().strip()
    url_lower = url.lower()
    
    # Excluir elementos de navegación y páginas no deseadas específicas de Jumbo
    excluir = [
        'ver todo', 'ver todos', 'mi cuenta', 'mi carrito', 'ayuda', 'ofertas',
        'cerrar sesión', 'iniciar sesión', 'crear cuenta', 'buscar',
        'nuestras tiendas', 'políticas', 'contacto', 'inicio', 'soporte',
        'casa cuesta', 'supermercados nacional', 'juguetón', 'bebemundo',
        'cuesta libros', 'bonos ccn', 'javascript:', '#', 'mailto:', 'tel:',
        'footer', 'header', 'social', 'facebook', 'instagram', 'twitter',
        'whatsapp', 'términos', 'condiciones', 'privacidad', 'cookies'
    ]
    
    # Verificar exclusiones
    for termino in excluir:
        if termino in texto_lower or termino in url_lower:
            return False
    
    # Debe tener texto válido
    if len(texto.strip()) < 2 or len(texto.strip()) > 60:
        return False
    
    # URLs que no deben procesarse
    urls_excluir = ['#', '/', 'javascript:', 'mailto:', 'tel:', '.pdf', '.jpg', '.png']
    for excluir_url in urls_excluir:
        if excluir_url in url_lower:
            return False
    
    # Categorías específicas de supermercado Jumbo
    categorias_validas = [
        'supermercado', 'belleza', 'salud', 'hogar', 'electrodomésticos', 
        'ferretería', 'deportes', 'bebés', 'escolares', 'oficina', 'juguetería',
        'carne', 'pollo', 'pescado', 'mariscos', 'embutidos', 'charcutería',
        'leche', 'queso', 'yogurt', 'lácteos', 'huevos', 'mantequilla',
        'fruta', 'vegetal', 'verdura', 'hortalizas', 'vegetales', 'frutas',
        'pan', 'panadería', 'cereales', 'arroz', 'pasta', 'granos', 'harinas',
        'bebida', 'agua', 'jugo', 'café', 'té', 'vino', 'cerveza', 'licores',
        'limpieza', 'detergente', 'jabón', 'desinfectante', 'papel higiénico',
        'shampoo', 'cuidado personal', 'higiene', 'pañal', 'cosmético',
        'condimento', 'especias', 'salsa', 'aceite', 'vinagre', 'sal', 'azúcar',
        'conserva', 'enlatado', 'mermelada', 'congelado', 'helado', 'frozen',
        'mascota', 'gato', 'perro', 'despensa', 'abarrotes', 'snacks', 'dulces',
        'galleta', 'chocolate', 'refresco', 'agua', 'medicina', 'vitamina'
    ]
    
    # Verificar si contiene términos de supermercado
    for termino in categorias_validas:
        if termino in texto_lower:
            return True
    
    # Si el texto parece ser una categoría de producto (no contiene espacios extra o caracteres raros)
    if re.match(r'^[a-záéíóúñü\s&-]+$', texto_lower) and len(texto.split()) <= 4:
        return True
    
    return False

def encontrar_categorias_jumbo(soup, base_url):
    """Encontrar categorías específicas de Jumbo"""
    categorias = set()
    
    print("🔍 Buscando categorías en la navegación principal...")
    
    # Selectores específicos para Jumbo (basado en la estructura típica de e-commerce)
    selectores = [
        # Navegación principal
        'nav a[href]', '.nav a[href]', '.navigation a[href]', '.menu a[href]',
        '.navbar a[href]', '.main-nav a[href]', '.primary-nav a[href]',
        # Headers y menús
        'header a[href]', '.header a[href]', '.top-menu a[href]',
        # Listas de categorías
        'ul.categories a[href]', '.category-list a[href]', '.cat-menu a[href]',
        # Enlaces generales que podrían ser categorías
        'a[href*="categoria"]', 'a[href*="category"]', 'a[href*="/c/"]',
        # Selectores más generales
        'li a[href]', 'div a[href]'
    ]
    
    enlaces_procesados = set()
    
    for selector in selectores:
        try:
            enlaces = soup.select(selector)
            print(f"   Selector '{selector}': {len(enlaces)} enlaces encontrados")
            
            for enlace in enlaces:
                href = enlace.get('href', '').strip()
                texto = enlace.get_text().strip()
                
                if not href or href in enlaces_procesados:
                    continue
                
                enlaces_procesados.add(href)
                
                # Construir URL completa
                if href.startswith('http'):
                    url_completa = href
                elif href.startswith('/'):
                    url_completa = base_url.rstrip('/') + href
                else:
                    url_completa = urljoin(base_url, href)
                
                # Verificar que sea del mismo dominio
                parsed_url = urlparse(url_completa)
                parsed_base = urlparse(base_url)
                
                if parsed_url.netloc != parsed_base.netloc:
                    continue
                
                if es_categoria_valida_jumbo(url_completa, texto):
                    categorias.add((url_completa, texto))
                    print(f"✓ Categoría encontrada: '{texto}' -> {url_completa}")
        
        except Exception as e:
            print(f"   ❌ Error con selector '{selector}': {e}")
            continue
    
    # También buscar en elementos con clases específicas de categorías
    print("🔍 Buscando en elementos específicos de categorías...")
    try:
        elementos_categoria = soup.find_all(['div', 'li', 'span'], class_=re.compile(r'categor|menu|nav', re.I))
        for elemento in elementos_categoria:
            enlaces = elemento.find_all('a', href=True)
            for enlace in enlaces:
                href = enlace['href'].strip()
                texto = enlace.get_text().strip()
                
                if href and href not in enlaces_procesados:
                    enlaces_procesados.add(href)
                    
                    url_completa = urljoin(base_url, href)
                    parsed_url = urlparse(url_completa)
                    parsed_base = urlparse(base_url)
                    
                    if parsed_url.netloc == parsed_base.netloc and es_categoria_valida_jumbo(url_completa, texto):
                        categorias.add((url_completa, texto))
                        print(f"✓ Categoría específica: '{texto}' -> {url_completa}")
    except Exception as e:
        print(f"   ❌ Error buscando elementos específicos: {e}")
    
    return list(categorias)

def extraer_productos_jumbo(soup, url_categoria):
    """Extraer productos específicos de páginas de Jumbo"""
    productos = []
    
    # Selectores específicos para productos en sitios de e-commerce como Jumbo
    selectores_productos = [
        # Selectores específicos de productos
        '.product-item', '.product', '.item-product', '.producto',
        '.product-card', '.card-product', '.item', '.card',
        # Selectores de grillas de productos
        '.grid-item', '.product-grid-item', '.catalog-item',
        # Selectores genéricos
        'div[class*="product"]', 'li[class*="product"]',
        'div[class*="item"]', 'article[class*="product"]',
        # Selectores por datos
        '[data-product]', '[data-item]',
        # Más específicos para e-commerce
        '.js-product-item', '.product-tile', '.product-list-item'
    ]
    
    items_encontrados = []
    selector_usado = None
    
    for selector in selectores_productos:
        try:
            items = soup.select(selector)
            if len(items) > len(items_encontrados):
                items_encontrados = items
                selector_usado = selector
        except Exception as e:
            continue
    
    print(f"   📦 Encontrados {len(items_encontrados)} elementos con selector '{selector_usado}'")
    
    if not items_encontrados:
        # Intentar con selectores más amplios si no encontramos nada
        print("   🔍 Intentando con selectores más amplios...")
        selectores_amplios = ['article', 'div[class]', 'li[class]']
        
        for selector in selectores_amplios:
            try:
                items = soup.select(selector)
                # Filtrar solo elementos que parezcan productos
                items_productos = []
                for item in items:
                    texto = item.get_text().lower()
                    if any(palabra in texto for palabra in ['precio', '$', 'añadir', 'comprar', 'producto']):
                        items_productos.append(item)
                
                if len(items_productos) > len(items_encontrados):
                    items_encontrados = items_productos
                    selector_usado = f"{selector} (filtrado)"
            except:
                continue
        
        print(f"   📦 Con selectores amplios: {len(items_encontrados)} elementos")
    
    for i, item in enumerate(items_encontrados):
        try:
            nombre = extraer_nombre_producto_jumbo(item)
            precio = extraer_precio_producto_jumbo(item)
            
            if nombre and len(nombre.strip()) > 2 and nombre.lower() not in ['sin nombre', 'producto', 'item']:
                productos.append({
                    'nombre': nombre,
                    'precio': precio if precio else "Sin precio"
                })
        except Exception as e:
            continue
    
    # Si no encontramos muchos productos, intentar buscar en JSON embebido
    if len(productos) < 5:
        print("   🔍 Buscando productos en scripts JSON...")
        productos_json = extraer_productos_json(soup)
        productos.extend(productos_json)
    
    return productos

def extraer_nombre_producto_jumbo(item):
    """Extraer nombre del producto específico para Jumbo"""
    selectores_nombre = [
        # Títulos de productos
        'h1', 'h2', 'h3', 'h4', 'h5',
        # Enlaces de productos
        'a.product-item-link', 'a.product-name', 'a.product-title',
        '.product-name', '.product-title', '.item-name', '.item-title',
        # Selectores por clases
        '.name', '.title', '.titulo', '.nombre',
        # Selectores por atributos
        'a[title]', '[data-name]', '[data-title]',
        # Selectores más específicos
        '.product-info h3', '.product-info h2', '.product-info .name',
        'span.name', 'div.name', 'p.name'
    ]
    
    for selector in selectores_nombre:
        try:
            elemento = item.select_one(selector)
            if elemento:
                # Intentar obtener texto
                texto = elemento.get_text().strip()
                if texto and len(texto) > 2 and len(texto) < 150:
                    # Limpiar el texto
                    texto = re.sub(r'\s+', ' ', texto)
                    texto = texto.replace('\n', ' ').replace('\t', ' ').strip()
                    if texto:
                        return texto
                
                # Intentar atributos si no hay texto
                for attr in ['title', 'alt', 'data-name', 'data-title']:
                    valor = elemento.get(attr, '').strip()
                    if valor and len(valor) > 2 and len(valor) < 150:
                        return valor
        except:
            continue
    
    # Si no encontramos nombre específico, buscar en todo el texto del item
    try:
        texto_completo = item.get_text().strip()
        if texto_completo:
            # Buscar la primera línea que parezca un nombre de producto
            lineas = [linea.strip() for linea in texto_completo.split('\n') if linea.strip()]
            for linea in lineas:
                if len(linea) > 5 and len(linea) < 100:
                    # Evitar líneas que son claramente precios o botones
                    if not re.search(r'^\$|precio|añadir|comprar|ver|más', linea.lower()):
                        return linea
    except:
        pass
    
    return "Sin nombre"

def extraer_precio_producto_jumbo(item):
    """Extraer precio del producto específico para Jumbo"""
    selectores_precio = [
        # Selectores específicos de precio
        '.price', '.precio', '.cost', '.amount', '.value',
        # Selectores por clases que contengan 'price'
        'span[class*="price"]', 'div[class*="price"]', 'p[class*="price"]',
        # Selectores específicos de moneda dominicana
        'span[class*="peso"]', 'div[class*="peso"]',
        # Selectores por datos
        '[data-price]', '[data-cost]',
        # Selectores más específicos
        '.product-price', '.item-price', '.current-price', '.sale-price',
        '.regular-price', '.final-price'
    ]
    
    for selector in selectores_precio:
        try:
            elemento = item.select_one(selector)
            if elemento:
                precio_texto = elemento.get_text().strip()
                if precio_texto and validar_precio(precio_texto):
                    return limpiar_precio(precio_texto)
                
                # Intentar atributos
                for attr in ['data-price', 'data-cost', 'title']:
                    valor = elemento.get(attr, '').strip()
                    if valor and validar_precio(valor):
                        return limpiar_precio(valor)
        except:
            continue
    
    # Buscar patrones de precio en todo el texto del item
    try:
        texto_completo = item.get_text()
        patrones_precio = [
            # Pesos dominicanos
            r'RD\$\s*[\d,]+\.?\d*', r'\$\s*[\d,]+\.?\d*',
            # Patrones numéricos que podrían ser precios
            r'[\d,]+\.\d{2}', r'[\d,]{3,}\.?\d*'
        ]
        
        for patron in patrones_precio:
            matches = re.findall(patron, texto_completo)
            for match in matches:
                if validar_precio(match):
                    return limpiar_precio(match)
    except:
        pass
    
    return "Sin precio"

def validar_precio(precio_texto):
    """Validar si un texto parece ser un precio"""
    if not precio_texto:
        return False
    
    # Debe contener números
    if not re.search(r'\d', precio_texto):
        return False
    
    # Patrones válidos de precio
    patrones_validos = [
        r'[\$]', r'RD\$', r'peso', r'DOP',  # Símbolos de moneda
        r'\d+[.,]\d{2}',  # Formato con decimales
        r'\d{3,}'  # Al menos 3 dígitos (precios realistas)
    ]
    
    for patron in patrones_validos:
        if re.search(patron, precio_texto, re.I):
            return True
    
    return False

def limpiar_precio(precio_texto):
    """Limpiar y formatear texto de precio"""
    if not precio_texto:
        return "Sin precio"
    
    # Quitar espacios extra y caracteres especiales innecesarios
    precio_limpio = re.sub(r'\s+', ' ', precio_texto.strip())
    
    return precio_limpio

def extraer_productos_json(soup):
    """Buscar productos en scripts JSON embebidos"""
    productos = []
    
    try:
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string)
                # Buscar productos en estructura JSON+LD
                if isinstance(data, dict) and 'Product' in str(data):
                    producto = extraer_producto_de_json(data)
                    if producto:
                        productos.append(producto)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and 'Product' in str(item):
                            producto = extraer_producto_de_json(item)
                            if producto:
                                productos.append(producto)
            except:
                continue
        
        # También buscar en otros scripts que puedan contener datos de productos
        scripts_js = soup.find_all('script', type='text/javascript')
        for script in scripts_js:
            if script.string:
                # Buscar patrones de productos en JavaScript
                matches = re.finditer(r'"name"\s*:\s*"([^"]+)".*?"price"\s*:\s*"?([^",}]+)"?', script.string)
                for match in matches:
                    nombre = match.group(1).strip()
                    precio = match.group(2).strip()
                    if len(nombre) > 2:
                        productos.append({
                            'nombre': nombre,
                            'precio': precio if validar_precio(precio) else "Sin precio"
                        })
    except:
        pass
    
    return productos[:20]  # Limitar a 20 productos de JSON para evitar spam

def extraer_producto_de_json(data):
    """Extraer producto de estructura JSON"""
    try:
        if isinstance(data, dict):
            nombre = data.get('name', '')
            precio = ''
            
            # Buscar precio en diferentes estructuras
            if 'offers' in data:
                offers = data['offers']
                if isinstance(offers, dict):
                    precio = offers.get('price', '')
                elif isinstance(offers, list) and offers:
                    precio = offers[0].get('price', '')
            elif 'price' in data:
                precio = data['price']
            
            if nombre and len(nombre) > 2:
                return {
                    'nombre': nombre,
                    'precio': str(precio) if precio else "Sin precio"
                }
    except:
        pass
    
    return None

def procesar_categoria_jumbo(url_categoria, nombre_categoria, max_paginas=3):
    """Procesar todos los productos de una categoría de Jumbo"""
    print(f"\n{'='*60}")
    print(f"PROCESANDO CATEGORÍA: {nombre_categoria}")
    print(f"URL: {url_categoria}")
    print(f"{'='*60}")
    
    productos_categoria = []
    
    # Procesar múltiples páginas si es posible
    for pagina in range(1, max_paginas + 1):
        print(f"\n📄 Procesando página {pagina}...")
        
        # Construir URL de página
        if pagina == 1:
            url_pagina = url_categoria
        else:
            # Intentar diferentes formatos de paginación
            separador = '&' if '?' in url_categoria else '?'
            url_pagina = f"{url_categoria}{separador}page={pagina}"
        
        # Obtener página
        html = obtener_pagina(url_pagina)
        if not html:
            print(f"❌ No se pudo obtener la página {pagina}")
            if pagina == 1:
                break  # Si no podemos obtener la primera página, salir
            continue
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extraer productos
        productos_pagina = extraer_productos_jumbo(soup, url_pagina)
        
        if not productos_pagina:
            print(f"   No se encontraron productos en página {pagina}")
            if pagina == 1:
                print("   🔍 Intentando analizar estructura de la página...")
                # Debug: mostrar algunas clases encontradas
                elementos_con_clase = soup.find_all(['div', 'li', 'article'], class_=True)[:10]
                for elem in elementos_con_clase:
                    clases = ' '.join(elem.get('class', []))
                    if clases:
                        print(f"      Clase encontrada: {clases}")
            break  # No hay más páginas
        
        # Agregar productos de esta página
        for producto in productos_pagina:
            productos_categoria.append({
                'Nombre': producto['nombre'],
                'Precio': producto['precio'],
                'Categoria': nombre_categoria,
                'URL_Categoria': url_categoria,
                'Pagina': pagina
            })
        
        print(f"   ✓ {len(productos_pagina)} productos extraídos de página {pagina}")
        
        # Pausa entre páginas
        time.sleep(2)
    
    print(f"✅ TOTAL EN '{nombre_categoria}': {len(productos_categoria)} productos")
    return productos_categoria

def main():
    base_url = 'https://jumbo.com.do/'
    todos_productos = []
    
    print("🚀 INICIANDO SCRAPING DE JUMBO REPÚBLICA DOMINICANA")
    print("=" * 70)
    
    # Obtener página principal
    print("📥 Obteniendo página principal...")
    html_principal = obtener_pagina(base_url)
    
    if not html_principal:
        print("❌ No se pudo obtener la página principal")
        print("   Verificar:")
        print("   - Conexión a internet")
        print("   - Disponibilidad del sitio web")
        print("   - Posibles restricciones de acceso")
        return
    
    soup_principal = BeautifulSoup(html_principal, 'html.parser')
    
    # Debug: mostrar información básica de la página
    title = soup_principal.find('title')
    print(f"   Título de página: {title.get_text() if title else 'No encontrado'}")
    
    # Encontrar categorías
    print("\n🔍 Buscando categorías de productos...")
    categorias = encontrar_categorias_jumbo(soup_principal, base_url)
    
    if not categorias:
        print("❌ No se encontraron categorías válidas")
        print("   Posibles causas:")
        print("   - Estructura del sitio diferente a la esperada")
        print("   - Contenido cargado dinámicamente con JavaScript")
        print("   - Cambios recientes en el diseño del sitio")
        
        # Intentar mostrar algunos enlaces encontrados para debug
        print("\n🔧 Enlaces encontrados (para debug):")
        todos_enlaces = soup_principal.find_all('a', href=True)[:20]
        for i, enlace in enumerate(todos_enlaces, 1):
            href = enlace['href']
            texto = enlace.get_text().strip()[:50]
            print(f"   {i:2d}. '{texto}' -> {href}")
        
        return
    
    print(f"\n✅ {len(categorias)} categorías encontradas:")
    for i, (url, nombre) in enumerate(categorias[:10], 1):  # Mostrar solo las primeras 10
        print(f"   {i:2d}. {nombre}")
    
    if len(categorias) > 10:
        print(f"   ... y {len(categorias) - 10} más")
    
    # Limitar número de categorías para evitar procesos muy largos
    max_categorias = min(len(categorias), 15)  # Procesar máximo 15 categorías
    categorias_seleccionadas = categorias[:max_categorias]
    
    if len(categorias) > max_categorias:
        print(f"\n⚠️  Se procesarán solo las primeras {max_categorias} categorías para optimizar el tiempo de ejecución")
    
    print(f"\n🚀 COMENZANDO EXTRACCIÓN DE PRODUCTOS...")
    print(f"   Categorías a procesar: {len(categorias_seleccionadas)}")
    
    # Procesar cada categoría
    categorias_exitosas = 0
    productos_totales = 0
    
    for i, (url_categoria, nombre_categoria) in enumerate(categorias_seleccionadas, 1):
        try:
            print(f"\n[{i}/{len(categorias_seleccionadas)}] 📂 Procesando: {nombre_categoria}")
            
            productos_categoria = procesar_categoria_jumbo(url_categoria, nombre_categoria)
            
            if productos_categoria:
                todos_productos.extend(productos_categoria)
                productos_totales += len(productos_categoria)
                categorias_exitosas += 1
                print(f"   ✅ {len(productos_categoria)} productos agregados")
            else:
                print(f"   ⚠️  No se encontraron productos en esta categoría")
            
            # Pausa entre categorías para no sobrecargar el servidor
            if i < len(categorias_seleccionadas):
                print("   ⏳ Pausa de 3 segundos...")
                time.sleep(3)
            
        except KeyboardInterrupt:
            print(f"\n⏹️  Proceso interrumpido por el usuario en categoría {i}")
            break
        except Exception as e:
            print(f"   ❌ Error procesando '{nombre_categoria}': {e}")
            continue
    
    # Resumen del proceso
    print(f"\n{'='*60}")
    print(f"📊 RESUMEN DEL SCRAPING:")
    print(f"   Categorías procesadas exitosamente: {categorias_exitosas}/{len(categorias_seleccionadas)}")
    print(f"   Total de productos extraídos: {productos_totales}")
    print(f"{'='*60}")
    
    # PROCESAR Y GUARDAR RESULTADOS
    if todos_productos:
        print(f"\n🔄 PROCESANDO RESULTADOS...")
        
        # Eliminar duplicados
        productos_unicos = eliminar_duplicados_avanzado(todos_productos)
        
        # Preparar datos finales
        productos_finales = []
        for producto in productos_unicos:
            productos_finales.append({
                'Nombre': producto['Nombre'],
                'Precio': producto['Precio'],
                'Categorias': '; '.join(producto['Categorias']),
                'URL_Categoria': producto.get('URL_Categoria', ''),
                'Tienda': 'Jumbo República Dominicana'
            })
        
        # Guardar resultados
        timestamp = int(time.time())
        archivo_final = f'inventario_jumbo_do_{timestamp}.csv'
        
        try:
            with open(archivo_final, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['Nombre', 'Precio', 'Categorias', 'URL_Categoria', 'Tienda']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(productos_finales)
            
            print(f'\n🎉 ¡SCRAPING COMPLETADO EXITOSAMENTE!')
            print(f'✅ {len(productos_finales)} productos únicos guardados en: {archivo_final}')
            
            # Estadísticas detalladas
            print(f"\n📈 ESTADÍSTICAS DETALLADAS:")
            print(f"   • Productos originales extraídos: {len(todos_productos)}")
            print(f"   • Productos únicos después de eliminar duplicados: {len(productos_finales)}")
            print(f"   • Duplicados eliminados: {len(todos_productos) - len(productos_finales)}")
            print(f"   • Categorías con productos: {categorias_exitosas}")
            
            # Resumen por categoría
            resumen_categorias = defaultdict(int)
            for producto in productos_unicos:
                for categoria in producto['Categorias']:
                    resumen_categorias[categoria] += 1
            
            print(f"\n📋 PRODUCTOS POR CATEGORÍA:")
            categorias_ordenadas = sorted(resumen_categorias.items(), key=lambda x: x[1], reverse=True)
            for categoria, cantidad in categorias_ordenadas[:10]:  # Top 10
                print(f"   • {categoria}: {cantidad} productos")
            
            if len(categorias_ordenadas) > 10:
                otros_total = sum(cantidad for _, cantidad in categorias_ordenadas[10:])
                print(f"   • Otras categorías: {otros_total} productos")
            
            # Análisis de precios
            productos_con_precio = [p for p in productos_finales if p['Precio'] != 'Sin precio']
            print(f"\n💰 ANÁLISIS DE PRECIOS:")
            print(f"   • Productos con precio: {len(productos_con_precio)}")
            print(f"   • Productos sin precio: {len(productos_finales) - len(productos_con_precio)}")
            
        except Exception as e:
            print(f"❌ Error guardando archivo: {e}")
            
    else:
        print('\n❌ No se extrajo ningún producto')
        print("   Posibles causas:")
        print("   - Todas las categorías están vacías")
        print("   - Estructura del sitio no compatible con los selectores")
        print("   - Problemas de conectividad")
        print("   - Restricciones del sitio web")

def mostrar_ayuda():
    """Mostrar información de ayuda del script"""
    print("🛒 JUMBO REPÚBLICA DOMINICANA SCRAPER")
    print("=" * 50)
    print("Este script extrae el inventario de productos de jumbo.com.do")
    print()
    print("Características:")
    print("• Extrae productos de múltiples categorías")
    print("• Elimina productos duplicados automáticamente")
    print("• Maneja múltiples páginas por categoría")
    print("• Guarda resultados en formato CSV")
    print("• Incluye manejo de errores robusto")
    print()
    print("Uso:")
    print("python jumbo_scraper.py")
    print()
    print("El archivo de salida se guardará como:")
    print("inventario_jumbo_do_[timestamp].csv")

if __name__ == "__main__":
    try:
        import sys
        if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h', 'help']:
            mostrar_ayuda()
        else:
            main()
    except KeyboardInterrupt:
        print("\n⏹️  Proceso interrumpido por el usuario")
        print("   Los datos parciales no se guardarán automáticamente.")
    except Exception as e:
        print(f"\n❌ Error crítico del programa: {e}")
        import traceback
        print("\n🔧 Información técnica del error:")
        traceback.print_exc()
        print("\nSi el problema persiste, verifique:")
        print("• Conexión a internet")
        print("• Disponibilidad del sitio web jumbo.com.do")
        print("• Permisos de escritura en el directorio actual")