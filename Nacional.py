import requests
import csv
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
from collections import defaultdict

def obtener_pagina(url, timeout=30, reintentos=3):
    """Obtener contenido de una página web"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
        'Connection': 'keep-alive'
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

def es_categoria_valida(url, texto):
    """Determinar si es una categoría válida de supermercado"""
    texto_lower = texto.lower().strip()
    url_lower = url.lower()
    
    # Excluir elementos de navegación y páginas no deseadas
    excluir = [
        'ver todo', 'ver todover todo', 'mi cuenta', 'mi carrito', 'mis listas', 
        'mis ordenes', 'cerrar sesión', 'iniciar sesión', 'crear cuenta', 
        'nuestras tiendas', 'políticas', 'retiro en tienda', 'ayuda', 'contacto',
        'inicio', 'soporte', 'trabaja con nosotros', 'cuesta libros', 'juguetón', 
        'bebemundo', 'casa cuesta', 'jumbo', 'bonos ccn', 'entrenamiento',
        'ofertas de la semana', 'exclusivo online', 'javascript:', '#', 'mailto:', 'tel:'
    ]
    
    # Verificar exclusiones
    for termino in excluir:
        if termino in texto_lower or termino in url_lower:
            return False
    
    # Debe tener texto válido
    if len(texto.strip()) < 3 or len(texto.strip()) > 50:
        return False
    
    # Categorías válidas de supermercado
    categorias_validas = [
        'carne', 'res', 'pollo', 'cerdo', 'pescado', 'mariscos', 'embutidos',
        'leche', 'queso', 'yogurt', 'lácteos', 'huevos',
        'fruta', 'vegetal', 'verdura', 'hortalizas', 'vegetales', 'frutas',
        'pan', 'panadería', 'cereales', 'arroz', 'pasta', 'granos',
        'bebida', 'agua', 'jugo', 'café', 'té', 'vino', 'cerveza', 'licores',
        'limpieza', 'detergente', 'jabón', 'hogar', 'aseo',
        'shampoo', 'cuidado personal', 'higiene', 'pañal',
        'sal', 'azúcar', 'aceite', 'condimento', 'especias', 'salsa',
        'conserva', 'enlatado', 'mermelada', 'congelado', 'helado',
        'mascota', 'gato', 'perro', 'despensa', 'abarrotes', 'snacks', 'dulces'
    ]
    
    # Verificar si contiene términos de supermercado
    for termino in categorias_validas:
        if termino in texto_lower:
            return True
    
    return False

def encontrar_categorias(soup, base_url):
    """Encontrar categorías de productos válidas"""
    categorias = set()
    
    # Buscar enlaces en áreas de navegación
    selectores = [
        '.nav a[href]', '.navigation a[href]', '.menu a[href]',
        'nav a[href]', 'header a[href]', '.header a[href]',
        'ul li a[href]', 'a[href]'
    ]
    
    for selector in selectores:
        try:
            enlaces = soup.select(selector)
            for enlace in enlaces:
                href = enlace.get('href', '').strip()
                texto = enlace.get_text().strip()
                
                if href and href not in ['#', '/', 'javascript:void(0)']:
                    url_completa = urljoin(base_url, href)
                    
                    if es_categoria_valida(url_completa, texto):
                        categorias.add((url_completa, texto))
                        print(f"✓ Categoría encontrada: {texto}")
        except:
            continue
    
    return list(categorias)

def extraer_productos_pagina(soup):
    """Extraer productos de una página"""
    productos = []
    
    # Selectores para encontrar productos
    selectores_productos = [
        '.product-item', '.product', '.item-product', '.producto',
        'div[class*="product"]', 'li[class*="product"]',
        '.grid-item', '.product-card', '.item', '.card',
        'article', '.catalog-item'
    ]
    
    items_encontrados = []
    for selector in selectores_productos:
        try:
            items = soup.select(selector)
            if len(items) > len(items_encontrados):
                items_encontrados = items
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
    """Extraer nombre del producto"""
    selectores_nombre = [
        'a.product-item-link', '.product-name a', '.product-title',
        'h1', 'h2', 'h3', 'h4', '.name', '.title', 'a[title]'
    ]
    
    for selector in selectores_nombre:
        try:
            elemento = item.select_one(selector)
            if elemento:
                texto = elemento.get_text().strip()
                if texto and len(texto) > 2 and len(texto) < 100:
                    return texto
                
                # Intentar atributos
                for attr in ['title', 'alt', 'data-name']:
                    valor = elemento.get(attr, '').strip()
                    if valor and len(valor) > 2:
                        return valor
        except:
            continue
    
    return "Sin nombre"

def extraer_precio_producto(item):
    """Extraer precio del producto"""
    selectores_precio = [
        '.price', '.precio', 'span[class*="price"]', '.cost', '.amount'
    ]
    
    for selector in selectores_precio:
        try:
            elemento = item.select_one(selector)
            if elemento:
                precio_texto = elemento.get_text().strip()
                if precio_texto and ('$' in precio_texto or '₡' in precio_texto or 
                                   re.search(r'\d+[.,]\d+', precio_texto)):
                    return precio_texto
        except:
            continue
    
    # Buscar patrones de precio en todo el texto del item
    texto_completo = item.get_text()
    patrones_precio = [
        r'\$\s*\d+[.,]?\d*', r'₡\s*\d+[.,]?\d*',
        r'\d+[.,]\d+\s*[₡$]', r'\d{1,6}[.,]\d{2}'
    ]
    
    for patron in patrones_precio:
        match = re.search(patron, texto_completo)
        if match:
            return match.group().strip()
    
    return "Sin precio"

def procesar_categoria(url_categoria, nombre_categoria):
    """Procesar todos los productos de una categoría"""
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
    
    # Solo procesar la primera página (sin paginación adicional)
    
    print(f"✓ TOTAL EN '{nombre_categoria}': {len(productos_categoria)} productos")
    return productos_categoria

def main():
    base_url = 'https://supermercadosnacional.com/'
    todos_productos = []
    
    print("🚀 INICIANDO SCRAPING DE SUPERMERCADO NACIONAL")
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
    
    print(f"\n✓ {len(categorias)} categorías encontradas:")
    for i, (url, nombre) in enumerate(categorias, 1):
        print(f"  {i:2d}. {nombre}")
    
    print(f"\nCOMENZANDO EXTRACCIÓN DE PRODUCTOS...")
    
    # Procesar cada categoría
    for i, (url_categoria, nombre_categoria) in enumerate(categorias, 1):
        try:
            print(f"\n[{i}/{len(categorias)}] Procesando: {nombre_categoria}")
            
            productos_categoria = procesar_categoria(url_categoria, nombre_categoria)
            
            if productos_categoria:
                todos_productos.extend(productos_categoria)
                print(f"✓ {len(productos_categoria)} productos agregados")
            
            # No guardar archivos de progreso
            
            time.sleep(1)  # Pausa corta entre categorías
            
        except Exception as e:
            print(f"❌ Error procesando {nombre_categoria}: {e}")
            continue
    
    # Guardar resultados finales
    if todos_productos:
        timestamp = int(time.time())
        archivo_final = f'inventario_nacional_{timestamp}.csv'
        
        with open(archivo_final, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['Nombre', 'Precio', 'Categoria', 'URL_Categoria'])
            writer.writeheader()
            writer.writerows(todos_productos)
        
        print(f'\n🎉 SCRAPING COMPLETADO')
        print(f'✓ {len(todos_productos)} productos guardados en {archivo_final}')
        
        # Resumen por categoría
        resumen = defaultdict(int)
        for producto in todos_productos:
            resumen[producto['Categoria']] += 1
        
        print(f"\n📊 RESUMEN POR CATEGORÍA:")
        for categoria, cantidad in sorted(resumen.items(), key=lambda x: x[1], reverse=True):
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