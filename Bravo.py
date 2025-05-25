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
            print(f"Obteniendo: {url[:60]}...")
            response = requests.get(url, headers=headers, timeout=timeout, verify=False)
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
    if nombre1_norm in nombre2_norm or nombre2_norm in nombre1_norm:
        # Si los nombres son similares, verificar precios
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
    productos_procesados = set()
    
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

def es_categoria_valida(url, texto):
    """Determinar si es una categoría válida de supermercado - Super Bravo"""
    texto_lower = texto.lower().strip()
    url_lower = url.lower()
    
    # Excluir elementos de navegación y páginas no deseadas
    excluir = [
        'ver todo', 'ver mas', 'mi cuenta', 'mi carrito', 'mis listas', 
        'mis ordenes', 'cerrar sesión', 'iniciar sesión', 'crear cuenta', 
        'nuestras tiendas', 'políticas', 'retiro en tienda', 'ayuda', 'contacto',
        'inicio', 'soporte', 'trabaja con nosotros', 'sucursales', 'home',
        'ofertas', 'promociones', 'javascript:', '#', 'mailto:', 'tel:',
        'login', 'register', 'cart', 'checkout', 'search', 'buscar',
        'facebook', 'instagram', 'twitter', 'youtube', 'whatsapp'
    ]
    
    # Verificar exclusiones
    for termino in excluir:
        if termino in texto_lower or termino in url_lower:
            return False
    
    # Debe tener texto válido
    if len(texto.strip()) < 3 or len(texto.strip()) > 50:
        return False
    
    # Categorías válidas de supermercado República Dominicana
    categorias_validas = [
        'carne', 'res', 'pollo', 'cerdo', 'pescado', 'mariscos', 'embutidos',
        'leche', 'queso', 'yogurt', 'lácteos', 'huevos',
        'fruta', 'vegetal', 'verdura', 'hortalizas', 'vegetales', 'frutas',
        'pan', 'panadería', 'cereales', 'arroz', 'pasta', 'granos',
        'bebida', 'agua', 'jugo', 'café', 'té', 'vino', 'cerveza', 'licores',
        'limpieza', 'detergente', 'jabón', 'hogar', 'aseo', 'lavandería',
        'shampoo', 'cuidado personal', 'higiene', 'pañal', 'farmacia',
        'sal', 'azúcar', 'aceite', 'condimento', 'especias', 'salsa',
        'conserva', 'enlatado', 'mermelada', 'congelado', 'helado',
        'mascota', 'gato', 'perro', 'despensa', 'abarrotes', 'snacks', 'dulces',
        'electrónico', 'electrodoméstico', 'bazar', 'juguete', 'ropa', 'textil'
    ]
    
    # Verificar si contiene términos de supermercado
    for termino in categorias_validas:
        if termino in texto_lower:
            return True
    
    return False

def encontrar_categorias(soup, base_url):
    """Encontrar categorías de productos válidas - Super Bravo"""
    categorias = set()
    
    # Selectores específicos para Super Bravo
    selectores = [
        # Menú principal
        '.main-menu a[href]', '.navbar a[href]', '.nav-menu a[href]',
        # Navegación de categorías
        '.category-menu a[href]', '.categories a[href]', '.cat-menu a[href]',
        # Enlaces generales
        'nav a[href]', 'header a[href]', '.header a[href]',
        '.navigation a[href]', '.menu a[href]',
        # Listas de categorías
        'ul li a[href]', '.category-list a[href]',
        # Dropdowns y submenús
        '.dropdown-menu a[href]', '.submenu a[href]',
        # Enlaces en el footer que puedan ser categorías
        'footer a[href]',
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
                    
                    # Verificar que la URL pertenezca al dominio
                    if 'superbravo.com.do' in url_completa and es_categoria_valida(url_completa, texto):
                        categorias.add((url_completa, texto))
                        print(f"✓ Categoría encontrada: {texto}")
        except Exception as e:
            continue
    
    return list(categorias)

def extraer_productos_pagina(soup):
    """Extraer productos de una página - Super Bravo"""
    productos = []
    
    # Selectores específicos para Super Bravo (adaptables)
    selectores_productos = [
        # Selectores comunes de productos
        '.product-item', '.product', '.item-product', '.producto',
        '.product-card', '.product-box', '.item-box',
        # Selectores de grids y listas
        'div[class*="product"]', 'li[class*="product"]',
        '.grid-item', '.list-item', '.item', '.card',
        # Selectores de artículos
        'article', '.catalog-item', '.shop-item',
        # Selectores genéricos
        '.product-wrap', '.product-container', '.item-wrap'
    ]
    
    items_encontrados = []
    for selector in selectores_productos:
        try:
            items = soup.select(selector)
            if len(items) > len(items_encontrados):
                items_encontrados = items
                print(f"Mejor selector encontrado: {selector} ({len(items)} items)")
        except:
            continue
    
    print(f"Encontrados {len(items_encontrados)} elementos de productos")
    
    for item in items_encontrados:
        try:
            nombre = extraer_nombre_producto(item)
            precio = extraer_precio_producto(item)
            
            if nombre and len(nombre.strip()) > 2:
                productos.append({
                    'nombre': nombre,
                    'precio': precio
                })
        except:
            continue
    
    return productos

def extraer_nombre_producto(item):
    """Extraer nombre del producto - Super Bravo"""
    selectores_nombre = [
        # Selectores específicos de nombres
        'a.product-item-link', '.product-name a', '.product-title',
        '.product-name', '.item-name', '.product-title',
        # Títulos y encabezados
        'h1', 'h2', 'h3', 'h4', 'h5',
        '.name', '.title', '.product-info h3', '.product-info h4',
        # Enlaces con título
        'a[title]', 'a.product-link',
        # Selectores alternativos
        '.product-description', '.item-title'
    ]
    
    for selector in selectores_nombre:
        try:
            elemento = item.select_one(selector)
            if elemento:
                texto = elemento.get_text().strip()
                if texto and len(texto) > 2 and len(texto) < 150:
                    return texto
                
                # Intentar atributos
                for attr in ['title', 'alt', 'data-name', 'data-title']:
                    valor = elemento.get(attr, '').strip()
                    if valor and len(valor) > 2 and len(valor) < 150:
                        return valor
        except:
            continue
    
    return "Sin nombre"

def extraer_precio_producto(item):
    """Extraer precio del producto - Super Bravo"""
    selectores_precio = [
        # Selectores específicos de precios
        '.price', '.precio', '.cost', '.amount',
        'span[class*="price"]', 'div[class*="price"]',
        '.product-price', '.item-price', '.price-current',
        '.price-now', '.sale-price', '.regular-price',
        # Selectores con moneda dominicana
        'span[class*="pesos"]', 'span[class*="rd"]',
        '.currency', '.money'
    ]
    
    for selector in selectores_precio:
        try:
            elemento = item.select_one(selector)
            if elemento:
                precio_texto = elemento.get_text().strip()
                # Buscar patrones de precio dominicano (RD$ o $)
                if precio_texto and ('RD$' in precio_texto or '$' in precio_texto or 
                                   re.search(r'\d+[.,]\d+', precio_texto)):
                    return precio_texto
        except:
            continue
    
    # Buscar patrones de precio en todo el texto del item
    texto_completo = item.get_text()
    patrones_precio = [
        r'RD\$\s*\d+[.,]?\d*', r'\$\s*\d+[.,]?\d*',
        r'\d+[.,]\d+\s*RD\$', r'\d+[.,]\d+\s*\$',
        r'\d{1,6}[.,]\d{2}', r'\d+\.\d{2}', r'\d+,\d{2}'
    ]
    
    for patron in patrones_precio:
        match = re.search(patron, texto_completo)
        if match:
            return match.group().strip()
    
    return "Sin precio"

def procesar_categoria(url_categoria, nombre_categoria):
    """Procesar todos los productos de una categoría - Super Bravo"""
    print(f"\n{'='*50}")
    print(f"PROCESANDO CATEGORÍA: {nombre_categoria}")
    print(f"URL: {url_categoria}")
    print(f"{'='*50}")
    
    productos_categoria = []
    
    # Obtener página de la categoría
    html = obtener_pagina(url_categoria)
    if not html:
        print("❌ No se pudo obtener la página")
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Extraer productos de esta página
    productos = extraer_productos_pagina(soup)
    
    for producto in productos:
        productos_categoria.append({
            'Nombre': producto['nombre'],
            'Precio': producto['precio'],
            'Categoria': nombre_categoria,
            'URL_Categoria': url_categoria
        })
    
    print(f"✓ {len(productos_categoria)} productos extraídos de '{nombre_categoria}'")
    
    print(f"✓ TOTAL EN '{nombre_categoria}': {len(productos_categoria)} productos")
    return productos_categoria

def main():
    base_url = 'https://www.superbravo.com.do/'
    todos_productos = []
    
    print("🚀 INICIANDO SCRAPING DE SUPER BRAVO")
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
    categorias = encontrar_categorias(soup_principal, base_url)
    
    if not categorias:
        print("❌ No se encontraron categorías válidas")
        return
    
    # Remover duplicados de categorías
    categorias_unicas = list(set(categorias))
    print(f"\n✓ {len(categorias_unicas)} categorías únicas encontradas:")
    for i, (url, nombre) in enumerate(categorias_unicas[:20], 1):  # Mostrar solo las primeras 20
        print(f"  {i:2d}. {nombre}")
    
    if len(categorias_unicas) > 20:
        print(f"  ... y {len(categorias_unicas) - 20} más")
    
    print(f"\nCOMENZANDO EXTRACCIÓN DE PRODUCTOS...")
    
    # Procesar cada categoría (limitar a las primeras 15 para prueba)
    categorias_a_procesar = categorias_unicas[:15]
    
    for i, (url_categoria, nombre_categoria) in enumerate(categorias_a_procesar, 1):
        try:
            print(f"\n[{i}/{len(categorias_a_procesar)}] Procesando: {nombre_categoria}")
            
            productos_categoria = procesar_categoria(url_categoria, nombre_categoria)
            
            if productos_categoria:
                todos_productos.extend(productos_categoria)
                print(f"✓ {len(productos_categoria)} productos agregados")
            
            time.sleep(2)  # Pausa entre categorías
            
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
        archivo_final = f'inventario_superbravo_{timestamp}.csv'
        
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
        for categoria, cantidad in sorted(resumen.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"   {categoria}: {cantidad} productos")
            
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