import time
import csv
import logging
import re
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from collections import Counter

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class JumboCompleteScraper:
    def __init__(self, headless=True, target_products=2000):
        self.base_url = "https://jumbo.com.do/"
        self.driver = None
        self.products_data = []
        self.headless = headless
        self.processed_urls = set()
        self.target_products = target_products
        self.unique_products = set()  # Para evitar duplicados
        
        # Categorías principales objetivo (más específicas para República Dominicana)
        self.target_categories = {
            "Supermercado": ["supermercado", "mercado", "alimentos", "comida", "groceries", "abarrotes", "food"],
            "Belleza y Salud": ["belleza", "salud", "cuidado personal", "higiene", "beauty", "health", "cosmetic"],
            "Hogar": ["hogar", "cocina", "limpieza", "muebles", "home", "casa", "furniture"],
            "Electrodomésticos": ["electrodomésticos", "electrodomestico", "electro", "appliances", "electronics"],
            "Ferretería": ["ferretería", "ferreteria", "herramientas", "tools", "hardware", "construccion"],
            "Deportes": ["deportes", "fitness", "ejercicio", "sports", "deporte"],
            "Bebés": ["bebés", "bebes", "niños", "niñas", "baby", "kids", "infantil"],
            "Oficina": ["oficina", "útiles", "escolares", "office", "school", "papeleria"],
            "Juguetería": ["juguetes", "juegos", "toys", "games", "jugueteria"],
            "Tecnología": ["tecnologia", "tech", "computacion", "celulares", "phones"],
            "Ropa": ["ropa", "vestir", "clothing", "fashion", "textil"],
            "Automóvil": ["auto", "carro", "vehiculo", "automotive", "car"]
        }
        
    def setup_driver(self):
        """Configurar el driver de Selenium optimizado para JavaScript"""
        try:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless")
            
            # Opciones optimizadas para sitios JavaScript
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # Optimizaciones para velocidad manteniendo funcionalidad
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-logging")
            chrome_options.add_argument("--disable-dev-tools")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Timeout optimizado
            self.driver.implicitly_wait(3)
            logger.info("✅ Driver configurado correctamente")
            return True
        except Exception as e:
            logger.error(f"❌ Error configurando Selenium: {e}")
            return False
    
    def get_page_with_js_wait(self, url, max_retries=2):
        """Cargar página esperando a que JavaScript termine de cargar"""
        for attempt in range(max_retries):
            try:
                self.driver.get(url)
                
                # Esperar a que el body esté presente
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, 'body'))
                )
                
                # Esperar un poco para JavaScript
                time.sleep(2)
                
                # Scroll para activar lazy loading
                self.driver.execute_script("window.scrollTo(0, 500);")
                time.sleep(1)
                self.driver.execute_script("window.scrollTo(0, 0);")
                
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                text_content = soup.get_text(strip=True)
                
                if len(text_content) > 300:
                    return soup
                    
            except Exception as e:
                logger.warning(f"⚠️ Intento {attempt + 1} fallido: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2)
        
        return None

    def find_main_categories(self):
        """Buscar categorías principales con estrategias múltiples"""
        soup = self.get_page_with_js_wait(self.base_url)
        if not soup:
            return []
        
        categories = []
        
        # ESTRATEGIA 1: Navegación principal
        nav_selectors = [
            'nav a', 'header nav a', '.navbar a', '.nav a', '.navigation a',
            '.main-menu a', '.primary-menu a', '.menu-principal a',
            '.header-menu a', '.top-menu a', '.main-nav a'
        ]
        
        for selector in nav_selectors:
            links = soup.select(selector)
            logger.info(f"🔍 Selector '{selector}': {len(links)} enlaces")
            
            for link in links:
                text = link.get_text(strip=True)
                href = link.get('href', '')
                
                if self.is_potential_category(text, href):
                    full_url = urljoin(self.base_url, href)
                    categories.append({
                        'name': self.normalize_category_name(text),
                        'url': full_url,
                        'parent': None,
                        'level': 'main'
                    })
        
        # ESTRATEGIA 2: Búsqueda por palabras clave en todos los enlaces
        if len(categories) < 8:
            all_links = soup.find_all('a', href=True)
            logger.info(f"🔍 Analizando {len(all_links)} enlaces por palabras clave")
            
            for link in all_links:
                text = link.get_text(strip=True)
                href = link.get('href', '')
                
                if self.is_target_category(text) and len(text) > 3 and len(text) < 50:
                    full_url = urljoin(self.base_url, href)
                    categories.append({
                        'name': self.normalize_category_name(text),
                        'url': full_url,
                        'parent': None,
                        'level': 'main'
                    })
        
        # Limpiar duplicados
        unique_categories = self.clean_categories(categories)
        
        logger.info(f"📊 CATEGORÍAS PRINCIPALES ENCONTRADAS: {len(unique_categories)}")
        for cat in unique_categories:
            logger.info(f"   📂 {cat['name']} -> {cat['url']}")
        
        return unique_categories
    
    def find_subcategories(self, main_category, max_subcategories=15):
        """Buscar subcategorías de una categoría principal"""
        soup = self.get_page_with_js_wait(main_category['url'])
        if not soup:
            return []
        
        subcategories = []
        
        # ESTRATEGIA 1: Buscar en menús laterales y filtros
        sidebar_selectors = [
            '.sidebar a', '.filters a', '.categories a', 
            '.menu-lateral a', '.category-nav a', '.subcategory a',
            '[class*="filter"] a', '[class*="category"] a',
            '[class*="submenu"] a', '[class*="subcategory"] a'
        ]
        
        for selector in sidebar_selectors:
            links = soup.select(selector)
            
            for link in links:
                text = link.get_text(strip=True)
                href = link.get('href', '')
                
                if self.is_valid_subcategory(text, href, main_category):
                    full_url = urljoin(self.base_url, href)
                    subcategories.append({
                        'name': text,
                        'url': full_url,
                        'parent': main_category['name'],
                        'level': 'sub'
                    })
        
        # ESTRATEGIA 2: Buscar enlaces dentro de secciones de categoría
        category_sections = soup.find_all(['div', 'section'], class_=lambda x: x and any(
            keyword in x.lower() for keyword in ['category', 'filter', 'menu', 'nav']
        ))
        
        for section in category_sections:
            links = section.find_all('a', href=True)
            for link in links:
                text = link.get_text(strip=True)
                href = link.get('href', '')
                
                if self.is_valid_subcategory(text, href, main_category):
                    full_url = urljoin(self.base_url, href)
                    subcategories.append({
                        'name': text,
                        'url': full_url,
                        'parent': main_category['name'],
                        'level': 'sub'
                    })
        
        # Limpiar y limitar subcategorías
        cleaned_subs = self.clean_categories(subcategories)[:max_subcategories]
        
        logger.info(f"   📁 Encontradas {len(cleaned_subs)} subcategorías para {main_category['name']}")
        for sub in cleaned_subs:
            logger.info(f"      ↳ {sub['name']}")
        
        return cleaned_subs
    
    def find_pagination_links(self, soup, current_url):
        """Buscar enlaces de paginación en la página actual"""
        pagination_links = []
        
        # Selectores comunes para paginación
        pagination_selectors = [
            '.pagination a', '.pager a', '.page-nav a',
            '[class*="page"] a', '[class*="next"] a',
            '.paginacion a', '.paginas a'
        ]
        
        for selector in pagination_selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href', '')
                text = link.get_text(strip=True).lower()
                
                # Buscar enlaces "siguiente" o números de página
                if href and (text.isdigit() or 'next' in text or 'siguiente' in text or 'más' in text):
                    full_url = urljoin(self.base_url, href)
                    if full_url != current_url and full_url not in pagination_links:
                        pagination_links.append(full_url)
        
        # También buscar parámetros de página en la URL
        if '?' in current_url:
            base_url = current_url.split('?')[0]
            for page_num in range(2, 6):  # Páginas 2-5
                page_url = f"{base_url}?page={page_num}"
                if page_url not in pagination_links:
                    pagination_links.append(page_url)
        
        return pagination_links[:4]  # Máximo 4 páginas adicionales
    
    def extract_products_complete(self, category, max_pages=5):
        """Extraer productos de una categoría con paginación"""
        all_products = []
        pages_to_process = [category['url']]
        
        # Obtener primera página y buscar paginación
        soup = self.get_page_with_js_wait(category['url'])
        if soup:
            # Extraer productos de la primera página
            products = self.extract_products_from_page(soup, category)
            all_products.extend(products)
            
            # Buscar más páginas
            pagination_links = self.find_pagination_links(soup, category['url'])
            pages_to_process.extend(pagination_links[:max_pages-1])
        
        # Procesar páginas adicionales
        for i, page_url in enumerate(pages_to_process[1:], 2):
            if len(all_products) >= 50:  # Límite por categoría
                break
                
            logger.info(f"      📄 Página {i}: {page_url}")
            page_soup = self.get_page_with_js_wait(page_url)
            if page_soup:
                page_products = self.extract_products_from_page(page_soup, category)
                if page_products:
                    all_products.extend(page_products)
                else:
                    break  # Si no hay productos, probablemente no hay más páginas
            
            time.sleep(1)  # Pausa entre páginas
        
        logger.info(f"📦 Total extraído de {category['name']}: {len(all_products)} productos")
        return all_products
    
    def extract_products_from_page(self, soup, category):
        """Extraer productos de una página específica"""
        products = []
        
        # Selectores optimizados para productos
        product_selectors = [
            '[class*="product-item"]', '[class*="product-card"]', 
            '[class*="item-product"]', '[class*="product"]',
            '[data-product]', '[data-item]',
            '.card', '.tile', '[class*="card"]'
        ]
        
        for selector in product_selectors:
            containers = soup.select(selector)
            
            if containers:
                logger.info(f"      🔍 Usando selector '{selector}': {len(containers)} elementos")
                
                for container in containers:
                    product = self.extract_product_data(container, category)
                    if product:
                        # Evitar duplicados usando nombre + categoría como clave
                        product_key = f"{product['nombre'].lower()}_{product['categoria']}"
                        if product_key not in self.unique_products:
                            self.unique_products.add(product_key)
                            products.append(product)
                
                if products:  # Si encontramos productos, no probar más selectores
                    break
        
        # Método alternativo si no encontramos productos
        if not products:
            products = self.alternative_product_extraction(soup, category)
        
        return products[:40]  # Máximo 40 productos por página
    
    def alternative_product_extraction(self, soup, category):
        """Método alternativo para extraer productos"""
        products = []
        
        # Buscar divs que contengan imagen + título
        all_divs = soup.find_all('div')[:200]  # Limitar búsqueda
        
        for div in all_divs:
            if len(products) >= 30:
                break
                
            img = div.find('img')
            title_elem = div.find(['h1', 'h2', 'h3', 'h4', 'h5', 'span', 'a'])
            
            if img and title_elem:
                product = self.extract_product_data(div, category)
                if product:
                    product_key = f"{product['nombre'].lower()}_{product['categoria']}"
                    if product_key not in self.unique_products:
                        self.unique_products.add(product_key)
                        products.append(product)
        
        return products
    
    def extract_product_data(self, container, category):
        """Extraer datos del producto desde el contenedor"""
        try:
            # Extraer nombre
            name = self.extract_product_name(container)
            if not name or not self.is_valid_product_name(name):
                return None
            
            # Extraer precio
            price = self.extract_product_price(container)
            
            # Construir categoría completa
            full_category = category['name']
            if category.get('parent'):
                full_category = f"{category['parent']} > {category['name']}"
            
            return {
                'nombre': name[:120],
                'precio': price or 'Precio no disponible',
                'categoria': full_category
            }
            
        except Exception:
            return None
    
    def extract_product_name(self, container):
        """Extraer nombre del producto"""
        name_selectors = [
            'h1', 'h2', 'h3', 'h4', 'h5',
            '[class*="name"]', '[class*="title"]', '[class*="product-name"]',
            '[class*="item-name"]', '[data-name]', 'a[title]'
        ]
        
        for selector in name_selectors:
            element = container.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                if text and 3 < len(text) < 150:
                    return text
        
        # Método alternativo con atributos de imagen
        img = container.find('img')
        if img:
            for attr in ['alt', 'title', 'data-name']:
                value = img.get(attr, '').strip()
                if value and 3 < len(value) < 150:
                    return value
        
        return None
    
    def extract_product_price(self, container):
        """Extraer precio del producto"""
        price_selectors = [
            '[class*="price"]', '[class*="precio"]', '[class*="cost"]',
            '[data-price]', '.currency', '[class*="amount"]'
        ]
        
        for selector in price_selectors:
            elements = container.select(selector)
            for element in elements:
                price_text = element.get_text(strip=True)
                parsed_price = self.parse_price(price_text)
                if parsed_price:
                    return parsed_price
        
        return None
    
    def parse_price(self, price_text):
        """Parsear y formatear precio"""
        try:
            clean_text = re.sub(r'[^\d.,]', '', price_text)
            
            price_patterns = [
                r'(\d{1,3}(?:[,.]\d{3})*(?:[.,]\d{2})?)',
                r'(\d+[.,]\d{2})',
                r'(\d+)'
            ]
            
            for pattern in price_patterns:
                match = re.search(pattern, clean_text)
                if match:
                    num_str = match.group(1)
                    
                    if ',' in num_str and '.' in num_str:
                        if num_str.rindex(',') > num_str.rindex('.'):
                            num_str = num_str.replace('.', '').replace(',', '.')
                        else:
                            num_str = num_str.replace(',', '')
                    elif num_str.count(',') == 1 and len(num_str.split(',')[1]) == 2:
                        num_str = num_str.replace(',', '.')
                    elif ',' in num_str:
                        num_str = num_str.replace(',', '')
                    
                    price = float(num_str)
                    
                    if 1 <= price <= 500000:
                        return f"RD${price:,.2f}"
            
            return None
        except:
            return None
    
    def is_potential_category(self, text, href):
        """Determinar si un enlace es una categoría potencial"""
        if not text or not href:
            return False
        
        text_lower = text.lower().strip()
        href_lower = href.lower()
        
        # Filtros negativos
        negative_keywords = [
            'login', 'cuenta', 'carrito', 'buscar', 'ayuda', 'contacto',
            'facebook', 'twitter', 'instagram', 'newsletter' ,'whatsapp'
        ]
        
        if any(neg in text_lower for neg in negative_keywords):
            return False
        
        # Filtros positivos
        positive_url_patterns = [
            'categoria', 'category', 'departamento', 'department',
            'seccion', 'section', '/c/', '/cat/'
        ]
        
        return any(pattern in href_lower for pattern in positive_url_patterns) or self.is_target_category(text)
    
    def is_target_category(self, name):
        """Verificar si coincide con categorías objetivo"""
        if not name:
            return False
        name_lower = name.lower()
        return any(any(keyword in name_lower for keyword in keywords) 
                  for keywords in self.target_categories.values())
    
    def normalize_category_name(self, name):
        """Normalizar nombre de categoría"""
        name_lower = name.lower()
        for category, keywords in self.target_categories.items():
            if any(keyword in name_lower for keyword in keywords):
                return category
        return name.strip().title()
    
    def is_valid_subcategory(self, text, href, main_category):
        """Validar si es una subcategoría válida"""
        if not text or not href or len(text) < 3 or len(text) > 80:
            return False
        
        text_lower = text.lower()
        invalid_terms = [
            'ver todo', 'ver más', 'mostrar todo', 'volver', 'home',
            'página', 'siguiente', 'anterior', 'filtro', 'casa cuesta'
        ]
        
        return not any(term in text_lower for term in invalid_terms)
    
    def is_valid_product_name(self, name):
        """Validar nombre de producto"""
        if not name or len(name) < 3 or len(name) > 120:
            return False
        
        invalid_terms = [
            'ver más', 'comprar', 'añadir', 'carrito', 'login',
            'página', 'siguiente', 'filtro', 'ordenar'
        ]
        
        name_lower = name.lower()
        return not any(term in name_lower for term in invalid_terms) and \
               bool(re.search(r'[a-zA-ZáéíóúÁÉÍÓÚñÑ]', name))
    
    def clean_categories(self, categories):
        """Limpiar y eliminar duplicados de categorías"""
        cleaned = []
        seen_urls = set()
        seen_names = set()
        
        for cat in categories:
            url = cat['url']
            name = cat['name'].lower()
            
            if url not in seen_urls and name not in seen_names:
                seen_urls.add(url)
                seen_names.add(name)
                cleaned.append(cat)
        
        return cleaned
    
    def scrape_complete(self):
        """Proceso completo de scraping con todas las categorías y subcategorías"""
        logger.info(f"🚀 Iniciando scraping completo - Objetivo: {self.target_products} productos")
        
        if not self.setup_driver():
            return False
        
        try:
            # Paso 1: Obtener categorías principales
            main_categories = self.find_main_categories()
            if not main_categories:
                logger.error("❌ No se encontraron categorías principales")
                return False
            
            logger.info(f"📂 Encontradas {len(main_categories)} categorías principales")
            
            # Paso 2: Procesar cada categoría principal
            for i, main_cat in enumerate(main_categories, 1):
                if len(self.products_data) >= self.target_products:
                    logger.info(f"🎯 Objetivo de {self.target_products} productos alcanzado")
                    break
                
                logger.info(f"\n📦 [{i}/{len(main_categories)}] PROCESANDO: {main_cat['name']}")
                logger.info(f"🔗 URL: {main_cat['url']}")
                
                # Extraer productos de la categoría principal
                main_products = self.extract_products_complete(main_cat)
                self.products_data.extend(main_products)
                
                logger.info(f"📊 Productos acumulados: {len(self.products_data)}")
                
                # Paso 3: Buscar y procesar subcategorías
                subcategories = self.find_subcategories(main_cat)
                
                if subcategories:
                    logger.info(f"   📁 Procesando {len(subcategories)} subcategorías...")
                    
                    for j, sub_cat in enumerate(subcategories, 1):
                        if len(self.products_data) >= self.target_products:
                            break
                        
                        logger.info(f"      ↳ [{j}/{len(subcategories)}] {sub_cat['name']}")
                        
                        # Extraer productos de subcategoría
                        sub_products = self.extract_products_complete(sub_cat)
                        self.products_data.extend(sub_products)
                        
                        time.sleep(1)  # Pausa entre subcategorías
                
                logger.info(f"📊 Total después de {main_cat['name']}: {len(self.products_data)} productos")
                time.sleep(2)  # Pausa entre categorías principales
            
            logger.info(f"\n🎉 SCRAPING COMPLETADO - Total productos: {len(self.products_data)}")
            return len(self.products_data) > 0
            
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("🔚 Driver cerrado")
    
    def save_results(self, filename='jumbo_productos_completo.csv'):
        """Guardar resultados completos en CSV"""
        if not self.products_data:
            logger.warning("⚠️ No hay productos para guardar")
            return
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['nombre', 'precio', 'categoria'])
                writer.writeheader()
                writer.writerows(self.products_data)
            
            logger.info(f"💾 Datos guardados en {filename}")
            print(f"\n✅ RESULTADOS GUARDADOS EN {filename}")
            print(f"📊 TOTAL DE PRODUCTOS: {len(self.products_data)}")
            
            # Estadísticas detalladas
            main_categories = Counter()
            subcategories = Counter()
            
            for product in self.products_data:
                categoria = product['categoria']
                if '>' in categoria:
                    main_cat, sub_cat = categoria.split('>', 1)
                    main_categories[main_cat.strip()] += 1
                    subcategories[categoria] += 1
                else:
                    main_categories[categoria] += 1
            
            print(f"\n📦 PRODUCTOS POR CATEGORÍA PRINCIPAL:")
            for cat, count in main_categories.most_common():
                print(f"   {cat}: {count} productos")
            
            print(f"\n🔍 TOP 10 SUBCATEGORÍAS:")
            for cat, count in subcategories.most_common(10):
                print(f"   {cat}: {count} productos")
            
            # Ejemplos de productos
            print(f"\n📝 EJEMPLOS DE PRODUCTOS ENCONTRADOS:")
            for i, product in enumerate(self.products_data[:8], 1):
                print(f"   {i}. {product['nombre']} - {product['precio']}")
                print(f"      Categoría: {product['categoria']}")
            
        except Exception as e:
            logger.error(f"❌ Error guardando CSV: {e}")

def main():
    print("🛒 JUMBO.COM.DO - SCRAPER COMPLETO")
    print("=" * 80)
    print("🎯 EXTRACCIÓN COMPLETA DE PRODUCTOS")
    print("📂 Todas las categorías principales y subcategorías")
    print("📄 Múltiples páginas por categoría")
    print("🔄 Sistema anti-duplicados integrado")
    print("=" * 80)
    
    # Configurar objetivo de productos
    try:
        target = int(input("¿Cuántos productos necesitas? (por defecto 2000): ") or "2000")
        if target < 100:
            target = 2000
    except:
        target = 2000
    
    # Configurar modo headless
    headless = True
    respuesta = input("¿Ejecutar en modo visible para monitoreo? (s/N): ").lower()
    if respuesta in ['s', 'si', 'sí']:
        headless = False
        print("🖥️  Ejecutando en modo visible")
    
    print(f"\n🎯 Objetivo: {target} productos únicos")
    print("🚀 Iniciando extracción completa...")
    
    # Ejecutar scraper
    start_time = time.time()
    scraper = JumboCompleteScraper(headless=headless, target_products=target)
    
    if scraper.scrape_complete():
        scraper.save_results()
        elapsed_time = time.time() - start_time
        print(f"\n⏱️  TIEMPO TOTAL: {elapsed_time:.1f} segundos")
        print(f"⚡ VELOCIDAD: {len(scraper.products_data)/(elapsed_time/60):.1f} productos/minuto")
        print("🎉 ¡PROCESO COMPLETADO EXITOSAMENTE!")
    else:
        print("❌ No se pudieron extraer productos")
    
    print("=" * 80)

if __name__ == "__main__":
    main()