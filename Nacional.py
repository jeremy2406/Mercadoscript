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

def es_categoria_valida(url, texto):
    """Filtrar y determinar si es una categoría de productos válida"""
    
    # Lista de términos que NO son categorías válidas
    excluir_terminos = [
        'ver todo', 'ver todover todo', 'mis datos', 'mi cuenta', 'mi carrito', 'mis listas', 
        'mis ordenes', 'cerrar sesión', 'iniciar sesión', 'crear cuenta', 'nuestras tiendas',
        'políticas de privacidad', 'retiro en tienda', 'supermercadosnacional',
        'entrenamiento', 'ofertas de la semana', 'exclusivo online', 'prepara un desayuno',
        'hasta un 15 de descuento', 'ofertas quincenazo', '3x2 vinos', 'culinary tours',
        'javascript:', '#', 'aquí', '?q=', 'vinos-y-espumantes?vinos_3x2=1'
    ]
    
    # Lista de términos que SÍ indican categorías válidas de productos
    incluir_terminos = [
        # Carnes y proteínas
        'carne', 'res', 'pollo', 'cerdo', 'pavo', 'jamón', 'salami', 'chorizo', 'mortadela',
        'pescado', 'mariscos', 'camarón', 'salmón', 'atún', 'gallina', 'codorniz',
        
        # Lácteos y huevos
        'leche', 'queso', 'yogurt', 'mantequilla', 'crema', 'huevos', 'lácteos',
        
        # Frutas y vegetales
        'fruta', 'vegetal', 'verdura', 'hortalizas', 'manzana', 'pera', 'plátano',
        'lechuga', 'tomate', 'cebolla', 'papa', 'yuca', 'uva', 'fresa',
        
        # Panadería y cereales
        'pan', 'panadería', 'galleta', 'cereal', 'avena', 'arroz', 'pasta', 'harina',
        'repostería', 'bizcocho', 'croissant', 'bagel',
        
        # Bebidas
        'bebida', 'agua', 'jugo', 'refresco', 'soda', 'café', 'té', 'vino', 'cerveza',
        'whisky', 'ron', 'vodka', 'licor', 'champagne', 'malta', 'energizante',
        
        # Limpieza y hogar
        'limpieza', 'detergente', 'jabón', 'cloro', 'desinfectante', 'papel',
        'servilleta', 'ambientador', 'fregador', 'esponja',
        
        # Cuidado personal
        'shampoo', 'acondicionador', 'crema', 'desodorante', 'jabón', 'pasta dental',
        'cepillo', 'pañal', 'toalla', 'protector',
        
        # Condimentos y especias
        'sal', 'azúcar', 'aceite', 'vinagre', 'salsa', 'condimento', 'especia',
        'mayonesa', 'mostaza', 'catchup', 'aderezo',
        
        # Conservas y enlatados
        'conserva', 'enlatado', 'mermelada', 'miel', 'dulce', 'chocolate',
        
        # Congelados
        'congelado', 'helado', 'pizza congelada', 'vegetal congelado',
        
        # Mascotas
        'gato', 'perro', 'mascota', 'alimento para'
    ]
    
    texto_lower = texto.lower().strip()
    url_lower = url.lower()
    
    # Primero verificar exclusiones
    for termino in excluir_terminos:
        if termino in texto_lower or termino in url_lower:
            return False
    
    # Filtrar URLs que claramente no son categorías
    if any(x in url_lower for x in ['javascript:', '#', 'mailto:', 'tel:']):
        return False
    
    # Filtrar textos muy cortos o muy largos
    if len(texto.strip()) < 3 or len(texto.strip()) > 50:
        return False
    
    # Verificar si contiene términos de categorías válidas
    for termino in incluir_terminos:
        if termino in texto_lower:
            return True
    
    # Verificar patrones en la URL que indiquen categorías
    patrones_url_validos = [
        r'/categoria/',
        r'/departamento/',
        r'/seccion/',
        r'/[a-zA-Z-]+-y-[a-zA-Z-]+',  # ej: frutas-y-vegetales
        r'/[a-zA-Z-]+(?:es|as|os)$',   # terminaciones en plural
    ]
    
    for patron in patrones_url_validos:
        if re.search(patron, url_lower):
            return True
    
    # Si el texto parece ser una categoría (no contiene números, símbolos raros, etc.)
    if re.match(r'^[a-zA-ZáéíóúñÁÉÍÓÚÑ\s\-]+$', texto) and len(texto.split()) <= 4:
        # Verificar que no sea una frase de navegación común
        frases_navegacion = ['ver más', 'mostrar más', 'cargar más', 'página siguiente', 'anterior']
        if not any(frase in texto_lower for frase in frases_navegacion):
            return True
    
    return False

def encontrar_categorias_validas(soup, base_url):
    """Encontrar solo categorías válidas de productos"""
    categorias_validas = set()
    
    # Encontrar todos los enlaces
    enlaces = soup.find_all('a', href=True)
    print(f"Analizando {len(enlaces)} enlaces en total...")
    
    for enlace in enlaces:
        href = enlace.get('href', '').strip()
        texto = enlace.get_text().strip()
        
        if not href or href in ['#', '/', 'javascript:void(0)']:
            continue
            
        url_completa = urljoin(base_url, href)
        
        # Aplicar filtros de validación
        if es_categoria_valida(url_completa, texto):
            categorias_validas.add((url_completa, texto))
    
    print(f"✓ Filtradas a {len(categorias_validas)} categorías válidas")
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
    
    print("🚀 INICIANDO SCRAPING OPTIMIZADO Y FILTRADO")
    print("=" * 80)
    
    # Obtener página principal
    print("Obteniendo página principal...")
    html_principal = obtener_pagina(base_url)
    
    if not html_principal:
        print("❌ No se pudo obtener la página principal")
        return
    
    soup_principal = BeautifulSoup(html_principal, 'html.parser')
    
    # Encontrar solo categorías válidas
    print("\nBUSCANDO Y FILTRANDO CATEGORÍAS...")
    categorias_validas = encontrar_categorias_validas(soup_principal, base_url)
    
    if not categorias_validas:
        print("❌ No se encontraron categorías válidas")
        return
    
    print(f"\n📊 ENCONTRADAS {len(categorias_validas)} CATEGORÍAS VÁLIDAS")
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
            
            # Guardar progreso cada 20 categorías
            if i % 20 == 0:
                timestamp = int(time.time())
                archivo_progreso = f'progreso_inventario_{timestamp}.csv'
                
                with open(archivo_progreso, mode='w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=['Nombre', 'Precio', 'Categoría', 'URL_Categoria'])
                    writer.writeheader()
                    for producto in todos_productos:
                        writer.writerow(producto)
                
                print(f"💾 PROGRESO GUARDADO: {len(todos_productos)} productos")
            
            # Pausa entre categorías (reducida)
            time.sleep(2)
                
        except Exception as e:
            print(f"❌ Error procesando {nombre_categoria}: {e}")
            continue
    
    # Guardar resultados finales
    if todos_productos:
        timestamp = int(time.time())
        nombre_archivo = f'inventario_nacional_optimizado_{timestamp}.csv'
        
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

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹ Script interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error no controlado: {e}")
        import traceback
        print(traceback.format_exc())