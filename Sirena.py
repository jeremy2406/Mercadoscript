import requests
import csv
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
from collections import defaultdict
import hashlib

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
            response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
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
    """Normalizar texto para comparación (quitar espacios, acentos, mayúsculas)"""
    if not texto:
        return ""
    
    # Convertir a minúsculas y quitar espacios extra
    texto = re.sub(r'\s+', ' ', texto.lower().strip())
    
    # Quitar acentos básicos
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
    
    # Extraer solo números y puntos/comas
    precio_limpio = re.sub(r'[^\d.,]', '', precio)
    # Normalizar separadores decimales
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
    if len(nombre1_norm) > 10 and len(nombre2_norm) > 10:
        if nombre1_norm in nombre2_norm or nombre2_norm in nombre1_norm:
            precio1_norm = normalizar_precio(prod1['precio'])
            precio2_norm = normalizar_precio(prod2['precio'])
            
            if precio1_norm == precio2_norm:
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
            
            if precio1_norm == precio2_norm:
                return True
    
    return False

def eliminar_duplicados_avanzado(productos):
    """Eliminar duplicados usando múltiples criterios"""
    print(f"\n🔍 ELIMINANDO DUPLICADOS...")
    print(f"Productos originales: {len(productos)}")
    
    productos_unicos = []
    productos_procesados = set()  # Para tracking de hashes únicos
    
    for i, producto_actual in enumerate(productos):
        
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

def es_categoria_valida_sirena(url, texto):
    """Determinar si es una categoría válida para Sirena"""
    texto_lower = texto.lower().strip()
    url_lower = url.lower()
    
    # Excluir elementos de navegación y páginas no deseadas
    excluir = [
        'ver todo', 'ver todos', 'mi cuenta', 'mi carrito', 'mi perfil', 'wishlist',
        'cerrar sesión', 'iniciar sesión', 'login', 'register', 'registrarse',
        'contacto', 'about us', 'nosotros', 'términos', 'políticas', 'ayuda',
        'inicio', 'home', 'soporte', 'support', 'javascript:', '#', 'mailto:', 'tel:',
        'facebook', 'instagram', 'twitter', 'youtube', 'redes sociales',
        'blog', 'noticias', 'ofertas especiales', 'promociones', 'cupones'
    ]
    
    # Verificar exclusiones
    for termino in excluir:
        if termino in texto_lower or termino in url_lower:
            return False
    
    # Debe tener texto válido
    if len(texto.strip()) < 3 or len(texto.strip()) > 60:
        return False
    
    # Categorías válidas de supermercado (adaptadas para República Dominicana)
    categorias_validas = [
        'carne', 'res', 'pollo', 'cerdo', 'pescado', 'mariscos', 'embutidos', 'charcutería',
        'leche', 'queso', 'yogurt', 'lácteos', 'huevos', 'mantequilla',
        'fruta', 'vegetal', 'verdura', 'hortalizas', 'vegetales', 'frutas', 'produce',
        'pan', 'panadería', 'cereales', 'arroz', 'pasta', 'granos', 'harinas',
        'bebida', 'agua', 'jugo', 'café', 'té', 'refrescos', 'sodas', 'bebidas',
        'vino', 'cerveza', 'licores', 'alcohol', 'ron',
        'limpieza', 'detergente', 'jabón', 'hogar', 'aseo', 'cleaning',
        'shampoo', 'cuidado personal', 'higiene', 'pañal', 'personal care',
        'sal', 'azúcar', 'aceite', 'condimento', 'especias', 'salsa', 'sazonadores',
        'conserva', 'enlatado', 'mermelada', 'congelado', 'helado', 'frozen',
        'mascota', 'gato', 'perro', 'pet', 'despensa', 'abarrotes', 'snacks', 'dulces',
        'desayuno', 'breakfast', 'galletas', 'cookies', 'chocolate',
        'deli', 'delicatessen', 'gourmet', 'orgánico', 'organic',
        'farmacia', 'medicina', 'vitaminas', 'suplementos', 'health'
    ]
    
    # Verificar si contiene términos de supermercado
    for termino in categorias_validas:
        if termino in texto_lower:
            return True
    
    # También verificar en la URL
    for termino in categorias_validas:
        if termino in url_lower:
            return True
    
    return False

def encontrar_categorias_sirena(soup, base_url):
    """Encontrar categorías de productos específicas para Sirena"""
    categorias = set()
    
    # Selectores específicos para Sirena
    selectores = [
        # Menú principal de navegación
        '.main-navigation a[href]',
        '.navbar a[href]',
        '.menu a[href]',
        'nav a[href]',
        # Categorías en el header
        'header a[href]',
        '.header a[href]',
        # Links de categorías
        '.category-link',
        '.cat-link',
        # Menús desplegables
        '.dropdown-menu a[href]',
        '.mega-menu a[href]',
        # Sidebar de categorías
        '.sidebar a[href]',
        '.category-sidebar a[href]',
        # Lista de categorías
        'ul.categories a[href]',
        '.category-list a[href]',
        # Enlaces generales que podrían ser categorías
        'a[href*="categoria"]',
        'a[href*="category"]',
        'a[href*="departamento"]',
        'a[href*="department"]',
        # Cualquier enlace
        'a[href]'
    ]
    
    for selector in selectores:
        try:
            enlaces = soup.select(selector)
            for enlace in enlaces:
                href = enlace.get('href', '').strip()
                texto = enlace.get_text().strip()
                
                if href and href not in ['#', '/', 'javascript:void(0)', '']:
                    # Construir URL completa
                    if href.startswith('http'):
                        url_completa = href
                    else:
                        url_completa = urljoin(base_url, href)
                    
                    # Verificar que sea del mismo dominio
                    parsed_base = urlparse(base_url)
                    parsed_url = urlparse(url_completa)
                    
                    if parsed_url.netloc == parsed_base.netloc or not parsed_url.netloc:
                        if es_categoria_valida_sirena(url_completa, texto):
                            categorias.add((url_completa, texto))
                            print(f"✓ Categoría encontrada: {texto}")
        except Exception as e:
            continue
    
    # Si no encontramos muchas categorías, intentar con selectores más generales
    if len(categorias) < 5:
        print("Buscando categorías con selectores alternativos...")
        try:
            # Buscar todos los enlaces y filtrar manualmente
            todos_enlaces = soup.find_all('a', href=True)
            for enlace in todos_enlaces:
                href = enlace.get('href', '').strip()
                texto = enlace.get_text().strip()
                
                if href and len(texto) > 0:
                    url_completa = urljoin(base_url, href)
                    if es_categoria_valida_sirena(url_completa, texto):
                        categorias.add((url_completa, texto))
        except:
            pass
    
    return list(categorias)

def extraer_productos_sirena(soup):
    """Extraer productos específicamente de páginas de Sirena"""
    productos = []
    
    # Selectores específicos para productos en Sirena
    selectores_productos = [
        # Selectores comunes de e-commerce
        '.product-item',
        '.product',
        '.item-product',
        '.producto',
        '.product-card',
        '.product-container',
        '.item',
        '.card',
        # Selectores de grids
        '.grid-item',
        '.col-product',
        'div[class*="product"]',
        'li[class*="product"]',
        'div[class*="item"]',
        # Selectores específicos posibles de Sirena
        '.sirena-product',
        '.product-tile',
        '.catalog-item',
        'article',
        # Selectores más generales
        'div[data-product]',
        '[data-product-id]'
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
    
    print(f"Mejor selector encontrado: '{mejor_selector}' con {len(items_encontrados)} elementos")
    
    for item in items_encontrados:
        try:
            nombre = extraer_nombre_producto_sirena(item)
            precio = extraer_precio_producto_sirena(item)
            
            if nombre and len(nombre.strip()) > 2 and nombre != "Sin nombre":
                productos.append({
                    'nombre': nombre,
                    'precio': precio
                })
        except Exception as e:
            continue
    
    return productos

def extraer_nombre_producto_sirena(item):
    """Extraer nombre del producto específicamente para Sirena"""
    selectores_nombre = [
        # Títulos y nombres de productos
        'h1', 'h2', 'h3', 'h4', 'h5',
        '.product-name',
        '.product-title',
        '.item-name',
        '.name',
        '.title',
        # Enlaces con títulos
        'a.product-item-link',
        'a[title]',
        'a',
        # Específicos de Sirena
        '.sirena-product-name',
        '.product-info h3',
        '.product-info h2',
        # Más generales
        '[data-product-name]',
        '.description',
        'span.name'
    ]
    
    for selector in selectores_nombre:
        try:
            elemento = item.select_one(selector)
            if elemento:
                # Intentar texto del elemento
                texto = elemento.get_text().strip()
                if texto and len(texto) > 2 and len(texto) < 150:
                    # Limpiar texto innecesario
                    texto = re.sub(r'^\d+\.\s*', '', texto)  # Quitar numeración
                    texto = re.sub(r'\s+', ' ', texto)  # Normalizar espacios
                    if len(texto) > 2:
                        return texto
                
                # Intentar atributos
                for attr in ['title', 'alt', 'data-name', 'data-product-name']:
                    valor = elemento.get(attr, '').strip()
                    if valor and len(valor) > 2 and len(valor) < 150:
                        return valor
        except:
            continue
    
    return "Sin nombre"

def extraer_precio_producto_sirena(item):
    """Extraer precio del producto específicamente para Sirena"""
    selectores_precio = [
        # Selectores de precio comunes
        '.price',
        '.precio',
        '.cost',
        '.amount',
        '.money',
        # Específicos de e-commerce
        'span[class*="price"]',
        'div[class*="price"]',
        '.product-price',
        '.item-price',
        # Específicos posibles de Sirena
        '.sirena-price',
        '.current-price',
        '.regular-price',
        # Más específicos
        '[data-price]',
        '.price-current',
        '.price-regular'
    ]
    
    for selector in selectores_precio:
        try:
            elemento = item.select_one(selector)
            if elemento:
                precio_texto = elemento.get_text().strip()
                # Verificar si contiene símbolos de moneda o números
                if precio_texto and (any(simbolo in precio_texto for simbolo in ['$', 'RD$', 'DOP', '₡']) or 
                                   re.search(r'\d+[.,]?\d*', precio_texto)):
                    return precio_texto
                
                # Intentar atributos
                for attr in ['data-price', 'data-amount', 'content']:
                    valor = elemento.get(attr, '').strip()
                    if valor and re.search(r'\d+', valor):
                        return valor
        except:
            continue
    
    # Buscar patrones de precio en todo el texto del item
    texto_completo = item.get_text()
    patrones_precio = [
        r'RD\$\s*\d+[.,]?\d*',  # Peso dominicano
        r'\$\s*\d+[.,]?\d*',     # Dólar genérico
        r'DOP\s*\d+[.,]?\d*',    # Código de moneda
        r'\d+[.,]\d+\s*(?:RD\$|DOP|\$)',  # Número seguido de moneda
        r'\d{1,6}[.,]\d{2}',     # Formato decimal
        r'\d{1,6}[.,]\d{1}',     # Formato decimal con un decimal
        r'\d+\s*(?:pesos?|RD)',  # Número seguido de "pesos" o "RD"
    ]
    
    for patron in patrones_precio:
        match = re.search(patron, texto_completo, re.IGNORECASE)
        if match:
            return match.group().strip()
    
    return "Sin precio"

def procesar_categoria_sirena(url_categoria, nombre_categoria):
    """Procesar todos los productos de una categoría en Sirena"""
    print(f"\n{'='*50}")
    print(f"PROCESANDO CATEGORÍA: {nombre_categoria}")
    print(f"URL: {url_categoria}")
    print(f"{'='*50}")
    
    productos_categoria = []
    pagina_actual = 1
    max_paginas = 5  # Limitar a 5 páginas por categoría
    
    while pagina_actual <= max_paginas:
        print(f"\n--- Página {pagina_actual} ---")
        
        # Construir URL de la página
        if pagina_actual == 1:
            url_pagina = url_categoria
        else:
            # Intentar diferentes formatos de paginación
            formatos_paginacion = [
                f"{url_categoria}?page={pagina_actual}",
                f"{url_categoria}&page={pagina_actual}",
                f"{url_categoria}/page/{pagina_actual}",
                f"{url_categoria}?p={pagina_actual}",
                f"{url_categoria}&p={pagina_actual}"
            ]
            url_pagina = formatos_paginacion[0]  # Usar el primero por defecto
        
        # Obtener página
        html = obtener_pagina(url_pagina)
        if not html:
            print(f"❌ No se pudo obtener la página {pagina_actual}")
            break
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extraer productos de esta página
        productos = extraer_productos_sirena(soup)
        
        if not productos:
            print(f"No se encontraron productos en la página {pagina_actual}")
            break
        
        print(f"✓ {len(productos)} productos encontrados en página {pagina_actual}")
        
        for producto in productos:
            productos_categoria.append({
                'Nombre': producto['nombre'],
                'Precio': producto['precio'],
                'Categoria': nombre_categoria,
                'URL_Categoria': url_categoria
            })
        
        # Si encontramos menos de 10 productos, probablemente no hay más páginas
        if len(productos) < 10:
            break
            
        pagina_actual += 1
        time.sleep(2)  # Pausa entre páginas
    
    print(f"✓ TOTAL EN '{nombre_categoria}': {len(productos_categoria)} productos")
    return productos_categoria

def main():
    base_url = 'https://www.sirena.do/'
    todos_productos = []
    
    print("🚀 INICIANDO SCRAPING DE SIRENA.DO")
    print("=" * 60)
    
    # Obtener página principal
    print("Obteniendo página principal...")
    html_principal = obtener_pagina(base_url)
    
    if not html_principal:
        print("❌ No se pudo obtener la página principal")
        return
    
    soup_principal = BeautifulSoup(html_principal, 'html.parser')
    
    # Encontrar categorías
    print("\nBuscando categorías de productos...")
    categorias = encontrar_categorias_sirena(soup_principal, base_url)
    
    if not categorias:
        print("❌ No se encontraron categorías válidas")
        # Intentar URLs de categorías conocidas como fallback
        categorias_fallback = [
            ('https://www.sirena.do/productos', 'Productos'),
            ('https://www.sirena.do/categoria/carnes', 'Carnes'),
            ('https://www.sirena.do/categoria/lacteos', 'Lácteos'),
            ('https://www.sirena.do/categoria/frutas-vegetales', 'Frutas y Vegetales'),
            ('https://www.sirena.do/categoria/bebidas', 'Bebidas'),
            ('https://www.sirena.do/categoria/limpieza', 'Limpieza'),
        ]
        
        print("Usando categorías predeterminadas...")
        categorias = categorias_fallback
    
    print(f"\n✓ {len(categorias)} categorías para procesar:")
    for i, (url, nombre) in enumerate(categorias, 1):
        print(f"  {i:2d}. {nombre}")
    
    print(f"\nCOMENZANDO EXTRACCIÓN DE PRODUCTOS...")
    
    # Procesar cada categoría
    for i, (url_categoria, nombre_categoria) in enumerate(categorias, 1):
        try:
            print(f"\n[{i}/{len(categorias)}] Procesando: {nombre_categoria}")
            
            productos_categoria = procesar_categoria_sirena(url_categoria, nombre_categoria)
            
            if productos_categoria:
                todos_productos.extend(productos_categoria)
                print(f"✓ {len(productos_categoria)} productos agregados")
            else:
                print(f"⚠ No se encontraron productos en {nombre_categoria}")
            
            time.sleep(3)  # Pausa entre categorías
            
        except Exception as e:
            print(f"❌ Error procesando {nombre_categoria}: {e}")
            continue
    
    # ELIMINAR DUPLICADOS
    if todos_productos:
        productos_unicos = eliminar_duplicados_avanzado(todos_productos)
        
        # Preparar datos finales con categorías combinadas
        productos_finales = []
        for producto in productos_unicos:
            productos_finales.append({
                'Nombre': producto['Nombre'],
                'Precio': producto['Precio'],
                'Categorias': '; '.join(producto['Categorias']),
                'URL_Categoria': producto['URL_Categoria']
            })
        
        # Guardar resultados finales
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
        print('\n❌ No se extrajeron productos')

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹ Proceso interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()