import time
import csv
import logging
import re
from urllib.parse import urljoin, urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from bs4 import BeautifulSoup
from collections import Counter
import json

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SirenaAdvancedScraper:
    def __init__(self, headless=True):
        self.base_url = "https://www.sirena.do/"
        self.driver = None
        self.products_data = []
        self.headless = headless
        self.processed_urls = set()
        self.found_categories = []
        self.max_pages_per_category = 2  # Máximo 2 páginas por categoría como solicitado
        
    def setup_driver(self):
        """Configurar el driver de Selenium con configuración optimizada"""
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
            chrome_options.add_argument("--disable-images")  # Optimización para velocidad
            chrome_options.add_argument("--disable-javascript-harmony-shipping")
            chrome_options.add_argument("--disable-extensions")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.implicitly_wait(10)
            
            logger.info("✅ Driver de Selenium configurado correctamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error configurando Selenium: {e}")
            return False
    
    def get_page_with_retry(self, url, max_retries=3, wait_seconds=15):
        """Cargar página con reintentos y manejo mejorado de errores"""
        for attempt in range(max_retries):
            try:
                logger.info(f"🌐 Cargando página (intento {attempt + 1}): {url}")
                self.driver.get(url)
                
                # Esperar carga inicial
                time.sleep(5)
                
                # Verificar que la página se cargó correctamente
                try:
                    WebDriverWait(self.driver, wait_seconds).until(
                        lambda driver: driver.execute_script("return document.readyState") == "complete"
                    )
                except TimeoutException:
                    logger.warning(f"⚠️ Timeout en carga completa, continuando...")
                
                # Scroll progresivo para activar lazy loading
                self.progressive_scroll()
                
                # Verificar si hay contenido útil
                html = self.driver.page_source
                if len(html) > 5000:  # Página mínimamente cargada
                    soup = BeautifulSoup(html, 'html.parser')
                    logger.info("✅ Página cargada correctamente")
                    return soup
                else:
                    logger.warning(f"⚠️ Página con poco contenido, reintentando...")
                    time.sleep(3)
                    
            except Exception as e:
                logger.error(f"❌ Error en intento {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                    
        logger.error(f"❌ Falló cargar página después de {max_retries} intentos")
        return None
    
    def progressive_scroll(self):
        """Scroll progresivo para activar lazy loading"""
        try:
            # Obtener altura total
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            current_position = 0
            scroll_step = 300
            
            while current_position < total_height:
                # Scroll gradual
                self.driver.execute_script(f"window.scrollTo(0, {current_position});")
                time.sleep(0.5)
                current_position += scroll_step
                
                # Actualizar altura total (puede cambiar con lazy loading)
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height > total_height:
                    total_height = new_height
            
            # Scroll final al top
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
        except Exception as e:
            logger.warning(f"⚠️ Error en scroll progresivo: {e}")
    
    def find_all_categories_comprehensive(self, soup):
        """Búsqueda exhaustiva de todas las categorías y subcategorías"""
        categories = []
        found_urls = set()
        
        logger.info("🔍 Iniciando búsqueda exhaustiva de categorías...")
        
        # 1. Buscar en menús principales y de navegación
        nav_selectors = [
            'nav', 'header nav', '.navigation', '.nav', '.menu',
            '[class*="nav"]', '[class*="menu"]', '[id*="nav"]', '[id*="menu"]',
            '.header', '.top-menu', '.main-menu', '.primary-nav'
        ]
        
        for selector in nav_selectors:
            try:
                nav_elements = soup.select(selector)
                for nav in nav_elements:
                    self.extract_links_from_element(nav, categories, found_urls, "Navegación")
            except:
                continue
        
        # 2. Buscar en sidebars y menús laterales
        sidebar_selectors = [
            '.sidebar', '.side-nav', '.left-nav', '.category-menu',
            '[class*="sidebar"]', '[class*="category"]', '.filters',
            '.facets', '.refinements'
        ]
        
        for selector in sidebar_selectors:
            try:
                sidebar_elements = soup.select(selector)
                for sidebar in sidebar_elements:
                    self.extract_links_from_element(sidebar, categories, found_urls, "Sidebar")
            except:
                continue
        
        # 3. Buscar en listas de categorías
        list_selectors = [
            'ul li a', 'ol li a', '.category-list a', '.product-categories a',
            '[class*="category"] a', '[class*="department"] a'
        ]
        
        for selector in list_selectors:
            try:
                links = soup.select(selector)
                for link in links:
                    self.process_category_link(link, categories, found_urls, "Lista")
            except:
                continue
        
        # 4. Buscar enlaces con texto relacionado a categorías
        all_links = soup.find_all('a', href=True)
        category_keywords = [
            'electrodomésticos', 'electrodomestico', 'electrónicos', 'electronico',
            'hogar', 'cocina', 'refrigeración', 'refrigeracion', 'lavado',
            'climatización', 'climatizacion', 'audio', 'video', 'televisores',
            'televisor', 'tv', 'celulares', 'celular', 'móviles', 'moviles',
            'computadoras', 'computadora', 'laptop', 'tablets', 'tablet',
            'gaming', 'juegos', 'muebles', 'decoración', 'decoracion',
            'jardín', 'jardin', 'herramientas', 'ferretería', 'ferreteria',
            'deportes', 'fitness', 'salud', 'belleza', 'cuidado personal',
            'línea blanca', 'linea blanca', 'pequeños electrodomésticos',
            'neveras', 'refrigeradores', 'lavadoras', 'secadoras', 'estufas',
            'hornos', 'microondas', 'aires acondicionados', 'ventiladores',
            'samsung', 'lg', 'whirlpool', 'mabe', 'frigidaire', 'electrolux'
        ]
        
        for link in all_links:
            text = link.get_text(strip=True).lower()
            href = link.get('href', '')
            
            # Verificar si contiene palabras clave de categorías
            if any(keyword in text for keyword in category_keywords):
                self.process_category_link(link, categories, found_urls, "Keyword Match")
            
            # Verificar si la URL sugiere una categoría
            elif any(keyword in href.lower() for keyword in category_keywords):
                self.process_category_link(link, categories, found_urls, "URL Match")
        
        # 5. Buscar patrones específicos de URLs de categorías
        url_patterns = [
            r'/categoria/', r'/category/', r'/departamento/', r'/department/',
            r'/seccion/', r'/section/', r'/productos/', r'/products/',
            r'/electrodomesticos', r'/electronicos', r'/hogar', r'/cocina'
        ]
        
        for link in all_links:
            href = link.get('href', '')
            if any(re.search(pattern, href, re.IGNORECASE) for pattern in url_patterns):
                self.process_category_link(link, categories, found_urls, "Pattern Match")
        
        # 6. Buscar en breadcrumbs
        breadcrumb_selectors = [
            '.breadcrumb a', '.breadcrumbs a', '[class*="breadcrumb"] a',
            '.nav-path a', '.page-path a'
        ]
        
        for selector in breadcrumb_selectors:
            try:
                breadcrumb_links = soup.select(selector)
                for link in breadcrumb_links:
                    self.process_category_link(link, categories, found_urls, "Breadcrumb")
            except:
                continue
        
        # Eliminar duplicados y filtrar
        unique_categories = self.filter_and_deduplicate_categories(categories)
        
        logger.info(f"✅ Encontradas {len(unique_categories)} categorías únicas")
        return unique_categories
    
    def extract_links_from_element(self, element, categories, found_urls, source):
        """Extraer enlaces de un elemento específico"""
        links = element.find_all('a', href=True)
        for link in links:
            self.process_category_link(link, categories, found_urls, source)
    
    def process_category_link(self, link, categories, found_urls, source):
        """Procesar un enlace potencial de categoría"""
        try:
            text = link.get_text(strip=True)
            href = link.get('href', '')
            
            if not text or not href or len(text) > 100:
                return
            
            # Construir URL completa
            if href.startswith('/'):
                full_url = urljoin(self.base_url, href)
            elif href.startswith('http'):
                full_url = href
            else:
                full_url = urljoin(self.driver.current_url, href)
            
            # Filtrar URLs no válidas
            if not self.is_valid_category_url(full_url, text):
                return
            
            if full_url not in found_urls:
                found_urls.add(full_url)
                categories.append({
                    'name': text,
                    'url': full_url,
                    'source': source
                })
                
        except Exception as e:
            logger.debug(f"Error procesando enlace: {e}")
    
    def is_valid_category_url(self, url, text):
        """Validar si una URL y texto corresponden a una categoría válida"""
        # Verificar dominio
        if not url.startswith(self.base_url):
            return False
        
        # Excluir URLs no deseadas
        excluded_patterns = [
            'javascript:', 'mailto:', 'tel:', '#',
            '/account', '/login', '/register', '/cart', '/checkout',
            '/contact', '/about', '/help', '/support', '/terms',
            '/privacy', '/return', '/shipping', '/faq'
        ]
        
        if any(pattern in url.lower() for pattern in excluded_patterns):
            return False
        
        # Excluir textos no deseados
        excluded_texts = [
            'inicio', 'home', 'contacto', 'ayuda', 'cuenta', 'carrito',
            'login', 'registrar', 'buscar', 'search', 'ver todo', 'más'
        ]
        
        if text.lower() in excluded_texts:
            return False
        
        # Debe tener longitud razonable
        if len(text) < 3 or len(text) > 80:
            return False
        
        return True
    
    def filter_and_deduplicate_categories(self, categories):
        """Filtrar y eliminar duplicados de categorías"""
        unique_categories = []
        seen_urls = set()
        seen_names = set()
        
        # Priorizar por fuente
        priority_sources = ['Navegación', 'Sidebar', 'Lista', 'Keyword Match', 'URL Match', 'Pattern Match', 'Breadcrumb']
        
        # Ordenar por prioridad
        categories.sort(key=lambda x: priority_sources.index(x['source']) if x['source'] in priority_sources else 999)
        
        for category in categories:
            url_key = category['url']
            name_key = category['name'].lower().strip()
            
            if url_key not in seen_urls and name_key not in seen_names:
                seen_urls.add(url_key)
                seen_names.add(name_key)
                unique_categories.append(category)
        
        return unique_categories
    
    def find_pagination_links(self, soup, current_url):
        """Encontrar enlaces de paginación"""
        pagination_links = []
        
        # Selectores comunes para paginación
        pagination_selectors = [
            '.pagination a', '.pager a', '.page-numbers a',
            '[class*="pagination"] a', '[class*="pager"] a',
            '.next', '.siguiente', '[rel="next"]'
        ]
        
        for selector in pagination_selectors:
            try:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href')
                    if href:
                        full_url = urljoin(current_url, href)
                        if full_url != current_url and full_url not in pagination_links:
                            pagination_links.append(full_url)
            except:
                continue
        
        # También buscar enlaces con números de página
        page_number_pattern = r'\b[2-9]\b|\b1[0-9]\b'  # Páginas 2-19
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            text = link.get_text(strip=True)
            if re.match(page_number_pattern, text):
                href = link.get('href')
                if href:
                    full_url = urljoin(current_url, href)
                    if full_url != current_url and full_url not in pagination_links:
                        pagination_links.append(full_url)
        
        return pagination_links[:self.max_pages_per_category - 1]  # -1 porque ya tenemos la página actual
    
    def extract_products_advanced(self, soup, category_name, page_url):
        """Extracción avanzada de productos"""
        products = []
        
        logger.info(f"🔍 Extrayendo productos de: {category_name}")
        
        # Selectores mejorados para productos
        product_selectors = [
            # Selectores específicos de e-commerce
            '.product', '.product-item', '.item', '.product-card',
            '[data-product]', '[data-item]', '[class*="product"]',
            '.card', '.tile', '.box', '[class*="item"]',
            # Selectores de listas
            'li[class*="product"]', 'article', '.listing-item',
            # Grid patterns
            '.grid-item', '.col', '[class*="col-"]'
        ]
        
        potential_products = []
        
        for selector in product_selectors:
            try:
                elements = soup.select(selector)
                potential_products.extend(elements)
            except:
                continue
        
        # También buscar divs que contengan productos
        all_divs = soup.find_all('div')
        for div in all_divs:
            if self.looks_like_product_container(div):
                potential_products.append(div)
        
        logger.info(f"📦 Analizando {len(potential_products)} contenedores potenciales...")
        
        # Procesar cada contenedor potencial
        for container in potential_products:
            try:
                product_data = self.extract_product_data(container, category_name)
                if product_data:
                    products.append(product_data)
            except Exception as e:
                logger.debug(f"Error extrayendo producto: {e}")
                continue
        
        # Eliminar duplicados
        unique_products = self.remove_duplicate_products(products)
        
        logger.info(f"✅ Productos únicos extraídos: {len(unique_products)}")
        return unique_products
    
    def looks_like_product_container(self, element):
        """Determinar si un elemento parece contener un producto"""
        try:
            text = element.get_text().lower()
            html = str(element).lower()
            
            # Debe tener imagen o precio
            has_image = element.find('img') is not None
            has_price = bool(re.search(r'(?:rd\$|precio|\$)\s*[\d,]+', text))
            
            # Debe tener texto suficiente pero no demasiado
            text_length = len(text.strip())
            
            # Indicadores positivos
            positive_indicators = [
                has_image and text_length > 10,
                has_price,
                any(brand in text for brand in [
                    'samsung', 'lg', 'whirlpool', 'mabe', 'frigidaire'
                ]),
                any(term in html for term in [
                    'product', 'item', 'card'
                ])
            ]
            
            # Indicadores negativos
            negative_indicators = [
                text_length < 5 or text_length > 1000,
                'navigation' in html or 'menu' in html,
                any(term in text for term in [
                    'copyright', 'todos los derechos', 'política'
                ])
            ]
            
            return any(positive_indicators) and not any(negative_indicators)
            
        except:
            return False
    
    def extract_product_data(self, container, category_name):
        """Extraer datos específicos del producto"""
        try:
            # Extraer nombre
            name = self.extract_product_name_advanced(container)
            if not name:
                return None
            
            # Extraer precio
            price = self.extract_product_price_advanced(container)
            
            # Verificar que sea un producto válido
            if not self.is_valid_product(name, price):
                return None
            
            return {
                'nombre': name,
                'precio': price or 'Precio no disponible',
                'categoria': category_name
            }
            
        except Exception as e:
            logger.debug(f"Error extrayendo datos del producto: {e}")
            return None
    
    def extract_product_name_advanced(self, container):
        """Extracción avanzada de nombre de producto"""
        name_candidates = []
        
        # 1. Títulos y headings (máxima prioridad)
        for tag in ['h1', 'h2', 'h3', 'h4']:
            titles = container.find_all(tag)
            for title in titles:
                text = title.get_text(strip=True)
                if self.is_valid_product_name(text):
                    name_candidates.append((text, 4))
        
        # 2. Enlaces con título (alta prioridad)
        links = container.find_all('a', title=True)
        for link in links:
            title = link.get('title', '').strip()
            if self.is_valid_product_name(title):
                name_candidates.append((title, 3))
        
        # 3. Alt de imágenes (prioridad media)
        images = container.find_all('img', alt=True)
        for img in images:
            alt = img.get('alt', '').strip()
            if self.is_valid_product_name(alt):
                name_candidates.append((alt, 2))
        
        # 4. Clases específicas de productos
        for class_pattern in ['product-name', 'name', 'title', 'product-title']:
            elements = container.find_all(class_=lambda x: x and class_pattern in str(x).lower())
            for elem in elements:
                text = elem.get_text(strip=True)
                if self.is_valid_product_name(text):
                    name_candidates.append((text, 3))
        
        # 5. Texto con marcas conocidas (baja prioridad)
        text_lines = [line.strip() for line in container.get_text().split('\n') if line.strip()]
        brands = ['samsung', 'lg', 'whirlpool', 'mabe', 'frigidaire', 'electrolux', 'haier']
        
        for line in text_lines:
            if (10 < len(line) < 150 and 
                any(brand in line.lower() for brand in brands) and
                self.is_valid_product_name(line)):
                name_candidates.append((line, 1))
        
        # Retornar el mejor candidato
        if name_candidates:
            name_candidates.sort(key=lambda x: x[1], reverse=True)
            return name_candidates[0][0]
        
        return None
    
    def extract_product_price_advanced(self, container):
        """Extracción avanzada de precio"""
        text = container.get_text()
        
        # Patrones de precio específicos para República Dominicana
        price_patterns = [
            r'RD\$\s*[\d,]+(?:\.\d{2})?',
            r'\$\s*[\d,]+(?:\.\d{2})?',
            r'Precio:\s*RD?\$?\s*[\d,]+(?:\.\d{2})?',
            r'(?:^|\s)([\d,]{4,}(?:\.\d{2})?)(?:\s*(?:RD|pesos?)|$)',
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Validar rango de precio razonable
                price_num = re.sub(r'[^\d.]', '', str(match))
                try:
                    if '.' in price_num:
                        price_val = float(price_num.replace(',', ''))
                    else:
                        price_val = int(price_num.replace(',', ''))
                    
                    if 500 <= price_val <= 2000000:  # Rango amplio para electrodomésticos
                        return match if isinstance(match, str) else str(match)
                except:
                    continue
        
        return None
    
    def is_valid_product(self, name, price):
        """Validar si es un producto real"""
        if not name or len(name) < 8:
            return False
        
        # Excluir textos obvios de UI
        ui_texts = [
            'ver más', 'click here', 'loading', 'cargando', 'buscar',
            'filtrar', 'ordenar', 'página', 'siguiente', 'anterior'
        ]
        
        name_lower = name.lower()
        if any(ui_text in name_lower for ui_text in ui_texts):
            return False
        
        return True
    
    def is_valid_product_name(self, text):
        """Validar nombre de producto mejorado"""
        if not text or len(text) < 5 or len(text) > 200:
            return False
        
        # Debe contener letras
        if not re.search(r'[a-zA-Z]', text):
            return False
        
        # Excluir patrones específicos
        invalid_patterns = [
            r'^\d+$',  # Solo números
            r'^(ver|click|buscar|filtrar)',  # Comandos de UI
            r'^(página|page)\s+\d+',  # Números de página
            r'^(siguiente|next|anterior|prev)$',  # Navegación
        ]
        
        text_lower = text.lower()
        for pattern in invalid_patterns:
            if re.match(pattern, text_lower):
                return False
        
        return True
    
    def remove_duplicate_products(self, products):
        """Eliminar productos duplicados"""
        unique_products = []
        seen_names = set()
        
        for product in products:
            # Normalizar nombre para comparación
            name_key = re.sub(r'\s+', ' ', product['nombre'].lower().strip())
            name_key = re.sub(r'[^\w\s]', '', name_key)  # Eliminar puntuación
            
            if name_key not in seen_names:
                seen_names.add(name_key)
                unique_products.append(product)
        
        return unique_products
    
    def scrape_category_with_pagination(self, category):
        """Scraper de categoría con paginación"""
        logger.info(f"📂 Procesando: {category['name']}")
        
        category_products = []
        urls_to_process = [category['url']]
        
        # Procesar página principal de la categoría
        soup = self.get_page_with_retry(category['url'])
        if soup:
            # Extraer productos de la primera página
            products = self.extract_products_advanced(soup, category['name'], category['url'])
            category_products.extend(products)
            
            # Buscar enlaces de paginación
            pagination_links = self.find_pagination_links(soup, category['url'])
            urls_to_process.extend(pagination_links)
        
        # Procesar páginas adicionales (máximo self.max_pages_per_category)
        for i, url in enumerate(urls_to_process[1:self.max_pages_per_category], 2):
            logger.info(f"   📄 Página {i}: {url}")
            
            soup = self.get_page_with_retry(url)
            if soup:
                products = self.extract_products_advanced(soup, category['name'], url)
                category_products.extend(products)
            
            time.sleep(3)  # Pausa entre páginas
        
        # Eliminar duplicados finales
        unique_products = self.remove_duplicate_products(category_products)
        
        logger.info(f"✅ {category['name']}: {len(unique_products)} productos únicos")
        return unique_products
    
    def run_comprehensive_scraping(self):
        """Ejecutar scraping exhaustivo"""
        logger.info("🚀 Iniciando scraping exhaustivo de Sirena.do...")
        
        if not self.setup_driver():
            return False
        
        try:
            # Cargar página principal
            soup = self.get_page_with_retry(self.base_url, wait_seconds=30)
            if not soup:
                logger.error("❌ No se pudo cargar la página principal")
                return False
            
            # Encontrar todas las categorías
            categories = self.find_all_categories_comprehensive(soup)
            
            if not categories:
                logger.error("❌ No se encontraron categorías")
                return False
            
            logger.info(f"📂 Procesando {len(categories)} categorías encontradas...")
            
            # Mostrar categorías encontradas
            print("\n📋 CATEGORÍAS ENCONTRADAS:")
            print("=" * 60)
            for i, cat in enumerate(categories, 1):
                print(f"{i:2d}. {cat['name']} ({cat['source']})")
            print("=" * 60)
            
            # Procesar cada categoría
            total_products = 0
            for i, category in enumerate(categories, 1):
                logger.info(f"🔄 [{i}/{len(categories)}] {category['name']}")
                
                try:
                    if category['url'] not in self.processed_urls:
                        self.processed_urls.add(category['url'])
                        
                        category_products = self.scrape_category_with_pagination(category)
                        self.products_data.extend(category_products)
                        total_products += len(category_products)
                        
                        time.sleep(5)  # Pausa entre categorías
                    
                except Exception as e:
                    logger.error(f"❌ Error en {category['name']}: {e}")
                    continue
            
            logger.info(f"🎉 Scraping completado. Total: {len(self.products_data)} productos")
            return len(self.products_data) > 0
            
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("🔚 Driver cerrado")
    
    def save_to_csv(self, filename='sirena_productos_completo.csv'):
        """Guardar productos en CSV"""
        if not self.products_data:
            logger.warning("⚠️ No hay productos para guardar")
            return
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['nombre', 'precio', 'categoria']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for product in self.products_data:
                    writer.writerow(product)
            
            logger.info(f"💾 Guardado en: {filename}")
            print(f"✅ Archivo creado: {filename}")
            print(f"📊 Productos guardados: {len(self.products_data)}")
            
        except Exception as e:
            logger.error(f"❌ Error guardando CSV: {e}")
    
    def save_detailed_report(self, filename='sirena_reporte_detallado.txt'):
        """Guardar reporte detallado del scraping"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("REPORTE DETALLADO - SIRENA.DO SCRAPING\n")
                f.write("=" * 60 + "\n\n")
                
                # Estadísticas generales
                f.write(f"Total de productos extraídos: {len(self.products_data)}\n")
                f.write(f"Total de URLs procesadas: {len(self.processed_urls)}\n")
                f.write(f"Páginas por categoría: {self.max_pages_per_category}\n\n")
                
                # Productos por categoría
                category_counts = Counter(p['categoria'] for p in self.products_data)
                f.write("PRODUCTOS POR CATEGORÍA:\n")
                f.write("-" * 30 + "\n")
                for category, count in category_counts.most_common():
                    f.write(f"{category}: {count} productos\n")
                
                f.write("\n" + "=" * 60 + "\n")
                f.write("MUESTRA DE PRODUCTOS EXTRAÍDOS:\n")
                f.write("=" * 60 + "\n\n")
                
                # Muestra de productos (primeros 50)
                for i, product in enumerate(self.products_data[:50], 1):
                    f.write(f"{i:2d}. {product['nombre']}\n")
                    f.write(f"    💰 Precio: {product['precio']}\n")
                    f.write(f"    📂 Categoría: {product['categoria']}\n")
                    f.write("-" * 60 + "\n")
                
                if len(self.products_data) > 50:
                    f.write(f"\n... y {len(self.products_data) - 50} productos más.\n")
            
            logger.info(f"📄 Reporte detallado guardado en: {filename}")
            
        except Exception as e:
            logger.error(f"❌ Error guardando reporte: {e}")
    
    def print_comprehensive_results(self):
        """Mostrar resultados comprehensivos"""
        if not self.products_data:
            print("❌ No hay productos para mostrar")
            return
        
        print("\n" + "🎉 SCRAPING EXHAUSTIVO COMPLETADO" + " 🎉")
        print("=" * 80)
        
        # Estadísticas generales
        total_products = len(self.products_data)
        category_counts = Counter(p['categoria'] for p in self.products_data)
        
        print(f"📊 ESTADÍSTICAS GENERALES:")
        print(f"   Total de productos extraídos: {total_products}")
        print(f"   Categorías procesadas: {len(category_counts)}")
        print(f"   URLs procesadas: {len(self.processed_urls)}")
        print(f"   Páginas por categoría: {self.max_pages_per_category}")
        
        print(f"\n📂 PRODUCTOS POR CATEGORÍA:")
        print("-" * 50)
        for category, count in category_counts.most_common():
            percentage = (count / total_products) * 100
            print(f"   {category}: {count} productos ({percentage:.1f}%)")
        
        print(f"\n📋 MUESTRA DE PRODUCTOS EXTRAÍDOS:")
        print("=" * 80)
        
        # Mostrar muestra diversa de productos
        sample_size = min(20, len(self.products_data))
        sample_products = []
        
        # Obtener muestra representativa de cada categoría
        for category in category_counts.keys():
            cat_products = [p for p in self.products_data if p['categoria'] == category]
            sample_products.extend(cat_products[:3])  # 3 productos por categoría
        
        # Completar muestra si es necesario
        if len(sample_products) < sample_size:
            remaining = sample_size - len(sample_products)
            other_products = [p for p in self.products_data if p not in sample_products]
            sample_products.extend(other_products[:remaining])
        
        for i, product in enumerate(sample_products[:sample_size], 1):
            print(f"{i:2d}. {product['nombre']}")
            print(f"    💰 Precio: {product['precio']}")
            print(f"    📂 Categoría: {product['categoria']}")
            print("-" * 60)
        
        if total_products > sample_size:
            print(f"\n... y {total_products - sample_size} productos más.")
        
        print("\n" + "=" * 80)
        print("💾 Los datos completos se han guardado en archivos CSV y de reporte.")
        print("=" * 80)

def main():
    print("🚀 SIRENA.DO SCRAPER AVANZADO - EXPLORACIÓN EXHAUSTIVA")
    print("=" * 80)
    print("✅ CARACTERÍSTICAS IMPLEMENTADAS:")
    print("   • Búsqueda exhaustiva de TODAS las categorías y subcategorías")
    print("   • Navegación automática por múltiples páginas de paginación")
    print("   • Extracción inteligente de productos reales")
    print("   • Filtrado avanzado de contenido de navegación/UI")
    print("   • Validación estricta de nombres y precios")
    print("   • Eliminación automática de duplicados")
    print("   • Reportes detallados y estadísticas completas")
    print("   • Manejo robusto de errores y reintentos")
    print("=" * 80)
    
    try:
        headless_input = input("¿Ejecutar sin ventana visible? (s/N): ").lower()
        headless = headless_input in ['s', 'y', 'yes', 'sí']
    except:
        headless = True
    
    print(f"\n🔧 Configuración:")
    print(f"   • Modo headless: {'Activado' if headless else 'Desactivado'}")
    print(f"   • Páginas por categoría: 2 (como solicitado)")
    print(f"   • Pausa entre categorías: 5 segundos")
    print(f"   • Reintentos por página: 3")
    print("\n🚀 Iniciando scraping exhaustivo...")
    print("=" * 80)
    
    scraper = SirenaAdvancedScraper(headless=headless)
    
    start_time = time.time()
    
    if scraper.run_comprehensive_scraping():
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n⏱️  Tiempo total de ejecución: {duration:.1f} segundos")
        
        # Mostrar resultados
        scraper.print_comprehensive_results()
        
        # Guardar archivos
        scraper.save_to_csv('sirena_productos_exhaustivo.csv')
        scraper.save_detailed_report('sirena_reporte_completo.txt')
        
        print(f"\n🎉 ¡SCRAPING EXHAUSTIVO COMPLETADO EXITOSAMENTE!")
        print(f"📁 Archivos generados:")
        print(f"   • sirena_productos_exhaustivo.csv")
        print(f"   • sirena_reporte_completo.txt")
        
    else:
        print("❌ No se pudieron extraer productos")
        print("💡 Sugerencias:")
        print("   • Verificar conexión a internet")
        print("   • Comprobar que Sirena.do esté disponible")
        print("   • Intentar ejecutar sin modo headless")
    
    print("=" * 80)

if __name__ == "__main__":
    main()