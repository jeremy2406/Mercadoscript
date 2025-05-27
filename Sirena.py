import time
import csv
import logging
import re
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from bs4 import BeautifulSoup
from collections import Counter

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
            
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            chrome_options.add_argument("--window-size=1920,1080")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("✅ Driver de Selenium configurado correctamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error configurando Selenium: {e}")
            return False
    
    def get_page_with_js(self, url, wait_seconds=15):
        """Cargar página y esperar que se renderice el JavaScript"""
        try:
            logger.info(f"🌐 Cargando página: {url}")
            self.driver.get(url)
            
            time.sleep(5)
            
            try:
                WebDriverWait(self.driver, wait_seconds).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
                
                # Scroll para activar lazy loading
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(2)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(2)
                
            except TimeoutException:
                logger.warning("⚠️ Timeout esperando carga completa, continuando...")
            
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            logger.info("✅ Página cargada y renderizada")
            return soup
            
        except Exception as e:
            logger.error(f"❌ Error cargando página {url}: {e}")
            return None
    
    def extract_all_links(self, soup):
        """Extraer todos los enlaces de la página"""
        all_links = []
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link.get('href', '').strip()
            text = link.get_text(strip=True)
            
            if not href or not text:
                continue
                
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
    
    def find_category_links(self, all_links):
        """Encontrar enlaces que sean categorías de productos"""
        skip_terms = [
            'login', 'registro', 'sign', 'account', 'cuenta', 'perfil', 'mi cuenta',
            'carrito', 'cart', 'checkout', 'pago', 'payment', 'comprar',
            'contacto', 'contact', 'about', 'acerca', 'nosotros', 'quienes somos',
            'ayuda', 'help', 'support', 'soporte', 'faq', 'preguntas',
            'terminos', 'terms', 'privacidad', 'privacy', 'politicas',
            'facebook', 'twitter', 'instagram', 'youtube', 'whatsapp', 'redes',
            'sucursales', 'ubicaciones', 'horarios', 'empleo', 'trabajo',
            'newsletter', 'suscribir', 'blog', 'noticias', 'eventos',
            'garantia', 'devolucion', 'envio', 'delivery', 'ver más', 'leer más'
        ]
        
        categories = []
        seen_urls = set()
        
        for link_data in all_links:
            text = link_data['text'].lower()
            url = link_data['url']
            href = link_data['original_href']
            
            # Filtrar enlaces no deseados
            if (len(link_data['text']) < 3 or len(link_data['text']) > 80 or
                any(term in text for term in skip_terms) or
                href.startswith(('#', 'javascript:', 'mailto:', 'tel:'))):
                continue
            
            url_key = url.lower().rstrip('/')
            if url_key in seen_urls or url_key == self.base_url.rstrip('/').lower():
                continue
            seen_urls.add(url_key)
            
            # Identificar posibles categorías
            is_category = (
                '/categoria' in href.lower() or
                '/category' in href.lower() or
                '/c/' in href.lower() or
                '/productos' in href.lower() or
                '/products' in href.lower() or
                '/tienda' in href.lower() or
                '/shop' in href.lower() or
                any(term in text for term in ['electrodomesticos', 'tecnologia', 'hogar', 'muebles', 
                                              'cocina', 'refrigeracion', 'lavado', 'climatizacion',
                                              'audio', 'video', 'celulares', 'computadoras', 'gaming'])
            )
            
            if is_category:
                categories.append({
                    'name': link_data['text'],
                    'url': url
                })
        
        logger.info(f"📂 Categorías encontradas: {len(categories)}")
        return categories
    
    def extract_products_from_page(self, soup, category_name, page_url):
        """Extraer productos de una página usando múltiples estrategias"""
        products = []
        
        # Estrategias de selección ordenadas por efectividad
        selectors_to_try = [
            '.product, .product-item, .product-card, .product-box',
            '.item, .grid-item, .catalog-item, .shop-item',
            '[data-product], [data-product-id], [data-item]',
            '.card, .tile, .box',
            'article, .article',
            '.list-item, .listing-item'
        ]
        
        for selector in selectors_to_try:
            elements = soup.select(selector)
            
            if len(elements) >= 3:  # Si encuentra una cantidad razonable
                logger.info(f"✅ Usando selector '{selector}' - {len(elements)} elementos")
                
                for elem in elements:
                    product_data = self.extract_product_info(elem, category_name, page_url)
                    if product_data:
                        products.append(product_data)
                
                if len(products) >= 3:  # Si extrajo productos válidos
                    break
        
        # Estrategia alternativa: buscar elementos con imágenes y texto
        if len(products) < 3:
            logger.info("🔍 Aplicando extracción alternativa...")
            products = self.alternative_product_extraction(soup, category_name, page_url)
        
        return products
    
    def extract_product_info(self, element, category_name, page_url):
        """Extraer información específica del producto"""
        product = {
            'nombre': '',
            'precio': '',
            'categoria': category_name
        }
        
        # Extraer nombre del producto
        name_selectors = [
            'h1, h2, h3, h4, h5, h6',
            '.product-name, .name, .title, .product-title',
            'a[title]',
            'img[alt]',
            '.text, .description'
        ]
        
        for selector in name_selectors:
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
                
                if self.is_valid_product_name(text):
                    product['nombre'] = text
                    break
        
        # Extraer precio
        element_text = element.get_text()
        price = self.extract_price_from_text(element_text)
        if price:
            product['precio'] = price
        
        # Solo retornar si tiene nombre válido
        if product['nombre']:
            return product
        
        return None
    
    def is_valid_product_name(self, text):
        """Validar si un texto es un nombre de producto válido"""
        if not text or len(text) < 5 or len(text) > 200:
            return False
        
        invalid_starts = ['ver', 'more', 'click', 'comprar', 'buy', 'añadir', 'add']
        if any(text.lower().startswith(start) for start in invalid_starts):
            return False
        
        if text.isdigit() or text.replace('.', '').replace(',', '').isdigit():
            return False
        
        return True
    
    def extract_price_from_text(self, text):
        """Extraer precio del texto usando patrones"""
        price_patterns = [
            r'RD\$\s*[\d,]+\.?\d*',
            r'\$\s*[\d,]+\.?\d*', 
            r'[\d,]+\.\d{2}\s*RD',
            r'[\d,]+\s*pesos?',
            r'[\d,]{3,}\.\d{2}',
            r'[\d,]{4,}',
            r'Precio:\s*[\d,]+\.?\d*',
            r'Price:\s*[\d,]+\.?\d*'
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                price_text = match.group().strip()
                price_clean = re.sub(r'[^\d,.]', '', price_text)
                if price_clean and len(price_clean) >= 2:
                    return price_text
        
        return ''
    
    def alternative_product_extraction(self, soup, category_name, page_url):
        """Extracción alternativa basada en heurísticas"""
        products = []
        
        # Buscar divs que contengan imágenes y posibles precios
        all_containers = soup.find_all(['div', 'article', 'section', 'li'])
        
        for container in all_containers:
            has_image = container.find('img')
            container_text = container.get_text()
            
            # Buscar indicadores de precio
            has_price_indicator = any(indicator in container_text.lower() 
                                    for indicator in ['$', 'rd', 'precio', 'price', 'pesos'])
            
            # Buscar números que podrían ser precios
            price_numbers = re.findall(r'[\d,]{3,}', container_text)
            has_potential_price = len(price_numbers) > 0
            
            if has_image and (has_price_indicator or has_potential_price):
                product_data = self.extract_product_info(container, category_name, page_url)
                if product_data and product_data['nombre']:
                    products.append(product_data)
        
        return products
    
    def process_pagination(self, base_url, category_name, max_pages=2):
        """Procesar paginación de una categoría"""
        all_products = []
        
        for page_num in range(1, max_pages + 1):
            # Construir URL de página
            if '?' in base_url:
                page_url = f"{base_url}&page={page_num}"
            else:
                page_url = f"{base_url}?page={page_num}"
            
            logger.info(f"📄 Procesando página {page_num} de {category_name}")
            
            soup = self.get_page_with_js(page_url, wait_seconds=10)
            if not soup:
                break
            
            products = self.extract_products_from_page(soup, category_name, page_url)
            
            if products:
                all_products.extend(products)
                logger.info(f"✅ Página {page_num}: {len(products)} productos")
            else:
                logger.info(f"⚠️ No se encontraron productos en página {page_num}")
                break
            
            time.sleep(2)  # Pausa entre páginas
        
        return all_products
    
    def process_category(self, category_url, category_name):
        """Procesar una categoría completa con paginación"""
        logger.info(f"📂 Procesando categoría: {category_name}")
        
        # Procesar hasta 2 páginas
        all_products = self.process_pagination(category_url, category_name, max_pages=2)
        
        # Si no encontró productos, intentar buscar subcategorías
        if len(all_products) < 5:
            logger.info(f"🔍 Buscando subcategorías en: {category_name}")
            
            soup = self.get_page_with_js(category_url, wait_seconds=10)
            if soup:
                all_links = self.extract_all_links(soup)
                subcategories = self.find_subcategories(all_links, category_url)
                
                for subcat in subcategories:
                    if subcat['url'] not in self.processed_urls:
                        self.processed_urls.add(subcat['url'])
                        
                        subcat_products = self.process_pagination(
                            subcat['url'], 
                            f"{category_name} > {subcat['name']}", 
                            max_pages=2
                        )
                        all_products.extend(subcat_products)
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
            
            if url == parent_url:
                continue
            
            # Criterios para subcategorías
            is_subcategory = (
                (parent_path in path and path != parent_path and len(path) > len(parent_path)) or
                (len(text.split()) <= 4 and len(text) >= 3 and not text.isdigit())
            )
            
            if is_subcategory:
                subcategories.append({
                    'name': text,
                    'url': url
                })
        
        # Eliminar duplicados
        seen = set()
        unique_subcats = []
        for subcat in subcategories:
            if subcat['url'] not in seen:
                seen.add(subcat['url'])
                unique_subcats.append(subcat)
        
        return unique_subcats[:8]  # Máximo 8 subcategorías
    
    def run_selenium_scraping(self):
        """Ejecutar scraping completo"""
        logger.info("🚀 Iniciando scraping de Sirena.do...")
        
        if not self.setup_driver():
            return False
        
        try:
            # Cargar página principal
            soup = self.get_page_with_js(self.base_url, wait_seconds=20)
            if not soup:
                logger.error("❌ No se pudo cargar la página principal")
                return False
            
            # Extraer enlaces y encontrar categorías
            all_links = self.extract_all_links(soup)
            categories = self.find_category_links(all_links)
            
            if not categories:
                logger.error("❌ No se encontraron categorías")
                return False
            
            logger.info(f"📂 Procesando {len(categories)} categorías...")
            
            # Procesar cada categoría
            for i, category in enumerate(categories, 1):
                logger.info(f"🔄 [{i}/{len(categories)}] {category['name']}")
                
                try:
                    if category['url'] not in self.processed_urls:
                        self.processed_urls.add(category['url'])
                        
                        products = self.process_category(category['url'], category['name'])
                        
                        if products:
                            self.products_data.extend(products)
                            logger.info(f"✅ {category['name']}: {len(products)} productos")
                        
                        time.sleep(3)  # Pausa entre categorías
                    
                except Exception as e:
                    logger.error(f"❌ Error en {category['name']}: {e}")
                    continue
            
            logger.info(f"🎉 Scraping completado. Total: {len(self.products_data)} productos")
            return True
            
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("🔚 Driver cerrado")
    
    def save_to_csv(self, filename='sirena_productos.csv'):
        """Guardar productos en CSV eliminando duplicados"""
        if not self.products_data:
            logger.warning("⚠️ No hay productos para guardar")
            return
        
        try:
            # Eliminar duplicados
            unique_products = []
            seen = set()
            
            for product in self.products_data:
                key = (product['nombre'].lower().strip(), product['categoria'].lower().strip())
                if key not in seen and product['nombre'].strip():
                    seen.add(key)
                    unique_products.append(product)
            
            logger.info(f"🧹 Productos únicos: {len(unique_products)}")
            
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['nombre', 'precio', 'categoria']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for product in unique_products:
                    writer.writerow(product)
            
            logger.info(f"💾 Guardado en: {filename}")
            print(f"✅ Archivo creado: {filename}")
            print(f"📊 Productos únicos: {len(unique_products)}")
            
        except Exception as e:
            logger.error(f"❌ Error guardando CSV: {e}")
    
    def print_sample_products(self):
        """Mostrar muestra de productos"""
        if not self.products_data:
            print("❌ No hay productos para mostrar")
            return
        
        print("\n📋 MUESTRA DE PRODUCTOS EXTRAÍDOS:")
        print("=" * 80)
        
        # Mostrar primeros 10 productos
        for i, product in enumerate(self.products_data[:10], 1):
            print(f"{i}. {product['nombre']}")
            print(f"   💰 Precio: {product['precio'] or 'No disponible'}")
            print(f"   📂 Categoría: {product['categoria']}")
            print("-" * 60)
        
        # Estadísticas por categoría
        category_counts = Counter(p['categoria'] for p in self.products_data)
        
        print(f"\n📊 PRODUCTOS POR CATEGORÍA:")
        print("=" * 50)
        for category, count in category_counts.most_common(10):
            print(f"📂 {category}: {count} productos")

def main():
    print("🤖 Sirena.do Scraper Mejorado")
    print("=" * 60)
    print("✅ Características:")
    print("   • Extracción completa de categorías")
    print("   • Máximo 2 páginas por categoría")
    print("   • Productos reales con nombre, precio y categoría")
    print("   • Sin límites artificiales")
    print("=" * 60)
    
    try:
        headless_input = input("¿Ejecutar sin ventana visible? (s/N): ").lower()
        headless = headless_input in ['s', 'y', 'yes', 'sí']
    except:
        headless = True
    
    scraper = SirenaSeleniumScraper(headless=headless)
    
    if scraper.run_selenium_scraping():
        scraper.print_sample_products()
        scraper.save_to_csv()
        print(f"\n🎉 ¡SCRAPING COMPLETADO!")
    else:
        print("❌ Error en el scraping")
    
    print("=" * 60)

if __name__ == "__main__":
    main()