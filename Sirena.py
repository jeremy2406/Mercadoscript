import time
import csv
import logging
import re
from urllib.parse import urljoin, urlparse
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from bs4 import BeautifulSoup

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SirenaSeleniumScraper:
    def __init__(self, headless=True):
        self.base_url = "https://www.sirena.do/"
        self.driver = None
        self.products_data = []
        self.headless = headless
        self.processed_urls = set()
        
    def setup_driver(self):
        """Configurar el driver de Selenium"""
        try:
            chrome_options = Options()
            
            if self.headless:
                chrome_options.add_argument("--headless")
            
            # Opciones para mejor compatibilidad
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # User agent realista
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # Configurar ventana
            chrome_options.add_argument("--window-size=1920,1080")
            
            # Crear driver
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("✅ Driver de Selenium configurado correctamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error configurando Selenium: {e}")
            logger.error("💡 Asegúrate de tener ChromeDriver instalado")
            logger.error("💡 Instala con: pip install selenium")
            logger.error("💡 Descarga ChromeDriver desde: https://chromedriver.chromium.org/")
            return False
    
    def get_page_with_js(self, url, wait_seconds=15):
        """Cargar página y esperar que se renderice el JavaScript"""
        try:
            logger.info(f"🌐 Cargando página: {url}")
            self.driver.get(url)
            
            # Esperar que la página cargue completamente
            time.sleep(5)
            
            # Intentar detectar cuando el contenido se ha cargado
            try:
                WebDriverWait(self.driver, wait_seconds).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
                
                # Esperar más tiempo para contenido dinámico
                time.sleep(3)
                
                # Hacer scroll para activar lazy loading
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
                time.sleep(2)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(2)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(2)
                
            except TimeoutException:
                logger.warning("⚠️ Timeout esperando carga completa, continuando...")
            
            # Obtener el HTML renderizado final
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            logger.info("✅ Página cargada y renderizada completamente")
            return soup
            
        except Exception as e:
            logger.error(f"❌ Error cargando página {url}: {e}")
            return None
    
    def extract_all_links(self, soup):
        """Extraer todos los enlaces posibles de la página"""
        all_links = []
        
        # Encontrar TODOS los enlaces
        links = soup.find_all('a', href=True)
        logger.info(f"🔗 Total enlaces encontrados en la página: {len(links)}")
        
        for link in links:
            href = link.get('href', '').strip()
            text = link.get_text(strip=True)
            
            if not href or not text:
                continue
                
            # Crear URL completa
            if href.startswith('/'):
                full_url = urljoin(self.base_url, href)
            elif href.startswith('http'):
                full_url = href
            else:
                full_url = urljoin(self.base_url, href)
            
            all_links.append({
                'text': text,
                'url': full_url,
                'original_href': href
            })
        
        return all_links
    
    def categorize_links(self, all_links):
        """Categorizar enlaces en categorías principales y subcategorías"""
        # Términos que NO son categorías
        skip_terms = [
            'login', 'registro', 'sign', 'account', 'cuenta', 'perfil', 'mi cuenta',
            'carrito', 'cart', 'checkout', 'pago', 'payment', 'comprar',
            'contacto', 'contact', 'about', 'acerca', 'nosotros', 'quienes somos',
            'ayuda', 'help', 'support', 'soporte', 'faq', 'preguntas',
            'terminos', 'terms', 'privacidad', 'privacy', 'politicas',
            'facebook', 'twitter', 'instagram', 'youtube', 'whatsapp', 'redes',
            'sucursales', 'ubicaciones', 'horarios', 'empleo', 'trabajo',
            'newsletter', 'suscribir', 'blog', 'noticias', 'eventos',
            'garantia', 'devolucion', 'envio', 'delivery'
        ]
        
        # Indicadores de categorías de productos
        category_indicators = [
            'categoria', 'category', 'departamento', 'seccion', 'linea',
            'productos', 'products', 'tienda', 'shop', 'store',
            'electrodomesticos', 'tecnologia', 'hogar', 'muebles',
            'cocina', 'refrigeracion', 'lavado', 'climatizacion',
            'audio', 'video', 'celulares', 'computadoras', 'gaming'
        ]
        
        categories = []
        seen_urls = set()
        
        for link_data in all_links:
            text = link_data['text'].lower()
            url = link_data['url']
            href = link_data['original_href']
            
            # Skip enlaces vacíos o muy cortos
            if len(link_data['text']) < 2 or len(link_data['text']) > 100:
                continue
            
            # Skip términos no deseados
            if any(term in text for term in skip_terms):
                continue
            
            # Skip enlaces de JavaScript, email, teléfono, anclas
            if (href.startswith('#') or 
                href.startswith('javascript:') or 
                href.startswith('mailto:') or 
                href.startswith('tel:')):
                continue
            
            # Evitar duplicados
            url_key = url.lower().rstrip('/')
            if url_key in seen_urls or url_key == self.base_url.rstrip('/').lower():
                continue
            seen_urls.add(url_key)
            
            # Determinar si es una categoría potencial
            is_category = (
                any(indicator in text for indicator in category_indicators) or
                any(indicator in href.lower() for indicator in category_indicators) or
                (len(link_data['text'].split()) <= 3 and len(link_data['text']) >= 3)
            )
            
            # Si parece una categoría o si tiene estructura de URL de categoría
            if (is_category or 
                '/categoria' in href.lower() or 
                '/category' in href.lower() or
                '/c/' in href.lower() or
                '/productos' in href.lower() or
                '/products' in href.lower()):
                
                categories.append({
                    'name': link_data['text'],
                    'url': url,
                    'priority': 1 if is_category else 2
                })
        
        # Ordenar por prioridad y nombre
        categories.sort(key=lambda x: (x['priority'], len(x['name'])))
        
        logger.info(f"📂 Categorías potenciales encontradas: {len(categories)}")
        return categories
    
    def extract_products_from_page(self, soup, category_name, page_url):
        """Extraer productos de una página específica"""
        products = []
        
        # Múltiples estrategias de selección de productos
        product_strategies = [
            # Estrategia 1: Selectores específicos de productos
            {
                'selectors': ['.product', '.product-item', '.product-card', '.product-box'],
                'name': 'Selectores específicos de productos'
            },
            # Estrategia 2: Selectores de elementos de grilla/catálogo
            {
                'selectors': ['.item', '.grid-item', '.catalog-item', '.shop-item'],
                'name': 'Selectores de grilla/catálogo'
            },
            # Estrategia 3: Selectores por atributos data
            {
                'selectors': ['[data-product]', '[data-product-id]', '[data-item]'],
                'name': 'Selectores con atributos data'
            },
            # Estrategia 4: Selectores de tarjetas
            {
                'selectors': ['.card', '.tile', '.box'],
                'name': 'Selectores de tarjetas genéricas'
            }
        ]
        
        found_products = False
        
        for strategy in product_strategies:
            if found_products:
                break
                
            logger.info(f"🔍 Probando estrategia: {strategy['name']}")
            
            for selector in strategy['selectors']:
                elements = soup.select(selector)
                
                # Solo procesar si encuentra una cantidad razonable de elementos
                if len(elements) >= 3:
                    logger.info(f"✅ Encontrados {len(elements)} elementos con '{selector}'")
                    
                    products_from_selector = []
                    for elem in elements[:50]:  # Limitar a 50 por selector
                        product_data = self.extract_product_info_enhanced(elem, category_name, page_url)
                        if product_data:
                            products_from_selector.append(product_data)
                    
                    if len(products_from_selector) >= 3:  # Si encontró productos válidos
                        products.extend(products_from_selector)
                        found_products = True
                        logger.info(f"✅ Extraídos {len(products_from_selector)} productos válidos")
                        break
        
        # Estrategia 5: Análisis heurístico si no encuentra productos
        if not found_products:
            logger.info("🔍 Aplicando análisis heurístico...")
            products = self.heuristic_product_extraction(soup, category_name, page_url)
        
        return products
    
    def extract_product_info_enhanced(self, element, category_name, page_url):
        """Extraer información mejorada de un producto"""
        product = {
            'nombre': '',
            'precio': '',
            'categoria': category_name,
            'url_categoria': page_url
        }
        
        # Extraer nombre del producto - múltiples estrategias
        name_strategies = [
            ('h1, h2, h3, h4, h5', 'títulos'),
            ('.product-name, .name, .title, .product-title', 'clases específicas'),
            ('a[title]', 'títulos de enlaces'),
            ('img[alt]', 'texto alternativo de imágenes'),
            ('.text, .description', 'texto descriptivo')
        ]
        
        for selector, description in name_strategies:
            if product['nombre']:
                break
                
            elements = element.select(selector)
            for elem in elements:
                if elem.name == 'img':
                    text = elem.get('alt', '').strip()
                elif elem.name == 'a':
                    text = elem.get('title', '').strip() or elem.get_text(strip=True)
                else:
                    text = elem.get_text(strip=True)
                
                # Validar que el texto sea un nombre de producto válido
                if (text and 
                    5 <= len(text) <= 200 and 
                    not text.lower().startswith(('ver', 'more', 'click', 'comprar', 'buy')) and
                    not text.isdigit()):
                    product['nombre'] = text
                    break
        
        # Extraer precio - patrones expandidos
        element_text = element.get_text()
        price_patterns = [
            r'RD\$\s*[\d,]+\.?\d*',           # RD$1,000.00
            r'\$\s*[\d,]+\.?\d*',             # $1,000.00
            r'[\d,]+\.\d{2}\s*RD',            # 1,000.00 RD
            r'[\d,]+\s*pesos?',               # 1000 pesos
            r'[\d,]{3,}\.\d{2}',              # 1,000.00
            r'[\d,]{4,}',                     # 10,000
            r'Precio:\s*[\d,]+\.?\d*',        # Precio: 1000
            r'Price:\s*[\d,]+\.?\d*'          # Price: 1000
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, element_text, re.IGNORECASE)
            if match:
                price_text = match.group().strip()
                # Limpiar el precio
                price_clean = re.sub(r'[^\d,.]', '', price_text)
                if price_clean and len(price_clean) >= 2:
                    product['precio'] = price_text
                    break
        
        # Solo retornar si tiene al menos nombre
        if product['nombre']:
            return product
        
        return None
    
    def heuristic_product_extraction(self, soup, category_name, page_url):
        """Extracción heurística de productos"""
        logger.info("🧠 Aplicando extracción heurística...")
        
        products = []
        
        # Buscar elementos que contengan tanto imágenes como texto con precios
        all_divs = soup.find_all(['div', 'article', 'section'])
        
        potential_products = []
        
        for div in all_divs:
            # Criterios para identificar un producto:
            has_image = div.find('img')
            div_text = div.get_text()
            
            # Buscar indicadores de precio en el texto
            price_indicators = ['$', 'RD', 'precio', 'price', 'pesos']
            has_price = any(indicator in div_text for indicator in price_indicators)
            
            # Buscar patrones de precio más específicos
            price_pattern = re.search(r'[\d,]+\.?\d*', div_text)
            has_number = price_pattern and len(price_pattern.group()) >= 3
            
            # Si tiene imagen Y (precio O número grande), podría ser un producto
            if has_image and (has_price or has_number):
                potential_products.append(div)
        
        logger.info(f"🔍 Elementos potencialmente productos: {len(potential_products)}")
        
        # Extraer información de elementos potenciales
        for elem in potential_products[:30]:  # Limitar para evitar ruido
            product_data = self.extract_product_info_enhanced(elem, category_name, page_url)
            if product_data and product_data['nombre']:
                products.append(product_data)
        
        logger.info(f"🧠 Productos extraídos heurísticamente: {len(products)}")
        return products
    
    def process_category_deep(self, category_url, category_name, max_depth=2, current_depth=0):
        """Procesar una categoría en profundidad buscando subcategorías"""
        if current_depth >= max_depth:
            return []
        
        logger.info(f"{'  ' * current_depth}📂 Procesando: {category_name} (profundidad {current_depth})")
        
        soup = self.get_page_with_js(category_url, wait_seconds=12)
        if not soup:
            return []
        
        all_products = []
        
        # Primero, extraer productos de esta página
        products = self.extract_products_from_page(soup, category_name, category_url)
        if products:
            logger.info(f"{'  ' * current_depth}✅ Productos encontrados: {len(products)}")
            all_products.extend(products)
        
        # Si no encontró suficientes productos, buscar subcategorías
        if len(products) < 5 and current_depth < max_depth - 1:
            logger.info(f"{'  ' * current_depth}🔍 Buscando subcategorías...")
            
            all_links = self.extract_all_links(soup)
            subcategories = self.find_subcategories(all_links, category_url)
            
            if subcategories:
                logger.info(f"{'  ' * current_depth}📁 Subcategorías encontradas: {len(subcategories)}")
                
                for subcat in subcategories[:5]:  # Limitar subcategorías
                    if subcat['url'] not in self.processed_urls:
                        self.processed_urls.add(subcat['url'])
                        
                        subcat_products = self.process_category_deep(
                            subcat['url'], 
                            f"{category_name} > {subcat['name']}", 
                            max_depth, 
                            current_depth + 1
                        )
                        all_products.extend(subcat_products)
                        
                        # Pausa entre subcategorías
                        time.sleep(2)
        
        return all_products
    
    def find_subcategories(self, all_links, parent_url):
        """Encontrar subcategorías dentro de una categoría"""
        subcategories = []
        parent_path = urlparse(parent_url).path
        
        for link_data in all_links:
            url = link_data['url']
            text = link_data['text']
            path = urlparse(url).path
            
            # Skip si es el mismo enlace padre
            if url == parent_url:
                continue
            
            # Buscar enlaces que parezcan subcategorías
            # (que estén dentro del path padre o que sean categorías relacionadas)
            is_subcategory = (
                (parent_path in path and path != parent_path) or
                any(term in text.lower() for term in ['subcategoria', 'ver todo', 'mas', 'todos']) or
                (len(text.split()) <= 4 and len(text) >= 3 and not text.isdigit())
            )
            
            if is_subcategory and len(text) >= 3:
                subcategories.append({
                    'name': text,
                    'url': url
                })
        
        # Eliminar duplicados y limitar
        seen = set()
        unique_subcats = []
        for subcat in subcategories:
            if subcat['url'] not in seen:
                seen.add(subcat['url'])
                unique_subcats.append(subcat)
        
        return unique_subcats[:10]  # Máximo 10 subcategorías por categoría
    
    def run_selenium_scraping(self):
        """Ejecutar scraping completo optimizado"""
        logger.info("🚀 Iniciando scraping optimizado con Selenium...")
        
        if not self.setup_driver():
            return False
        
        try:
            # Cargar página principal
            soup = self.get_page_with_js(self.base_url, wait_seconds=20)
            if not soup:
                logger.error("❌ No se pudo cargar la página principal")
                return False
            
            # Extraer todos los enlaces
            all_links = self.extract_all_links(soup)
            
            # Categorizar enlaces
            categories = self.categorize_links(all_links)
            
            if not categories:
                logger.error("❌ No se encontraron categorías")
                return False
            
            logger.info(f"📂 Procesando {len(categories)} categorías...")
            
            # Procesar cada categoría en profundidad
            for i, category in enumerate(categories[:15], 1):  # Limitar a 15 categorías principales
                logger.info(f"🔄 [{i}/{min(15, len(categories))}] Procesando: {category['name']}")
                
                try:
                    if category['url'] not in self.processed_urls:
                        self.processed_urls.add(category['url'])
                        
                        products = self.process_category_deep(
                            category['url'], 
                            category['name'], 
                            max_depth=2
                        )
                        
                        if products:
                            self.products_data.extend(products)
                            logger.info(f"✅ Total productos de '{category['name']}': {len(products)}")
                        else:
                            logger.warning(f"⚠️ No se encontraron productos en: {category['name']}")
                        
                        # Pausa entre categorías principales
                        time.sleep(3)
                    
                except Exception as e:
                    logger.error(f"❌ Error procesando {category['name']}: {e}")
                    continue
            
            logger.info(f"🎉 Scraping completado. Total productos: {len(self.products_data)}")
            return True
            
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("🔚 Driver de Selenium cerrado")
    
    def save_to_csv(self, filename='sirena_productos_optimizado.csv'):
        """Guardar productos en CSV"""
        if not self.products_data:
            logger.warning("⚠️ No hay productos para guardar")
            return
        
        try:
            # Eliminar duplicados basados en nombre y categoría
            unique_products = []
            seen = set()
            
            for product in self.products_data:
                key = (product['nombre'].lower(), product['categoria'].lower())
                if key not in seen:
                    seen.add(key)
                    unique_products.append(product)
            
            logger.info(f"🧹 Productos únicos después de limpiar duplicados: {len(unique_products)}")
            
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['nombre', 'precio', 'categoria', 'url_categoria']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for product in unique_products:
                    writer.writerow(product)
            
            logger.info(f"💾 Productos guardados en: {filename}")
            print(f"✅ Archivo creado: {filename}")
            print(f"📊 Total productos únicos: {len(unique_products)}")
            
        except Exception as e:
            logger.error(f"❌ Error guardando CSV: {e}")
    
    def print_sample_products(self):
        """Mostrar muestra de productos"""
        if not self.products_data:
            print("❌ No hay productos para mostrar")
            return
        
        print("\n📋 MUESTRA DE PRODUCTOS EXTRAÍDOS:")
        print("=" * 80)
        
        # Mostrar productos de diferentes categorías
        categories_shown = set()
        products_shown = 0
        
        for product in self.products_data:
            if products_shown >= 10:
                break
                
            category = product['categoria']
            
            # Mostrar máximo 3 productos por categoría en la muestra
            if categories_shown.count(category) < 3:
                categories_shown.add(category)
                products_shown += 1
                
                print(f"{products_shown}. PRODUCTO: {product['nombre']}")
                print(f"   💰 PRECIO: {product['precio'] or 'No disponible'}")
                print(f"   📂 CATEGORÍA: {product['categoria']}")
                print("-" * 60)
        
        # Estadísticas por categoría
        from collections import Counter
        category_counts = Counter(p['categoria'] for p in self.products_data)
        
        print(f"\n📊 PRODUCTOS POR CATEGORÍA:")
        print("=" * 50)
        for category, count in category_counts.most_common(10):
            print(f"📂 {category}: {count} productos")

def main():
    print("🤖 Sirena.do Scraper OPTIMIZADO con Selenium")
    print("=" * 60)
    print("🔥 CARACTERÍSTICAS:")
    print("   ✅ Extracción profunda de categorías y subcategorías")
    print("   ✅ Múltiples estrategias de detección de productos")
    print("   ✅ Análisis heurístico inteligente")
    print("   ✅ Eliminación de duplicados")
    print("   ✅ Solo extrae: NOMBRE, PRECIO, CATEGORÍA")
    print("=" * 60)
    print("⚙️  Requiere: pip install selenium beautifulsoup4")
    print("🔧 Requiere: ChromeDriver instalado")
    print("=" * 60)
    
    # Preguntar configuración
    try:
        headless_input = input("¿Ejecutar en modo headless (sin ventana)? (s/N): ").lower()
        headless = headless_input in ['s', 'y', 'yes', 'sí']
        
        print(f"🚀 Iniciando scraper en modo {'headless' if headless else 'visual'}...")
        
    except:
        headless = True
        print("🚀 Iniciando scraper en modo headless...")
    
    scraper = SirenaSeleniumScraper(headless=headless)
    
    if scraper.run_selenium_scraping():
        scraper.print_sample_products()
        scraper.save_to_csv()
        print(f"\n🎉 ¡PROCESO COMPLETADO EXITOSAMENTE!")
        print(f"📁 Revisa el archivo: sirena_productos_optimizado.csv")
    else:
        print("❌ Error en el scraping. Revisa los logs para más detalles.")
    
    print("=" * 60)
    print("✨ FIN DEL PROCESO")

if __name__ == "__main__":
    main()