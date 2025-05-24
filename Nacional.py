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
            print(f"🔄 Intento {intento + 1}/{reintentos} para: {url[:80]}...")
            session = requests.Session()
            response = session.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            print(f"✔ Página obtenida exitosamente (Status: {response.status_code}, Tamaño: {len(response.text)} chars)")
            return response.text
        except requests.exceptions.Timeout:
            print(f"⏰ Timeout en intento {intento + 1}")
            if intento < reintentos - 1:
                time.sleep(10)
        except requests.exceptions.RequestException as e:
            print(f"❌ Error en intento {intento + 1}: {e}")
            if intento < reintentos - 1:
                time.sleep(10)
        except Exception as e:
            print(f"🚨 Error inesperado en intento {intento + 1}: {e}")
            if intento < reintentos - 1:
                time.sleep(10)
    
    print(f"❌ FALLÓ después de {reintentos} intentos")
    return None

def encontrar_todos_los_enlaces(soup, base_url):
    """Encontrar TODOS los enlaces posibles que puedan ser categorías"""
    todos_enlaces = set()
    
    # Encontrar todos los enlaces en la página
    enlaces = soup.find_all('a', href=True)
    print(f"🔍 Analizando {len(enlaces)} enlaces en total...")
    
    palabras_clave = [
        'categoria', 'category', 'departamento', 'seccion', 'productos',
        'product', 'item', 'catalogo', 'tienda', 'shop', 'store',
        'carne', 'lacteo', 'bebida', 'limpieza', 'hogar', 'personal',
        'fruta', 'verdura', 'panaderia', 'congelado', 'dulce', 'snack'
    ]
    
    for enlace in enlaces:
        href = enlace.get('href', '').strip()
        texto = enlace.get_text().strip()
        
        if not href or href in ['#', '/', 'javascript:void(0)']:
            continue
            
        url_completa = urljoin(base_url, href)
        
        # Filtrar por URL que contenga palabras clave
        url_lower = url_completa.lower()
        texto_lower = texto.lower()
        
        es_categoria = False
        
        # Verificar si es una categoría por URL
        for palabra in palabras_clave:
            if palabra in url_lower:
                es_categoria = True
                break
        
        # Verificar si es una categoría por texto del enlace
        if not es_categoria and texto and len(texto) > 2 and len(texto) < 100:
            for palabra in palabras_clave:
                if palabra in texto_lower:
                    es_categoria = True
                    break
        
        # También incluir enlaces que tengan cierta estructura
        if not es_categoria:
            if re.search(r'/[a-zA-Z-]+/[a-zA-Z-]+', href) or 'id=' in href or 'cat=' in href:
                es_categoria = True
        
        if es_categoria and url_completa != base_url:
            nombre_categoria = texto if texto else href.split('/')[-1]
            todos_enlaces.add((url_completa, nombre_categoria))
    
    print(f"✔ Encontrados {len(todos_enlaces)} enlaces potenciales de categorías")
    return list(todos_enlaces)

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
                print(f"✔ Mejor resultado: {len(items)} productos con selector: {selector}")
        except Exception as e:
            continue
    
    # Si no encontramos productos con selectores específicos, buscar por patrones
    if len(productos_encontrados) < 5:
        print("🔍 Buscando productos por patrones en el HTML...")
        
        # Buscar divs que contengan información de precio
        divs_con_precio = soup.find_all('div', text=re.compile(r'\$|precio|price|€|₡|₵', re.I))
        divs_padre_precio = []
        for div in divs_con_precio:
            parent = div.parent
            if parent:
                divs_padre_precio.append(parent)
        
        if divs_padre_precio:
            productos_encontrados = divs_padre_precio
            print(f"✔ Encontrados {len(productos_encontrados)} productos por patrón de precio")
    
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

def buscar_paginacion(soup, base_url):
    """Buscar enlaces de paginación para obtener más productos"""
    enlaces_paginacion = set()
    
    selectores_paginacion = [
        '.pagination a', '.pager a', '.page-numbers a',
        'a[href*="page"]', 'a[href*="p="]', 'a[href*="pagina"]',
        '.next a', '.siguiente a', 'a.next', 'a.siguiente',
        '[class*="pagination"] a', '[class*="pager"] a'
    ]
    
    for selector in selectores_paginacion:
        try:
            elementos = soup.select(selector)
            for elem in elementos:
                href = elem.get('href')
                if href:
                    url_completa = urljoin(base_url, href)
                    enlaces_paginacion.add(url_completa)
        except:
            continue
    
    return list(enlaces_paginacion)

def procesar_categoria_completa(url_categoria, nombre_categoria, base_url):
    """Procesar una categoría completamente incluyendo todas sus páginas"""
    print(f"\n🏪 PROCESANDO CATEGORÍA COMPLETA: {nombre_categoria}")
    print(f"🔗 URL: {url_categoria}")
    
    productos_categoria = []
    paginas_procesadas = set()
    paginas_por_procesar = [url_categoria]
    
    while paginas_por_procesar:
        url_actual = paginas_por_procesar.pop(0)
        
        if url_actual in paginas_procesadas:
            continue
            
        paginas_procesadas.add(url_actual)
        print(f"\n📄 Procesando página: {url_actual}")
        
        html_pagina = obtener_pagina(url_actual)
        if not html_pagina:
            continue
        
        soup = BeautifulSoup(html_pagina, 'html.parser')
        
        # Buscar productos en esta página
        items = buscar_productos_exhaustivo(soup)
        productos_en_pagina = 0
        
        if items:
            print(f"🛍 Encontrados {len(items)} productos en esta página")
            
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
            
            print(f"✅ {productos_en_pagina} productos válidos extraídos de esta página")
        else:
            print("⚠ No se encontraron productos en esta página")
        
        # Buscar más páginas (paginación)
        enlaces_paginacion = buscar_paginacion(soup, base_url)
        for enlace in enlaces_paginacion:
            if enlace not in paginas_procesadas and enlace not in paginas_por_procesar:
                paginas_por_procesar.append(enlace)
                print(f"📋 Agregada página para procesar: {enlace}")
        
        # Pausa entre páginas
        time.sleep(3)
        
        # Limitar para evitar bucles infinitos
        if len(paginas_procesadas) > 20:
            print("⚠ Límite de páginas alcanzado para esta categoría")
            break
    
    print(f"🎯 TOTAL EN CATEGORÍA '{nombre_categoria}': {len(productos_categoria)} productos")
    return productos_categoria

def main():
    base_url = 'https://supermercadosnacional.com/'
    todos_productos = []
    
    print("🚀 INICIANDO SCRAPING EXHAUSTIVO")
    print("=" * 80)
    
    # Obtener página principal
    print("📄 Obteniendo página principal...")
    html_principal = obtener_pagina(base_url)
    
    if not html_principal:
        print("❌ No se pudo obtener la página principal")
        return
    
    soup_principal = BeautifulSoup(html_principal, 'html.parser')
    
    # Encontrar TODOS los enlaces posibles
    print("\n🔍 BUSCANDO TODOS LOS ENLACES POSIBLES...")
    todas_categorias = encontrar_todos_los_enlaces(soup_principal, base_url)
    
    if not todas_categorias:
        print("❌ No se encontraron categorías")
        return
    
    print(f"\n📊 ENCONTRADAS {len(todas_categorias)} CATEGORÍAS POTENCIALES")
    print("\n📋 Lista de categorías a procesar:")
    for i, (url, nombre) in enumerate(todas_categorias, 1):
        print(f"  {i:3d}. {nombre[:60]}")
    
    # Procesar cada categoría de manera exhaustiva
    contador_categorias = 0
    contador_productos_total = 0
    
    for i, (url_categoria, nombre_categoria) in enumerate(todas_categorias, 1):
        try:
            print(f"\n{'='*20} CATEGORÍA {i}/{len(todas_categorias)} {'='*20}")
            
            productos_categoria = procesar_categoria_completa(url_categoria, nombre_categoria, base_url)
            
            if productos_categoria:
                todos_productos.extend(productos_categoria)
                contador_categorias += 1
                contador_productos_total += len(productos_categoria)
                
                print(f"✅ Categoría completada: {len(productos_categoria)} productos")
            else:
                print(f"⚠ Sin productos en: {nombre_categoria}")
            
            # Guardar progreso cada 10 categorías
            if i % 10 == 0:
                timestamp = int(time.time())
                archivo_progreso = f'progreso_inventario_{timestamp}.csv'
                
                with open(archivo_progreso, mode='w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=['Nombre', 'Precio', 'Categoría', 'URL_Categoria'])
                    writer.writeheader()
                    for producto in todos_productos:
                        writer.writerow(producto)
                
                print(f"💾 PROGRESO GUARDADO: {len(todos_productos)} productos en {archivo_progreso}")
                
        except Exception as e:
            print(f"❌ Error procesando {nombre_categoria}: {e}")
            continue
    
    # Guardar resultados finales
    if todos_productos:
        timestamp = int(time.time())
        nombre_archivo = f'inventario_nacional_{timestamp}.csv'
        
        with open(nombre_archivo, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['Nombre', 'Precio', 'Categoría', 'URL_Categoria'])
            writer.writeheader()
            for producto in todos_productos:
                writer.writerow(producto)
        
        print(f'\n🎉 SCRAPING COMPLETADO')
        print(f'✅ {len(todos_productos)} productos guardados en {nombre_archivo}')
        
        # Resumen por categoría
        categorias_resumen = defaultdict(int)
        for producto in todos_productos:
            categorias_resumen[producto['Categoría']] += 1
        
        print(f"\n📊 RESUMEN FINAL:")
        print(f"   • Categorías procesadas: {contador_categorias}")
        print(f"   • Total de productos: {len(todos_productos)}")
        print(f"\n📋 Productos por categoría:")
        
        for categoria, cantidad in sorted(categorias_resumen.items(), key=lambda x: x[1], reverse=True):
            print(f"   • {categoria[:50]}: {cantidad} productos")
            
    else:
        print('\n❗ No se extrajo ningún producto.')

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹ Script interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error no controlado: {e}")
        import traceback
        print(traceback.format_exc())