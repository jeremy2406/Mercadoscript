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
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.sirena.do/'
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

def analizar_estructura_pagina(soup, url):
    """Analizar la estructura de la página para entender cómo está organizada"""
    print(f"\n🔍 ANALIZANDO ESTRUCTURA DE: {url}")
    print("-" * 60)
    
    # Analizar elementos principales
    elementos_principales = [
        ('nav', 'Elementos de navegación'),
        ('header', 'Headers'),
        ('main', 'Contenido principal'),
        ('aside', 'Barras laterales'),
        ('footer', 'Pie de página'),
        ('.menu', 'Menús con clase menu'),
        ('.navigation', 'Navegación'),
        ('.navbar', 'Barras de navegación'),
        ('.category', 'Elementos con categoria'),
        ('.product', 'Elementos con producto')
    ]
    
    for selector, descripcion in elementos_principales:
        elementos = soup.select(selector)
        if elementos:
            print(f"✓ {descripcion}: {len(elementos)} encontrados")
            
            # Mostrar algunos ejemplos de clases
            clases_unicas = set()
            for elem in elementos[:5]:  # Solo los primeros 5
                clases = elem.get('class', [])
                if clases:
                    clases_unicas.update(clases)
            
            if clases_unicas:
                print(f"  Clases encontradas: {', '.join(list(clases_unicas)[:10])}")
    
    # Buscar datos estructurados (JSON-LD, microdata, etc.)
    scripts_json = soup.find_all('script', type='application/ld+json')
    if scripts_json:
        print(f"✓ Scripts JSON-LD encontrados: {len(scripts_json)}")
    
    # Analizar todos los enlaces únicos
    enlaces = soup.find_all('a', href=True)
    dominios_enlaces = set()
    patrones_url = defaultdict(int)
    
    for enlace in enlaces:
        href = enlace.get('href', '')
        if href.startswith('http'):
            dominio = urlparse(href).netloc
            dominios_enlaces.add(dominio)
        
        # Analizar patrones de URL
        if 'categoria' in href.lower() or 'category' in href.lower():
            patrones_url['categoria'] += 1
        elif 'producto' in href.lower() or 'product' in href.lower():
            patrones_url['producto'] += 1
        elif 'departamento' in href.lower() or 'department' in href.lower():
            patrones_url['departamento'] += 1
    
    print(f"\n📊 ANÁLISIS DE ENLACES:")
    print(f"Total de enlaces: {len(enlaces)}")
    print(f"Dominios externos: {len(dominios_enlaces)}")
    for patron, cantidad in patrones_url.items():
        if cantidad > 0:
            print(f"Enlaces con '{patron}': {cantidad}")
    
    return True

def encontrar_categorias_mejorado(soup, base_url):
    """Versión mejorada para encontrar categorías específicas de Sirena"""
    categorias = set()
    
    print("\n🔍 BUSCANDO CATEGORÍAS...")
    
    # 1. Buscar en menús de navegación principales
    selectores_navegacion = [
        'nav ul li a',
        '.main-menu a',
        '.primary-menu a',
        '.menu-principal a',
        '.navbar-nav a',
        'header nav a',
        '.navigation a',
        '.main-navigation a'
    ]
    
    for selector in selectores_navegacion:
        elementos = soup.select(selector)
        for enlace in elementos:
            procesar_enlace_categoria(enlace, base_url, categorias, "Navegación principal")
    
    # 2. Buscar en menús desplegables y megamenús
    selectores_dropdown = [
        '.dropdown-menu a',
        '.mega-menu a',
        '.submenu a',
        '.menu-dropdown a',
        '.categories-menu a'
    ]
    
    for selector in selectores_dropdown:
        elementos = soup.select(selector)
        for enlace in elementos:
            procesar_enlace_categoria(enlace, base_url, categorias, "Menú desplegable")
    
    # 3. Buscar categorías en sidebar o secciones específicas
    selectores_sidebar = [
        '.sidebar-categories a',
        '.category-list a',
        '.categories a',
        '.shop-categories a',
        'aside a'
    ]
    
    for selector in selectores_sidebar:
        elementos = soup.select(selector)
        for enlace in elementos:
            procesar_enlace_categoria(enlace, base_url, categorias, "Sidebar")
    
    # 4. Buscar por patrones en URLs
    todos_enlaces = soup.find_all('a', href=True)
    patrones_categoria = [
        r'/categoria/',
        r'/category/',
        r'/departamento/',
        r'/department/',
        r'/seccion/',
        r'/section/'
    ]
    
    for enlace in todos_enlaces:
        href = enlace.get('href', '')
        for patron in patrones_categoria:
            if re.search(patron, href, re.IGNORECASE):
                procesar_enlace_categoria(enlace, base_url, categorias, f"Patrón URL ({patron})")
                break
    
    # 5. Buscar en elementos con data attributes relacionados con categorías
    elementos_data = soup.select('[data-category], [data-cat], [data-section]')
    for elemento in elementos_data:
        enlace = elemento.find('a') or elemento
        if enlace and enlace.name == 'a':
            procesar_enlace_categoria(enlace, base_url, categorias, "Data attribute")
    
    return list(categorias)

def procesar_enlace_categoria(enlace, base_url, categorias, fuente):
    """Procesar un enlace individual para determinar si es una categoría válida"""
    href = enlace.get('href', '').strip()
    texto = enlace.get_text().strip()
    title = enlace.get('title', '').strip()
    
    if not href or href in['#', '/', 'javascript:void(0)', 'javascript:;']:
        return
    
    # Construir URL completa
    if href.startswith('http'):
        url_completa = href
    else:
        url_completa = urljoin(base_url, href)
    
    # Verificar dominio
    parsed_base = urlparse(base_url)
    parsed_url = urlparse(url_completa)
    
    if parsed_url.netloc and parsed_url.netloc != parsed_base.netloc:
        return
    
    # Usar el texto más descriptivo disponible
    nombre_categoria = texto or title or href.split('/')[-1]
    
    if es_categoria_valida_sirena_mejorado(url_completa, nombre_categoria):
        categorias.add((url_completa, nombre_categoria, fuente))
        print(f"✓ Categoría encontrada ({fuente}): {nombre_categoria}")

def es_categoria_valida_sirena_mejorado(url, texto):
    """Versión mejorada para validar categorías de Sirena"""
    texto_lower = texto.lower().strip()
    url_lower = url.lower()
    
    # Excluir elementos definitivamente no deseados
    excluir_exacto = [
        'inicio', 'home', 'ver todo', 'ver todos', 'mi cuenta', 'mi carrito', 
        'login', 'registro', 'contacto', 'nosotros', 'about', 'ayuda', 'help',
        'términos', 'políticas', 'privacy', 'soporte', 'support', 'faq',
        'blog', 'noticias', 'news', 'ofertas', 'promociones', 'cupones',
        'facebook', 'instagram', 'twitter', 'youtube', 'linkedin'
    ]
    
    # Excluir por contenido
    excluir_contenido = [
        'javascript:', 'mailto:', 'tel:', '#', 'void(0)'
    ]
    
    # Verificar exclusiones exactas
    if texto_lower in excluir_exacto:
        return False
    
    # Verificar exclusiones por contenido
    for excluir in excluir_contenido:
        if excluir in url_lower or excluir in texto_lower:
            return False
    
    # Debe tener texto válido
    if len(texto.strip()) < 2 or len(texto.strip()) > 80:
        return False
    
    # Palabras clave positivas para supermercados en RD
    palabras_positivas = [
        # Carnes y proteínas
        'carne', 'res', 'pollo', 'cerdo', 'pescado', 'mariscos', 'embutidos', 
        'charcutería', 'jamón', 'salchicha', 'chorizo',
        
        # Lácteos
        'leche', 'queso', 'yogurt', 'lácteos', 'huevos', 'mantequilla', 'crema',
        
        # Frutas y vegetales
        'fruta', 'frutas', 'vegetal', 'vegetales', 'verdura', 'verduras', 
        'hortalizas', 'produce', 'fresco', 'orgánico',
        
        # Panadería y granos
        'pan', 'panadería', 'cereales', 'arroz', 'pasta', 'granos', 'harinas',
        'avena', 'quinoa', 'frijoles', 'habichuelas',
        
        # Bebidas
        'bebida', 'bebidas', 'agua', 'jugo', 'jugos', 'café', 'té', 'refrescos', 
        'sodas', 'gaseosas', 'energética',
        
        # Alcohol
        'vino', 'cerveza', 'licores', 'alcohol', 'ron', 'whiskey', 'vodka',
        
        # Limpieza y hogar
        'limpieza', 'detergente', 'jabón', 'hogar', 'aseo', 'papel', 'servilletas',
        'desinfectante', 'suavizante',
        
        # Cuidado personal
        'shampoo', 'champú', 'cuidado personal', 'higiene', 'pañal', 'pañales',
        'pasta dental', 'desodorante', 'crema', 'loción',
        
        # Despensa
        'sal', 'azúcar', 'aceite', 'condimento', 'especias', 'salsa', 'sazonadores',
        'vinagre', 'mayonesa', 'ketchup', 'mostaza',
        
        # Conservas y enlatados
        'conserva', 'conservas', 'enlatado', 'enlatados', 'mermelada', 'miel',
        'sardina', 'atún', 'frijoles', 'maíz',
        
        # Congelados
        'congelado', 'congelados', 'helado', 'helados', 'frozen', 'hielo',
        
        # Mascotas
        'mascota', 'mascotas', 'gato', 'perro', 'pet', 'alimento para mascotas',
        
        # Snacks y dulces
        'snacks', 'dulces', 'galletas', 'cookies', 'chocolate', 'caramelos',
        'papitas', 'nachos', 'nuts', 'nueces',
        
        # Categorías generales
        'despensa', 'abarrotes', 'deli', 'delicatessen', 'gourmet', 'importados',
        'desayuno', 'breakfast', 'cocina', 'comida', 'alimentos',
        
        # Farmacia y salud
        'farmacia', 'medicina', 'medicinas', 'vitaminas', 'suplementos', 'health',
        'primeros auxilios', 'salud',
        
        # Términos específicos de supermercado
        'departamento', 'sección', 'categoria', 'productos', 'articulos'
    ]
    
    # Verificar si contiene términos positivos
    texto_completo = f"{texto_lower} {url_lower}"
    for palabra in palabras_positivas:
        if palabra in texto_completo:
            return True
    
    # Verificar patrones de URL que indican categorías
    patrones_url_positivos = [
        r'/categoria/',
        r'/category/',
        r'/departamento/',  
        r'/dept/',
        r'/seccion/',
        r'/productos/',
        r'/product/'
    ]
    
    for patron in patrones_url_positivos:
        if re.search(patron, url_lower):
            return True
    
    return False

def extraer_productos_mejorado(soup, url_categoria=""):
    """Versión mejorada para extraer productos de Sirena"""
    productos = []
    
    print(f"🔍 Analizando estructura de productos en: {url_categoria[:50]}...")
    
    # Selectores más específicos basados en estructura común de e-commerce
    selectores_productos = [
        # Selectores específicos de productos
        'div[class*="product"]',
        'article[class*="product"]',
        'li[class*="product"]',
        '.product-item',
        '.product-card',
        '.product-container',
        '.product-tile',
        '.item-product',
        
        # Selectores de grid/lista
        '.grid-item',
        '.list-item',
        '.catalog-item',
        '.shop-item',
        
        # Selectores generales pero comunes
        '.item',
        '.card',
        'article',
        
        # Selectores con data attributes
        '[data-product]',
        '[data-product-id]',
        '[data-item]',
        
        # Selectores específicos posibles de Sirena
        '.sirena-product',
        '.tienda-producto'
    ]
    
    mejor_resultado = []
    mejor_selector = ""
    
    # Probar cada selector y quedarse con el que más productos encuentre
    for selector in selectores_productos:
        try:
            elementos = soup.select(selector)
            productos_temp = []
            
            for elemento in elementos:
                nombre = extraer_nombre_mejorado(elemento)
                precio = extraer_precio_mejorado(elemento)
                
                if nombre and nombre != "Sin nombre" and len(nombre.strip()) > 2:
                    productos_temp.append({
                        'nombre': nombre,
                        'precio': precio,
                        'elemento_html': str(elemento)[:200] + "..."  # Para debug
                    })
            
            if len(productos_temp) > len(mejor_resultado):
                mejor_resultado = productos_temp
                mejor_selector = selector
                
        except Exception as e:
            continue
    
    print(f"✓ Mejor selector: '{mejor_selector}' con {len(mejor_resultado)} productos")
    
    # Si no encontramos productos con selectores específicos, intentar análisis más general
    if len(mejor_resultado) < 5:
        print("🔄 Intentando análisis más general...")
        productos_generales = extraer_productos_analisis_general(soup)
        if len(productos_generales) > len(mejor_resultado):
            mejor_resultado = productos_generales
            print(f"✓ Análisis general encontró {len(productos_generales)} productos")
    
    return mejor_resultado

def extraer_productos_analisis_general(soup):
    """Análisis general de la página para encontrar productos"""
    productos = []
    
    # Buscar cualquier elemento que contenga precio y nombre
    elementos_con_precio = soup.find_all(text=re.compile(r'[\$][\d,.]'))
    
    for elemento in elementos_con_precio:
        try:
            # Encontrar el elemento padre que contenga toda la información del producto
            padre = elemento.parent
            for _ in range(5):  # Subir hasta 5 niveles
                if padre is None:
                    break
                
                nombre = extraer_nombre_mejorado(padre)
                precio = extraer_precio_mejorado(padre)
                
                if nombre and nombre != "Sin nombre" and precio and precio != "Sin precio":
                    productos.append({
                        'nombre': nombre,
                        'precio': precio
                    })
                    break
                
                padre = padre.parent
                
        except:
            continue
    
    return productos

def extraer_nombre_mejorado(elemento):
    """Versión mejorada para extraer nombres de productos"""
    
    # Estrategia 1: Buscar en elementos de título específicos
    selectores_nombre = [
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        '.product-name', '.product-title', '.item-name', '.name', '.title',
        'a.product-link', 'a[title]',
        '.description', '.product-description',
        '[data-name]', '[data-product-name]', '[data-title]'
    ]
    
    for selector in selectores_nombre:
        try:
            sub_elemento = elemento.select_one(selector)
            if sub_elemento:
                texto = sub_elemento.get_text().strip()
                if validar_nombre_producto(texto):
                    return limpiar_nombre_producto(texto)
                
                # Intentar atributos
                for attr in ['title', 'alt', 'data-name', 'data-product-name']:
                    valor = sub_elemento.get(attr, '').strip()
                    if validar_nombre_producto(valor):
                        return limpiar_nombre_producto(valor)
        except:
            continue
    
    # Estrategia 2: Buscar el texto más largo que parezca un nombre de producto
    todos_textos = elemento.find_all(text=True)
    candidatos = []
    
    for texto in todos_textos:
        texto_limpio = texto.strip()
        if validar_nombre_producto(texto_limpio):
            candidatos.append(texto_limpio)
    
    if candidatos:
        # Ordenar por longitud y tomar el más descriptivo
        candidatos.sort(key=len, reverse=True)
        for candidato in candidatos:
            if 10 <= len(candidato) <= 100:  # Longitud razonable
                return limpiar_nombre_producto(candidato)
    
    return "Sin nombre"

def extraer_precio_mejorado(elemento):
    """Versión mejorada para extraer precios"""
    
    # Estrategia 1: Buscar en elementos de precio específicos
    selectores_precio = [
        '.price', '.precio', '.cost', '.amount', '.money',
        '[class*="price"]', '[class*="precio"]',
        '.product-price', '.item-price', '.current-price',
        '[data-price]', '[data-amount]'
    ]
    
    for selector in selectores_precio:
        try:
            sub_elemento = elemento.select_one(selector)
            if sub_elemento:
                precio_texto = sub_elemento.get_text().strip()
                if validar_precio(precio_texto):
                    return precio_texto
                
                # Intentar atributos
                for attr in ['data-price', 'data-amount', 'content', 'value']:
                    valor = sub_elemento.get(attr, '').strip()
                    if validar_precio(valor):
                        return valor
        except:
            continue
    
    # Estrategia 2: Buscar patrones de precio en todo el texto
    texto_completo = elemento.get_text()
    
    patrones_precio = [
        r'RD\$\s*[\d,]+\.?\d*',          # RD$1,234.56
        r'\$\s*[\d,]+\.?\d*',            # $1,234.56
        r'DOP\s*[\d,]+\.?\d*',           # DOP 1,234.56
        r'[\d,]+\.?\d*\s*(?:RD\$|DOP)',  # 1,234.56 RD$
        r'[\d,]{1,}\.[\d]{2}',           # 1,234.56
        r'[\d]{1,6}\.[\d]{2}',           # 1234.56
        r'[\d,]+\s*pesos?',              # 1,234 pesos
    ]
    
    for patron in patrones_precio:
        match = re.search(patron, texto_completo, re.IGNORECASE)
        if match:
            precio_encontrado = match.group().strip()
            if validar_precio(precio_encontrado):
                return precio_encontrado
    
    return "Sin precio"

def validar_nombre_producto(texto):
    """Validar si un texto parece ser un nombre de producto válido"""
    if not texto or len(texto.strip()) < 3:
        return False
    
    texto_lower = texto.lower().strip()
    
    # Excluir textos que claramente no son nombres de productos
    excluir = [
        'ver más', 'ver todo', 'añadir', 'agregar', 'comprar', 'carrito',
        'precio', 'oferta', 'descuento', 'envío', 'gratis', 'disponible',
        'stock', 'cantidad', 'unidades', 'kg', 'gr', 'ml', 'lt',
        'copyright', '©', 'todos los derechos', 'terms', 'privacy'
    ]
    
    for termino in excluir:
        if termino in texto_lower:
            return False
    
    # Debe tener una longitud razonable
    if len(texto) > 150:
        return False
    
    # Debe contener al menos una letra
    if not re.search(r'[a-zA-ZáéíóúñÁÉÍÓÚÑ]', texto):
        return False
    
    return True

def validar_precio(texto):
    """Validar si un texto parece ser un precio válido"""
    if not texto:
        return False
    
    # Debe contener números
    if not re.search(r'\d', texto):
        return False
    
    # Debe contener símbolos de moneda o patrones de precio
    patrones_validos = [
        r'[\$]',                    # Símbolo de dólar
        r'RD',                      # Pesos dominicanos
        r'DOP',                     # Código de moneda
        r'peso',                    # Palabra peso
        r'\d+[.,]\d+',             # Formato decimal
        r'\d{1,6}$'                # Solo números (podrían ser precios sin símbolo)
    ]
    
    for patron in patrones_validos:
        if re.search(patron, texto, re.IGNORECASE):
            return True
    
    return False

def limpiar_nombre_producto(nombre):
    """Limpiar y normalizar nombres de productos"""
    # Quitar numeración al inicio
    nombre = re.sub(r'^\d+\.\s*', '', nombre)
    
    # Normalizar espacios
    nombre = re.sub(r'\s+', ' ', nombre)
    
    # Quitar caracteres especiales innecesarios
    nombre = re.sub(r'[^\w\s\-\.\,\(\)\%\&]', '', nombre)
    
    return nombre.strip()

# Mantener las funciones originales de normalización y eliminación de duplicados
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

def procesar_categoria_mejorado(url_categoria, nombre_categoria):
    """Versión mejorada para procesar categorías de Sirena"""
    print(f"\n{'='*50}")
    print(f"PROCESANDO CATEGORÍA: {nombre_categoria}")
    print(f"URL: {url_categoria}")
    print(f"{'='*50}")
    
    productos_categoria = []
    pagina_actual = 1
    max_paginas = 3  # Reducido para evitar timeouts
    productos_sin_cambios = 0
    
    while pagina_actual <= max_paginas:
        print(f"\n--- Página {pagina_actual} ---")
        
        # Construir URL de la página
        if pagina_actual == 1:
            url_pagina = url_categoria
        else:
            # Probar diferentes formatos de paginación
            formatos_paginacion = [
                f"{url_categoria}?page={pagina_actual}",
                f"{url_categoria}&page={pagina_actual}",
                f"{url_categoria}/page/{pagina_actual}",
                f"{url_categoria}?p={pagina_actual}",
                f"{url_categoria}&p={pagina_actual}",
                f"{url_categoria}#{pagina_actual}"
            ]
            
            # Intentar el formato más común primero
            url_pagina = formatos_paginacion[0]
            if '?' in url_categoria:
                url_pagina = formatos_paginacion[1]
        
        # Obtener página
        html = obtener_pagina(url_pagina)
        if not html:
            print(f"❌ No se pudo obtener la página {pagina_actual}")
            break
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Analizar estructura en la primera página
        if pagina_actual == 1:
            analizar_estructura_pagina(soup, url_pagina)
        
        # Extraer productos de esta página
        productos = extraer_productos_mejorado(soup, url_pagina)
        
        if not productos:
            print(f"No se encontraron productos en la página {pagina_actual}")
            productos_sin_cambios += 1
            if productos_sin_cambios >= 2:  # Si 2 páginas seguidas sin productos, terminar
                break
        else:
            productos_sin_cambios = 0
            print(f"✓ {len(productos)} productos encontrados en página {pagina_actual}")
            
            # Mostrar algunos ejemplos para verificación
            if pagina_actual == 1 and productos:
                print("\n📋 EJEMPLOS DE PRODUCTOS ENCONTRADOS:")
                for i, prod in enumerate(productos[:3]):
                    print(f"  {i+1}. {prod['nombre'][:50]}... - {prod['precio']}")
            
            for producto in productos:
                productos_categoria.append({
                    'Nombre': producto['nombre'],
                    'Precio': producto['precio'],
                    'Categoria': nombre_categoria,
                    'URL_Categoria': url_categoria
                })
        
        # Si encontramos menos de 5 productos, probablemente no hay más páginas
        if len(productos) < 5:
            break
            
        pagina_actual += 1
        time.sleep(3)  # Pausa más larga entre páginas
    
    print(f"✓ TOTAL EN '{nombre_categoria}': {len(productos_categoria)} productos")
    return productos_categoria

def modo_debug_estructura(base_url):
    """Modo debug para analizar la estructura de la página principal"""
    print("🔧 MODO DEBUG - ANÁLISIS DE ESTRUCTURA")
    print("=" * 60)
    
    html = obtener_pagina(base_url)
    if not html:
        print("❌ No se pudo obtener la página principal")
        return False
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Análisis detallado
    print("\n📊 ANÁLISIS DETALLADO DE LA PÁGINA:")
    
    # Encontrar todos los elementos únicos
    elementos_unicos = set()
    for elemento in soup.find_all():
        if elemento.name:
            clases = ' '.join(elemento.get('class', []))
            if clases:
                elementos_unicos.add(f"{elemento.name}.{clases}")
            else:
                elementos_unicos.add(elemento.name)
    
    print(f"Elementos HTML únicos encontrados: {len(elementos_unicos)}")
    
    # Mostrar elementos que podrían contener categorías
    elementos_categoria = [elem for elem in elementos_unicos if 
                          any(palabra in elem.lower() for palabra in 
                              ['menu', 'nav', 'category', 'categoria', 'product', 'item'])]
    
    print(f"\nElementos posibles para categorías ({len(elementos_categoria)}):")
    for elem in sorted(elementos_categoria)[:20]:
        print(f"  - {elem}")
    
    # Buscar todos los enlaces y agrupar por patrones
    enlaces = soup.find_all('a', href=True)
    patrones_enlaces = defaultdict(list)
    
    for enlace in enlaces:
        href = enlace.get('href', '')
        texto = enlace.get_text().strip()
        
        if href and texto:
            # Clasificar por tipo de URL
            if 'categoria' in href.lower() or 'category' in href.lower():
                patrones_enlaces['Categorías'].append((href, texto))
            elif 'producto' in href.lower() or 'product' in href.lower():
                patrones_enlaces['Productos'].append((href, texto))
            elif any(palabra in texto.lower() for palabra in 
                    ['carne', 'leche', 'fruta', 'bebida', 'limpieza', 'pan']):
                patrones_enlaces['Posibles Categorías'].append((href, texto))
    
    print(f"\n🔗 ANÁLISIS DE ENLACES:")
    for tipo, enlaces_tipo in patrones_enlaces.items():
        print(f"\n{tipo} ({len(enlaces_tipo)}):")
        for href, texto in enlaces_tipo[:10]:  # Mostrar solo los primeros 10
            print(f"  - {texto[:30]:30} -> {href[:50]}")
    
    return True

def main():
    base_url = 'https://www.sirena.do/'
    todos_productos = []
    
    print("🚀 SCRAPER MEJORADO PARA SIRENA.DO")
    print("=" * 60)
    
    # Opción para modo debug
    print("¿Desea ejecutar modo debug para analizar la estructura? (s/n): ", end="")
    # En un script real, descomenta la siguiente línea:
    # respuesta = input().lower()
    respuesta = 'n'  # Por defecto no debug para ejecución automática
    
    if respuesta == 's':
        if modo_debug_estructura(base_url):
            print("\n¿Continuar con el scraping normal? (s/n): ", end="")
            # continuar = input().lower()
            continuar = 's'  # Por defecto sí para ejecución automática
            if continuar != 's':
                return
    
    # Obtener página principal
    print("\nObteniendo página principal...")
    html_principal = obtener_pagina(base_url)
    
    if not html_principal:
        print("❌ No se pudo obtener la página principal")
        return
    
    soup_principal = BeautifulSoup(html_principal, 'html.parser')
    
    # Analizar estructura de la página principal
    analizar_estructura_pagina(soup_principal, base_url)
    
    # Encontrar categorías con método mejorado
    print("\nBuscando categorías de productos...")
    categorias_encontradas = encontrar_categorias_mejorado(soup_principal, base_url)
    
    # Filtrar y organizar categorías
    categorias_unicas = {}
    for url, nombre, fuente in categorias_encontradas:
        # Evitar duplicados por URL
        if url not in categorias_unicas:
            categorias_unicas[url] = (nombre, fuente)
    
    categorias = [(url, datos[0]) for url, datos in categorias_unicas.items()]
    
    if not categorias:
        print("❌ No se encontraron categorías válidas")
        print("Intentando con URLs predeterminadas...")
        
        # URLs de fallback basadas en estructura típica de supermercados online
        categorias_fallback = [
            (f"{base_url}productos", "Productos"),
            (f"{base_url}categorias", "Categorías"),
            (f"{base_url}categoria/carnes", "Carnes"),
            (f"{base_url}categoria/lacteos", "Lácteos"),
            (f"{base_url}categoria/frutas-vegetales", "Frutas y Vegetales"),
            (f"{base_url}categoria/bebidas", "Bebidas"),
            (f"{base_url}categoria/limpieza", "Limpieza"),
            (f"{base_url}categoria/panaderia", "Panadería"),
            (f"{base_url}categoria/congelados", "Congelados"),
            (f"{base_url}categoria/despensa", "Despensa")
        ]
        
        # Verificar cuáles URLs de fallback existen
        categorias_validas = []
        for url, nombre in categorias_fallback:
            print(f"Verificando: {nombre}...")
            html_test = obtener_pagina(url)
            if html_test and len(html_test) > 1000:  # Si la página tiene contenido
                categorias_validas.append((url, nombre))
                print(f"✓ {nombre} - URL válida")
            else:
                print(f"✗ {nombre} - URL no válida")
            time.sleep(1)
        
        categorias = categorias_validas
    
    if not categorias:
        print("❌ No se pudieron encontrar categorías válidas")
        return
    
    print(f"\n✓ {len(categorias)} categorías para procesar:")
    for i, (url, nombre) in enumerate(categorias, 1):
        print(f"  {i:2d}. {nombre}")
    
    print(f"\nCOMENZANDO EXTRACCIÓN DE PRODUCTOS...")
    
    # Procesar cada categoría
    for i, (url_categoria, nombre_categoria) in enumerate(categorias, 1):
        try:
            print(f"\n[{i}/{len(categorias)}] Procesando: {nombre_categoria}")
            
            productos_categoria = procesar_categoria_mejorado(url_categoria, nombre_categoria)
            
            if productos_categoria:
                todos_productos.extend(productos_categoria)
                print(f"✓ {len(productos_categoria)} productos agregados de {nombre_categoria}")
            else:
                print(f"⚠ No se encontraron productos en {nombre_categoria}")
            
            time.sleep(5)  # Pausa más larga entre categorías
            
        except Exception as e:
            print(f"❌ Error procesando {nombre_categoria}: {e}")
            continue
    
    # PROCESAR RESULTADOS FINALES
    if todos_productos:
        print(f"\n📊 PROCESANDO {len(todos_productos)} PRODUCTOS TOTALES...")
        
        # Eliminar duplicados
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
        archivo_final = f'inventario_sirena_mejorado_{timestamp}.csv'
        
        with open(archivo_final, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['Nombre', 'Precio', 'Categorias', 'URL_Categoria'])
            writer.writeheader()
            writer.writerows(productos_finales)
        
        print(f'\n🎉 SCRAPING COMPLETADO EXITOSAMENTE')
        print(f'✓ {len(productos_finales)} productos únicos guardados en {archivo_final}')
        
        # Resumen detallado
        resumen = defaultdict(int)
        for producto in productos_unicos:
            for categoria in producto['Categorias']:
                resumen[categoria] += 1
        
        print(f"\n📊 RESUMEN POR CATEGORÍA:")
        for categoria, cantidad in sorted(resumen.items(), key=lambda x: x[1], reverse=True):
            print(f"   {categoria}: {cantidad} productos")
        
        # Mostrar algunos ejemplos de productos encontrados
        print(f"\n📋 EJEMPLOS DE PRODUCTOS EXTRAÍDOS:")
        for i, producto in enumerate(productos_finales[:10], 1):
            print(f"  {i:2d}. {producto['Nombre'][:60]:60} | {producto['Precio']:12} | {producto['Categorias']}")
            
    else:
        print('\n❌ No se extrajeron productos')
        print("\n🔧 SUGERENCIAS PARA RESOLVER EL PROBLEMA:")
        print("1. Verificar que sirena.do esté accesible")
        print("2. Revisar si la estructura de la página ha cambiado")
        print("3. Ejecutar en modo debug para analizar la estructura")
        print("4. Verificar si hay medidas anti-bot en el sitio")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹ Proceso interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error general: {e}")
        import traceback
        traceback.print_exc()