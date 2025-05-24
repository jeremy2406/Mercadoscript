import requests
import csv
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
from collections import defaultdict

def obtener_pagina(url, timeout=60, reintentos=5):
    """Obtener contenido de una página web con reintentos agresivos"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'no-cache'
    }
    
    for intento in range(reintentos):
        try:
            print(f"Intento {intento + 1}/{reintentos} para: {url[:80]}...")
            session = requests.Session()
            response = session.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            print(f"✓ Página obtenida (Status: {response.status_code}, Tamaño: {len(response.text)} chars)")
            return response.text
        except requests.exceptions.Timeout:
            print(f"Timeout en intento {intento + 1}")
            if intento < reintentos - 1:
                time.sleep(10)
        except requests.exceptions.RequestException as e:
            print(f"Error en intento {intento + 1}: {e}")
            if intento < reintentos - 1:
                time.sleep(10)
        except Exception as e:
            print(f"Error inesperado en intento {intento + 1}: {e}")
            if intento < reintentos - 1:
                time.sleep(10)
    
    print(f"❌ FALLÓ después de {reintentos} intentos")
    return None

def es_categoria_supermercado(url, texto):
    """Determinar si es una categoría específica de productos de supermercado"""
    
    # Lista de términos que SÍ indican categorías válidas de SUPERMERCADO
    categorias_supermercado = [
        # Carnes y proteínas
        'carne', 'res', 'pollo', 'cerdo', 'pavo', 'jamón', 'salami', 'chorizo', 'mortadela',
        'pescado', 'mariscos', 'camarón', 'salmón', 'atún', 'embutidos', 'carnicería',
        
        # Lácteos y huevos
        'leche', 'queso', 'yogurt', 'mantequilla', 'crema', 'huevos', 'lácteos', 'yogur',
        
        # Frutas y vegetales
        'fruta', 'vegetal', 'verdura', 'hortalizas', 'vegetales', 'frutas',
        'manzana', 'pera', 'plátano', 'banano', 'lechuga', 'tomate', 'cebolla', 
        'papa', 'yuca', 'uva', 'fresa', 'naranja', 'limón',
        
        # Panadería y cereales
        'pan', 'panadería', 'galleta', 'cereal', 'avena', 'arroz', 'pasta', 'harina',
        'repostería', 'panaderia', 'cereales', 'granos', 'harinas',
        
        # Bebidas
        'bebida', 'agua', 'jugo', 'refresco', 'soda', 'café', 'té', 'vino', 'cerveza',
        'whisky', 'ron', 'vodka', 'licor', 'malta', 'energizante', 'bebidas',
        'jugos', 'refrescos', 'licores', 'vinos',
        
        # Limpieza y hogar
        'limpieza', 'detergente', 'jabón', 'cloro', 'desinfectante', 'papel',
        'servilleta', 'ambientador', 'hogar', 'aseo',
        
        # Cuidado personal
        'shampoo', 'acondicionador', 'crema', 'desodorante', 'pasta dental',
        'cepillo', 'pañal', 'toalla', 'protector', 'cuidado personal', 'higiene',
        
        # Condimentos y especias
        'sal', 'azúcar', 'aceite', 'vinagre', 'salsa', 'condimento', 'especia',
        'mayonesa', 'mostaza', 'ketchup', 'aderezo', 'condimentos',
        
        # Conservas y enlatados
        'conserva', 'enlatado', 'mermelada', 'miel', 'conservas', 'enlatados',
        
        # Congelados
        'congelado', 'helado', 'congelados', 'helados',
        
        # Mascotas
        'gato', 'perro', 'mascota', 'alimento para mascotas', 'mascotas',
        
        # Categorías generales de supermercado
        'despensa', 'abarrotes', 'comestibles', 'alimentación', 'alimentos',
        'snacks', 'dulces', 'chocolate', 'galletas'
    ]
    
    # Lista de términos que NO son categorías de supermercado
    excluir_terminos = [
        # Navegación y UI
        'ver todo', 'ver todover todo', 'mis datos', 'mi cuenta', 'mi carrito', 'mis listas', 
        'mis ordenes', 'cerrar sesión', 'iniciar sesión', 'crear cuenta', 'nuestras tiendas',
        'políticas de privacidad', 'retiro en tienda', 'supermercadosnacional',
        'aquí', 'inicio', 'contacto', 'ayuda', 'soporte',
        
        # Otras tiendas/marcas (no supermercado)
        'cuesta libros', 'juguetón', 'bebemundo', 'bebémundo', 'casa cuesta', 'jumbo',
        'bonos ccn', 'elasticsuite', 'trabaja con nosotros',
        
        # Promociones/ofertas generales
        'entrenamiento', 'ofertas de la semana', 'exclusivo online', 'prepara un desayuno',
        'hasta un 15 de descuento', 'ofertas quincenazo', '3x2 vinos', 'culinary tours',
        
        # URLs problemáticas
        'javascript:', '#', '?q=', 'search', 'buscar', 'filtro'
    ]
    
    texto_lower = texto.lower().strip()
    url_lower = url.lower()
    
    # Filtrar URLs que claramente no son categorías
    if any(x in url_lower for x in ['javascript:', '#', 'mailto:', 'tel:']):
        return False
    
    # Primero verificar exclusiones
    for termino in excluir_terminos:
        if termino in texto_lower or termino in url_lower:
            return False
    
    # Filtrar textos muy cortos o muy largos
    if len(texto.strip()) < 3 or len(texto.strip()) > 60:
        return False
    
    # RELAJAR LOS FILTROS: Verificar si contiene términos específicos de supermercado
    for termino in categorias_supermercado:
        if termino in texto_lower:
            print(f"    ✓ Coincidencia encontrada: '{texto}' contiene '{termino}'")
            return True
    
    # Verificar patrones en la URL que indiquen categorías de supermercado
    patrones_url_supermercado = [
        r'/categoria[s]?/',
        r'/departamento[s]?/',
        r'/seccion[es]?/',
        r'/(frutas?|verduras?|vegetales?|carnes?|lacteos?|bebidas?|limpieza|panaderia)',
        r'/[a-zA-Z-]+-y-[a-zA-Z-]+',  # ej: frutas-y-vegetales
    ]
    
    for patron in patrones_url_supermercado:
        if re.search(patron, url_lower):
            print(f"    ✓ Patrón URL encontrado: '{url_lower}' coincide con {patron}")
            return True
    
    # MODO DEBUG: Mostrar por qué se rechaza
    if len(texto.strip()) >= 3 and len(texto.strip()) <= 60:
        print(f"    ❌ Rechazado: '{texto}' (no coincide con términos de supermercado)")
    
    return False

def encontrar_categorias_supermercado(soup, base_url):
    """Encontrar específicamente categorías de productos de supermercado"""
    categorias_validas = set()
    
    # Buscar en TODAS las áreas posibles, empezando con las más específicas
    areas_busqueda = [
        # Selectores específicos comunes
        '.nav a[href]', '.navigation a[href]', '.menu a[href]', 
        '.main-menu a[href]', '.primary-menu a[href]', '.header-menu a[href]',
        '.category-menu a[href]', '.departments a[href]', '.categories a[href]',
        
        # Selectores más genéricos
        'nav a[href]', 'header a[href]', '.header a[href]',
        'ul li a[href]', 'ol li a[href]',
        
        # Selectores de estructura común
        '.container a[href]', '.wrapper a[href]', '.content a[href]',
        
        # Por último, todos los enlaces
        'a[href]'
    ]
    
    enlaces_encontrados = []
    
    # Probar cada selector y ver cuáles funcionan
    for selector in areas_busqueda:
        try:
            elementos = soup.select(selector)
            if elementos:
                print(f"✓ Encontrados {len(elementos)} enlaces con selector: {selector}")
                if len(elementos) > len(enlaces_encontrados):
                    enlaces_encontrados = elementos
                    if len(elementos) >= 50:  # Si encuentra muchos, usar estos
                        break
        except Exception as e:
            continue
    
    print(f"Analizando {len(enlaces_encontrados)} enlaces en total...")
    
    # Debuggear algunos enlaces para entender la estructura
    print("\n🔍 MUESTRA DE ENLACES ENCONTRADOS (primeros 20):")
    for i, enlace in enumerate(enlaces_encontrados[:20]):
        href = enlace.get('href', '').strip()
        texto = enlace.get_text().strip()
        print(f"  {i+1:2d}. '{texto}' -> {href}")
    
    # Procesar todos los enlaces
    for enlace in enlaces_encontrados:
        href = enlace.get('href', '').strip()
        texto = enlace.get_text().strip()
        
        if not href or href in ['#', '/', 'javascript:void(0)']:
            continue
            
        url_completa = urljoin(base_url, href)
        
        # Aplicar filtros específicos para supermercado
        if es_categoria_supermercado(url_completa, texto):
            categorias_validas.add((url_completa, texto))
            print(f"✓ Categoría válida encontrada: '{texto}' -> {url_completa}")
    
    print(f"✓ Total de categorías de supermercado encontradas: {len(categorias_validas)}")
    return list(categorias_validas)

def buscar_productos_exhaustivo(soup):
    """Buscar productos usando TODOS los selectores posibles"""
    selectores_productos = [
        # Selectores específicos comunes
        '.product-item', '.product', '.item-product', '.producto',
        'div[class*="product"]', 'li[class*="product"]',
        '.grid-item', '.product-card', '.item', '.card',
        '[data-product-id]', '[data-product]', '[data-item]',
        
        # Selectores de listas
        'ul.products li', 'ol.products li', '.products .item',
        '.product-list .item', '.items-list .item',
        
        # Selectores de grillas
        '.grid .item', '.row .col', '.flex-item',
        '.catalog-item', '.shop-item', '.store-item',
        
        # Selectores más genéricos
        'article', '.article', 'div[itemtype*="Product"]',
        '[class*="item"]', '[class*="card"]'
    ]
    
    productos_encontrados = []
    
    for selector in selectores_productos:
        try:
            items = soup.select(selector)
            if items and len(items) > len(productos_encontrados):
                productos_encontrados = items
                print(f"✓ Mejor resultado: {len(items)} productos con selector: {selector}")
        except Exception as e:
            continue
    
    # Si no encontramos productos con selectores específicos, buscar por patrones
    if len(productos_encontrados) < 5:
        print("Buscando productos por patrones en el HTML...")
        
        # Buscar divs que contengan información de precio
        divs_con_precio = soup.find_all('div', text=re.compile(r'\$|precio|price|€|₡|₵', re.I))
        divs_padre_precio = []
        for div in divs_con_precio:
            parent = div.parent
            if parent:
                divs_padre_precio.append(parent)
        
        if divs_padre_precio:
            productos_encontrados = divs_padre_precio
            print(f"✓ Encontrados {len(productos_encontrados)} productos por patrón de precio")
    
    return productos_encontrados

def extraer_info_producto_exhaustivo(item):
    """Extraer información del producto de manera exhaustiva"""
    nombre = 'Nombre no disponible'
    precio = 'Precio no disponible'
    
    # Selectores para nombres (más exhaustivos)
    selectores_nombre = [
        'a.product-item-link', '.product-name a', '.product-title',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        '.name a', '.title a', 'a[title]',
        '.product-name', '.name', '.title', '.titulo',
        '[class*="name"]', '[class*="title"]', '[class*="titulo"]',
        'a', 'span.name', 'div.name', 'p.name'
    ]
    
    # Selectores para precios (más exhaustivos)
    selectores_precio = [
        'span.price', '.price', '.precio', '.cost', '.amount',
        '[class*="price"]', '[class*="precio"]', '[class*="cost"]',
        'span[class*="$"]', 'div[class*="$"]',
        '.currency', '.money', '.value', '.valor'
    ]
    
    # Buscar nombre
    for selector in selectores_nombre:
        try:
            elemento = item.select_one(selector)
            if elemento:
                # Intentar obtener texto de diferentes maneras
                texto_candidatos = [
                    elemento.get_text().strip(),
                    elemento.get('title', '').strip(),
                    elemento.get('alt', '').strip(),
                    elemento.get('data-name', '').strip()
                ]
                
                for texto in texto_candidatos:
                    if texto and len(texto) > 2 and len(texto) < 200:
                        nombre = texto
                        break
                
                if nombre != 'Nombre no disponible':
                    break
        except:
            continue
    
    # Buscar precio
    for selector in selectores_precio:
        try:
            elemento = item.select_one(selector)
            if elemento:
                precio_texto = elemento.get_text().strip()
                if precio_texto and ('$' in precio_texto or '₡' in precio_texto or 
                                   re.search(r'\d+[.,]\d+', precio_texto)):
                    precio = precio_texto
                    break
        except:
            continue
    
    # Si no encontró precio, buscar números que parezcan precios
    if precio == 'Precio no disponible':
        texto_completo = item.get_text()
        patrones_precio = [
            r'\$\s*\d+[.,]?\d*',
            r'₡\s*\d+[.,]?\d*',
            r'\d+[.,]\d+\s*₡',
            r'\d+[.,]\d+\s*\$',
            r'precio[:\s]*\d+[.,]?\d*',
            r'\d{1,6}[.,]\d{2}'
        ]
        
        for patron in patrones_precio:
            match = re.search(patron, texto_completo, re.I)
            if match:
                precio = match.group()
                break
    
    return nombre, precio

def procesar_categoria_simple(url_categoria, nombre_categoria):
    """Procesar una categoría con UNA SOLA PÁGINA"""
    print(f"\n📂 PROCESANDO: {nombre_categoria}")
    print(f"URL: {url_categoria}")
    
    productos_categoria = []
    
    # Obtener solo la primera página
    html_pagina = obtener_pagina(url_categoria)
    if not html_pagina:
        print("❌ No se pudo obtener la página")
        return []
    
    soup = BeautifulSoup(html_pagina, 'html.parser')
    
    # Buscar productos en esta página
    items = buscar_productos_exhaustivo(soup)
    productos_en_pagina = 0
    
    if items:
        print(f"Encontrados {len(items)} productos en esta página")
        
        for item in items:
            try:
                nombre, precio = extraer_info_producto_exhaustivo(item)
                
                if nombre != 'Nombre no disponible' and len(nombre.strip()) > 2:
                    productos_categoria.append({
                        'Nombre': nombre,
                        'Precio': precio,
                        'Categoría': nombre_categoria,
                        'URL_Categoria': url_categoria
                    })
                    productos_en_pagina += 1
            
            except Exception as e:
                continue
        
        print(f"✓ {productos_en_pagina} productos válidos extraídos")
    else:
        print("Sin productos en esta página")
    
    print(f"✓ TOTAL EN '{nombre_categoria}': {len(productos_categoria)} productos")
    return productos_categoria

def main():
    base_url = 'https://supermercadosnacional.com/'
    todos_productos = []
    
    print("🚀 INICIANDO SCRAPING ESPECÍFICO PARA SUPERMERCADO")
    print("=" * 80)
    
    # Obtener página principal
    print("Obteniendo página principal...")
    html_principal = obtener_pagina(base_url)
    
    if not html_principal:
        print("❌ No se pudo obtener la página principal")
        return
    
    soup_principal = BeautifulSoup(html_principal, 'html.parser')
    
    # Encontrar solo categorías de supermercado
    print("\nBUSCANDO CATEGORÍAS ESPECÍFICAS DE SUPERMERCADO...")
    categorias_validas = encontrar_categorias_supermercado(soup_principal, base_url)
    
    if not categorias_validas:
        print("❌ No se encontraron categorías de supermercado válidas")
        print("Mostrando algunos enlaces encontrados para depuración:")
        enlaces_debug = soup_principal.find_all('a', href=True)[:20]
        for enlace in enlaces_debug:
            texto = enlace.get_text().strip()
            href = enlace.get('href', '')
            if texto and href:
                print(f"  - {texto} -> {href}")
        return
    
    print(f"\n📊 ENCONTRADAS {len(categorias_validas)} CATEGORÍAS DE SUPERMERCADO")
    print("\nLista de categorías a procesar:")
    for i, (url, nombre) in enumerate(categorias_validas, 1):
        print(f"  {i:3d}. {nombre}")
    
    # Procesar cada categoría (solo primera página)
    contador_categorias = 0
    contador_productos_total = 0
    
    for i, (url_categoria, nombre_categoria) in enumerate(categorias_validas, 1):
        try:
            print(f"\n{'='*15} CATEGORÍA {i}/{len(categorias_validas)} {'='*15}")
            
            productos_categoria = procesar_categoria_simple(url_categoria, nombre_categoria)
            
            if productos_categoria:
                todos_productos.extend(productos_categoria)
                contador_categorias += 1
                contador_productos_total += len(productos_categoria)
                
                print(f"✓ Completada: {len(productos_categoria)} productos")
            else:
                print(f"Sin productos en: {nombre_categoria}")
            
            # Guardar progreso cada 10 categorías
            if i % 10 == 0:
                timestamp = int(time.time())
                archivo_progreso = f'progreso_inventario_{timestamp}.csv'
                
                with open(archivo_progreso, mode='w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=['Nombre', 'Precio', 'Categoría', 'URL_Categoria'])
                    writer.writeheader()
                    for producto in todos_productos:
                        writer.writerow(producto)
                
                print(f"💾 PROGRESO GUARDADO: {len(todos_productos)} productos")
            
            # Pausa entre categorías
            time.sleep(3)
                
        except Exception as e:
            print(f"❌ Error procesando {nombre_categoria}: {e}")
            continue
    
    # Guardar resultados finales
    if todos_productos:
        timestamp = int(time.time())
        nombre_archivo = f'inventario_nacional_supermercado_{timestamp}.csv'
        
        with open(nombre_archivo, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['Nombre', 'Precio', 'Categoría', 'URL_Categoria'])
            writer.writeheader()
            for producto in todos_productos:
                writer.writerow(producto)
        
        print(f'\n🎉 SCRAPING COMPLETADO')
        print(f'✓ {len(todos_productos)} productos guardados en {nombre_archivo}')
        
        # Resumen por categoría
        categorias_resumen = defaultdict(int)
        for producto in todos_productos:
            categorias_resumen[producto['Categoría']] += 1
        
        print(f"\n📊 RESUMEN FINAL:")
        print(f"   Categorías procesadas: {contador_categorias}")
        print(f"   Total de productos: {len(todos_productos)}")
        print(f"\nProductos por categoría:")
        
        for categoria, cantidad in sorted(categorias_resumen.items(), key=lambda x: x[1], reverse=True):
            print(f"   {categoria}: {cantidad} productos")
            
    else:
        print('\n❗ No se extrajo ningún producto.')
        print('\n🔍 SUGERENCIAS PARA DEPURACIÓN:')
        print('   1. Verificar que el sitio web tenga un menú de categorías visible')
        print('   2. Inspeccionar manualmente el HTML del sitio para identificar selectores')
        print('   3. Considerar que el sitio podría requerir JavaScript para cargar categorías')

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹ Script interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error no controlado: {e}")
        import traceback
        print(traceback.format_exc())