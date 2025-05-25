import requests
import csv
import time
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
import re
from collections import defaultdict
import hashlib

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
        'Sec-Fetch-Site': 'none'
    }
    
    for intento in range(reintentos):
        try:
            print(f"Obteniendo: {url[:60]}...")
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            print(f"✓ Página obtenida ({response.status_code})")
            return response.text
        except Exception as e:
            print(f"Error intento {intento + 1}: {e}")
            if intento < reintentos - 1:
                time.sleep(5)
    
    print(f"❌ Error después de {reintentos} intentos")
    return None

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

def normalizar_precio(precio):
    """Normalizar precio para comparación"""
    if not precio or precio == "Sin precio":
        return ""
    
    precio_limpio = re.sub(r'[^\d.,]', '', precio)
    precio_limpio = precio_limpio.replace(',', '.')
    
    return precio_limpio

def generar_hash_producto(nombre, precio):
    """Generar hash único basado en nombre y precio normalizados"""
    nombre_norm = normalizar_texto(nombre)
    precio_norm = normalizar_precio(precio)
    
    texto_unico = f"{nombre_norm}|{precio_norm}"
    
    return hashlib.md5(texto_unico.encode('utf-8')).hexdigest()

def productos_son_similares(prod1, prod2, umbral_similitud=0.85):
    """Verificar si dos productos son similares"""
    
    hash1 = generar_hash_producto(prod1['nombre'], prod1['precio'])
    hash2 = generar_hash_producto(prod2['nombre'], prod2['precio'])
    
    if hash1 == hash2:
        return True
    
    nombre1_norm = normalizar_texto(prod1['nombre'])
    nombre2_norm = normalizar_texto(prod2['nombre'])
    
    if nombre1_norm in nombre2_norm or nombre2_norm in nombre1_norm:
        precio1_norm = normalizar_precio(prod1['precio'])
        precio2_norm = normalizar_precio(prod2['precio'])
        
        if precio1_norm == precio2_norm:
            return True
    
    palabras1 = set(nombre1_norm.split())
    palabras2 = set(nombre2_norm.split())
    
    if palabras1 and palabras2:
        interseccion = len(palabras1.intersection(palabras2))
        union = len(palabras1.union(palabras2))
        similitud = interseccion / union if union > 0 else 0
        
        if similitud >= umbral_similitud:
            precio1_norm = normalizar_precio(prod1['precio'])
            precio2_norm = normalizar_precio(prod2['precio'])
            
            if precio1_norm == precio2_norm:
                return True
    
    return False

def eliminar_duplicados_avanzado(productos):
    """Eliminar duplicados usando múltiples criterios"""
    print(f"\n🔍 ELIMINANDO DUPLICADOS...")
    print(f"Productos originales: {len(productos)}")
    
    productos_unicos = []
    productos_procesados = set()
    
    for i, producto_actual in enumerate(productos):
        
        hash_actual = generar_hash_producto(producto_actual['Nombre'], producto_actual['Precio'])
        
        if hash_actual in productos_procesados:
            continue
        
        es_duplicado = False
        for producto_unico in productos_unicos:
            if productos_son_similares(
                {'nombre': producto_actual['Nombre'], 'precio': producto_actual['Precio']},
                {'nombre': producto_unico['Nombre'], 'precio': producto_unico['Precio']}
            ):
                es_duplicado = True
                if producto_actual['Categoria'] not in producto_unico['Categorias']:
                    producto_unico['Categorias'].append(producto_actual['Categoria'])
                break
        
        if not es_duplicado:
            producto_unico = producto_actual.copy()
            producto_unico['Categorias'] = [producto_actual['Categoria']]
            productos_unicos.append(producto_unico)
            productos_procesados.add(hash_actual)
    
    print(f"Productos únicos: {len(productos_unicos)}")
    print(f"Duplicados eliminados: {len(productos) - len(productos_unicos)}")
    
    return productos_unicos

def es_categoria_valida(url, texto):
    """Determinar si es una categoría válida de supermercado para Sirena"""
    texto_lower = texto.lower().strip()
    url_lower = url.lower()
    
    # Excluir elementos de navegación y páginas no deseadas específicos de Sirena
    excluir = [
        'mi cuenta', 'mi carrito', 'mi lista', 'mis ordenes', 'cerrar sesión', 
        'iniciar sesión', 'registrarse', 'crear cuenta', 'tiendas', 'sucursales',
        'políticas', 'términos', 'ayuda', 'contacto', 'inicio', 'home', 'soporte',
        'nosotros', 'nuestra historia', 'trabaja con nosotros', 'ofertas especiales',
        'javascript:', '#', 'mailto:', 'tel:', 'whatsapp', 'facebook', 'instagram',
        'twitter', 'newsletter', 'suscribirse', 'promociones', 'cupones',
        'farmacia', 'servicio al cliente', 'devoluciones', 'garantías'
    ]
    
    for termino in excluir:
        if termino in texto_lower or termino in url_lower:
            return False
    
    if len(texto.strip()) < 3 or len(texto.strip()) > 60:
        return False
    
    # Categorías válidas específicas de supermercados dominicanos
    categorias_validas = [
        'carnes', 'pollo', 'res', 'cerdo', 'pescado', 'mariscos', 'embutidos',
        'lácteos', 'leche', 'queso', 'yogurt', 'huevos', 'mantequilla',
        'frutas', 'vegetales', 'verduras', 'hortalizas', 'productos frescos',
        'panadería', 'pan', 'cereales', 'arroz', 'pasta', 'granos', 'harinas',
        'bebidas', 'agua', 'jugos', 'refrescos', 'sodas', 'café', 'té',
        'cerveza', 'vinos', 'licores', 'bebidas alcohólicas',
        'limpieza', 'detergentes', 'jabones', 'desinfectantes', 'hogar',
        'cuidado personal', 'shampoo', 'higiene', 'cosméticos', 'perfumes',
        'pañales', 'bebés', 'infantil', 'medicamentos', 'vitaminas',
        'condimentos', 'especias', 'salsas', 'aceites', 'vinagres',
        'conservas', 'enlatados', 'mermeladas', 'dulces', 'galletas',
        'congelados', 'helados', 'comida congelada',
        'mascotas', 'perros', 'gatos', 'alimento para mascotas',
        'despensa', 'abarrotes', 'snacks', 'botanas', 'dulcería'
    ]
    
    for termino in categorias_validas:
        if termino in texto_lower:
            return True
    
    return False

def encontrar_categorias_sirena(soup, base_url):
    """Encontrar categorías específicas de Sirena"""
    categorias = set()
    
    # Selectores específicos para la estructura de Sirena
    selectores = [
        # Menú principal de navegación
        '.main-navigation a[href]',
        '.navigation-menu a[href]',
        '.category-menu a[href]',
        '.menu-categories a[href]',
        # Enlaces de categorías en el menú
        'nav ul li a[href]',
        '.nav-item a[href]',
        '.category-item a[href]',
        # Enlaces en sidebar o footer de categorías
        '.sidebar-categories a[href]',
        '.footer-categories a[href]',
        # Cualquier enlace que contenga 'category' o 'categoria'
        'a[href*="category"]',
        'a[href*="categoria"]',
        'a[href*="departamento"]',
        'a[href*="seccion"]',
        # Enlaces generales que podrían ser categorías
        'a[href]'
    ]
    
    print("Buscando categorías en diferentes secciones...")
    
    for selector in selectores:
        try:
            enlaces = soup.select(selector)
            print(f"Encontrados {len(enlaces)} enlaces con selector: {selector}")
            
            for enlace in enlaces:
                href = enlace.get('href', '').strip()
                texto = enlace.get_text().strip()
                
                if href and href not in ['#', '/', 'javascript:void(0)', '']:
                    url_completa = urljoin(base_url, href)
                    
                    # Filtrar URLs que claramente son de categorías de productos
                    if any(keyword in href.lower() for keyword in ['category', 'categoria', 'departamento', 'seccion', 'products']):
                        if es_categoria_valida(url_completa, texto):
                            categorias.add((url_completa, texto))
                            print(f"✓ Categoría encontrada: {texto} -> {href}")
                    elif es_categoria_valida(url_completa, texto):
                        categorias.add((url_completa, texto))
                        print(f"✓ Categoría encontrada: {texto} -> {href}")
        except Exception as e:
            print(f"Error con selector {selector}: {e}")
            continue
    
    return list(categorias)

def extraer_productos_sirena(soup, url_pagina):
    """Extraer productos específicamente de la estructura de Sirena"""
    productos = []
    
    # Selectores específicos para productos en Sirena
    selectores_productos = [
        # Selectores comunes para productos
        '.product-item',
        '.product-card',
        '.product',
        '.item-product',
        'div[class*="product"]',
        'article[class*="product"]',
        '.grid-item',
        '.catalog-item',
        '.product-tile',
        # Selectores específicos que podrían usar en Sirena
        '.product-wrapper',
        '.product-container',
        '.item-wrapper',
        '.product-box',
        # Selectores más generales
        '.item',
        '.card',
        'article',
        'li[class*="item"]'
    ]
    
    items_encontrados = []
    mejor_selector = ""
    
    for selector in selectores_productos:
        try:
            items = soup.select(selector)
            if len(items) > len(items_encontrados):
                items_encontrados = items
                mejor_selector = selector
        except:
            continue
    
    print(f"Mejor selector encontrado: {mejor_selector} con {len(items_encontrados)} elementos")
    
    # Si no encontramos productos con selectores específicos, buscar por patrones de texto
    if len(items_encontrados) < 5:
        print("Pocos productos encontrados, buscando por patrones alternativos...")
        # Buscar divs que contengan precios
        items_con_precio = soup.find_all('div', string=re.compile(r'\$|RD\$|\d+\.\d+'))
        items_encontrados.extend(items_con_precio)
    
    print(f"Procesando {len(items_encontrados)} elementos de productos...")
    
    for i, item in enumerate(items_encontrados):
        try:
            nombre = extraer_nombre_producto_sirena(item)
            precio = extraer_precio_producto_sirena(item)
            
            if nombre and len(nombre.strip()) > 2:
                productos.append({
                    'nombre': nombre,
                    'precio': precio,
                    'elemento_html': str(item)[:200] + "..." if len(str(item)) > 200 else str(item)
                })
                
                if i < 5:  # Mostrar los primeros 5 para debug
                    print(f"  Producto {i+1}: {nombre} - {precio}")
        except Exception as e:
            print(f"Error procesando elemento {i}: {e}")
            continue
    
    return productos

def extraer_nombre_producto_sirena(item):
    """Extraer nombre del producto específicamente para Sirena"""
    selectores_nombre = [
        # Selectores específicos para nombres de productos
        '.product-name',
        '.product-title',
        '.item-name',
        '.item-title',
        '.name',
        '.title',
        # Enlaces de producto
        'a.product-link',
        'a[title]',
        '.product-item-link',
        # Encabezados
        'h1', 'h2', 'h3', 'h4', 'h5',
        # Spans con nombres
        'span.name',
        'span.title',
        # Selectores por atributos
        '[data-name]',
        '[data-title]'
    ]
    
    for selector in selectores_nombre:
        try:
            elemento = item.select_one(selector)
            if elemento:
                texto = elemento.get_text().strip()
                if texto and len(texto) > 2 and len(texto) < 150:
                    # Limpiar texto común de nombres de productos
                    texto = re.sub(r'\s+', ' ', texto)
                    return texto
                
                # Intentar atributos
                for attr in ['title', 'alt', 'data-name', 'data-title']:
                    valor = elemento.get(attr, '').strip()
                    if valor and len(valor) > 2 and len(valor) < 150:
                        return valor
        except:
            continue
    
    # Si no encontramos nombre específico, buscar el texto más largo que no sea precio
    texto_completo = item.get_text().strip()
    lineas = [linea.strip() for linea in texto_completo.split('\n') if linea.strip()]
    
    for linea in lineas:
        # Evitar líneas que claramente son precios
        if not re.search(r'[\$₡]|\d+[.,]\d+', linea) and len(linea) > 5 and len(linea) < 150:
            return linea
    
    return "Sin nombre"

def extraer_precio_producto_sirena(item):
    """Extraer precio del producto específicamente para Sirena"""
    selectores_precio = [
        # Selectores específicos para precios
        '.price',
        '.precio',
        '.cost',
        '.amount',
        '.product-price',
        '.item-price',
        'span[class*="price"]',
        'div[class*="price"]',
        '.money',
        '.currency',
        # Selectores por atributos
        '[data-price]',
        '[data-cost]'
    ]
    
    for selector in selectores_precio:
        try:
            elemento = item.select_one(selector)
            if elemento:
                precio_texto = elemento.get_text().strip()
                if precio_texto and es_precio_valido(precio_texto):
                    return limpiar_precio(precio_texto)
        except:
            continue
    
    # Buscar patrones de precio en todo el texto del item
    texto_completo = item.get_text()
    patrones_precio = [
        r'RD\$\s*[\d,]+\.?\d*',  # Pesos dominicanos
        r'\$\s*[\d,]+\.?\d*',    # Dólares
        r'[\d,]+\.?\d*\s*RD\$',  # Pesos al final
        r'[\d,]+\.\d{2}',        # Formato decimal
        r'[\d,]{1,6}\.\d{2}'     # Formato con comas
    ]
    
    for patron in patrones_precio:
        match = re.search(patron, texto_completo)
        if match:
            precio_encontrado = match.group().strip()
            if es_precio_valido(precio_encontrado):
                return limpiar_precio(precio_encontrado)
    
    return "Sin precio"

def es_precio_valido(precio_texto):
    """Verificar si un texto representa un precio válido"""
    if not precio_texto:
        return False
    
    # Debe contener números
    if not re.search(r'\d', precio_texto):
        return False
    
    # No debe ser solo números (podría ser código de producto)
    if precio_texto.isdigit() and len(precio_texto) > 6:
        return False
    
    # Debe tener formato de precio común
    patrones_validos = [
        r'[\$₡]', r'RD\$', r'\d+[.,]\d+', r'precio', r'cost'
    ]
    
    return any(re.search(patron, precio_texto, re.IGNORECASE) for patron in patrones_validos)

def limpiar_precio(precio_texto):
    """Limpiar y normalizar texto de precio"""
    # Conservar formato original pero limpio
    precio_limpio = re.sub(r'\s+', ' ', precio_texto.strip())
    return precio_limpio

def procesar_categoria_sirena(url_categoria, nombre_categoria, max_paginas=3):
    """Procesar todos los productos de una categoría de Sirena"""
    print(f"\n{'='*50}")
    print(f"PROCESANDO CATEGORÍA: {nombre_categoria}")
    print(f"URL: {url_categoria}")
    print(f"{'='*50}")
    
    productos_categoria = []
    
    for pagina in range(1, max_paginas + 1):
        print(f"\n--- Página {pagina} ---")
        
        # Construir URL de página (diferentes formatos posibles)
        url_pagina = url_categoria
        if pagina > 1:
            if '?' in url_categoria:
                url_pagina = f"{url_categoria}&page={pagina}"
            else:
                url_pagina = f"{url_categoria}?page={pagina}"
        
        html = obtener_pagina(url_pagina)
        if not html:
            print(f"❌ No se pudo obtener la página {pagina}")
            break
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extraer productos de esta página
        productos = extraer_productos_sirena(soup, url_pagina)
        
        if not productos:
            print(f"No se encontraron productos en la página {pagina}")
            if pagina == 1:
                print("Guardando HTML de muestra para análisis...")
                with open(f'debug_sirena_{nombre_categoria.replace(" ", "_")}.html', 'w', encoding='utf-8') as f:
                    f.write(html)
            break
        
        productos_pagina = 0
        for producto in productos:
            productos_categoria.append({
                'Nombre': producto['nombre'],
                'Precio': producto['precio'],
                'Categoria': nombre_categoria,
                'URL_Categoria': url_categoria,
                'Pagina': pagina
            })
            productos_pagina += 1
        
        print(f"✓ {productos_pagina} productos extraídos de la página {pagina}")
        
        # Si encontramos pocos productos, probablemente no hay más páginas
        if len(productos) < 10:
            print("Pocos productos encontrados, asumiendo última página")
            break
        
        time.sleep(2)  # Pausa entre páginas
    
    print(f"✓ TOTAL EN '{nombre_categoria}': {len(productos_categoria)} productos")
    return productos_categoria

def main():
    base_url = 'https://www.sirena.do/'
    todos_productos = []
    
    print("🚀 INICIANDO SCRAPING DE SIRENA SUPERMERCADOS")
    print("=" * 60)
    
    # Obtener página principal
    print("Obteniendo página principal...")
    html_principal = obtener_pagina(base_url)
    
    if not html_principal:
        print("❌ No se pudo obtener la página principal")
        return
    
    # Guardar HTML principal para análisis
    with open('debug_sirena_principal.html', 'w', encoding='utf-8') as f:
        f.write(html_principal)
    print("✓ HTML principal guardado como debug_sirena_principal.html")
    
    soup_principal = BeautifulSoup(html_principal, 'html.parser')
    
    # Encontrar categorías
    print("\nBuscando categorías de productos...")
    categorias = encontrar_categorias_sirena(soup_principal, base_url)
    
    if not categorias:
        print("❌ No se encontraron categorías válidas")
        print("Analizando estructura de la página...")
        
        # Mostrar algunos enlaces encontrados para debug
        todos_enlaces = soup_principal.find_all('a', href=True)
        print(f"\nTotal de enlaces encontrados: {len(todos_enlaces)}")
        print("\nPrimeros 10 enlaces:")
        for i, enlace in enumerate(todos_enlaces[:10]):
            href = enlace.get('href', '')
            texto = enlace.get_text().strip()
            print(f"  {i+1}. {texto[:30]} -> {href[:50]}")
        
        return
    
    print(f"\n✓ {len(categorias)} categorías encontradas:")
    for i, (url, nombre) in enumerate(categorias, 1):
        print(f"  {i:2d}. {nombre}")
    
    # Limitar a las primeras categorías para prueba
    categorias_a_procesar = categorias[:5]  # Solo primeras 5 categorías
    print(f"\nProcesando solo las primeras {len(categorias_a_procesar)} categorías para prueba...")
    
    # Procesar cada categoría
    for i, (url_categoria, nombre_categoria) in enumerate(categorias_a_procesar, 1):
        try:
            print(f"\n[{i}/{len(categorias_a_procesar)}] Procesando: {nombre_categoria}")
            
            productos_categoria = procesar_categoria_sirena(url_categoria, nombre_categoria)
            
            if productos_categoria:
                todos_productos.extend(productos_categoria)
                print(f"✓ {len(productos_categoria)} productos agregados")
            
            time.sleep(3)  # Pausa más larga entre categorías
            
        except Exception as e:
            print(f"❌ Error procesando {nombre_categoria}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # ELIMINAR DUPLICADOS Y GUARDAR
    if todos_productos:
        productos_unicos = eliminar_duplicados_avanzado(todos_productos)
        
        # Preparar datos finales
        productos_finales = []
        for producto in productos_unicos:
            productos_finales.append({
                'Nombre': producto['Nombre'],
                'Precio': producto['Precio'],
                'Categorias': '; '.join(producto['Categorias']),
                'URL_Categoria': producto['URL_Categoria']
            })
        
        # Guardar resultados
        timestamp = int(time.time())
        archivo_final = f'inventario_sirena_{timestamp}.csv'
        
        with open(archivo_final, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['Nombre', 'Precio', 'Categorias', 'URL_Categoria'])
            writer.writeheader()
            writer.writerows(productos_finales)
        
        print(f'\n🎉 SCRAPING COMPLETADO')
        print(f'✓ {len(productos_finales)} productos únicos guardados en {archivo_final}')
        
        # Resumen por categoría
        resumen = defaultdict(int)
        for producto in productos_unicos:
            for categoria in producto['Categorias']:
                resumen[categoria] += 1
        
        print(f"\n📊 RESUMEN POR CATEGORÍA:")
        for categoria, cantidad in sorted(resumen.items(), key=lambda x: x[1], reverse=True):
            print(f"   {categoria}: {cantidad} productos")
            
    else:
        print('\n❌ No se extrajo ningún producto')
        print('Revisa los archivos debug_sirena_*.html para analizar la estructura de la página')

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹ Proceso interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error general: {e}")
        import traceback
        traceback.print_exc()