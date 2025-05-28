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

class JumboSinglePageScraper:
    def __init__(self, headless=True):
        self.base_url = "https://jumbo.com.do/"
        self.driver = None
        self.products_data = []
        self.headless = headless
        self.processed_urls = set()
        
        # Categorías principales objetivo
        self.target_categories = {
            "Supermercado": ["supermercado", "mercado", "alimentos", "comida"],
            "Belleza y Salud": ["belleza", "salud", "cuidado personal", "higiene"],
            "Hogar": ["hogar", "cocina", "limpieza", "muebles"],
            "Electrodomésticos": ["electrodomésticos", "electrodomestico", "electro"],
            "Ferretería": ["ferretería", "ferreteria", "herramientas"],
            "Deportes": ["deportes", "fitness", "ejercicio"],
            "Bebés": ["bebés", "bebes", "niños", "niñas"],
            "Escolares y Oficina": ["escolares", "oficina", "útiles", "libros"],
            "Juguetería": ["juguetería", "juguetes", "juegos"]
        }
        
    def setup_driver(self):
        """Configurar el driver de Selenium optimizado"""
        try:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_argument("--window-size=1920,1080")
            
            # Optimizaciones para velocidad
            chrome_options.add_argument("--disable-images")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-gpu")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.implicitly_wait(3)
            logger.info("✅ Driver configurado correctamente")
            return True
        except Exception as e:
            logger.error(f"❌ Error configurando Selenium: {e}")
            return False
    
    def get_page(self, url, max_retries=2):
        """Cargar página con reintentos optimizados"""
        for attempt in range(max_retries):
            try:
                self.driver.get(url)
                WebDriverWait(self.driver, 8).until(
                    EC.presence_of_element_located((By.TAG_NAME, 'body'))
                )
                time.sleep(1.5)
                return BeautifulSoup(self.driver.page_source, 'html.parser')
            except Exception as e:
                logger.warning(f"⚠️ Intento {attempt + 1} fallido para {url}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2)
        return None

    def find_main_categories(self):
        """Buscar categorías principales con múltiples estrategias"""
        soup = self.get_page(self.base_url)
        if not soup:
            return []
        
        categories = []
        
        # Estrategia 1: Buscar en el menú de navegación principal
        nav_containers = [
            ('nav', 'nav'), 
            ('div', 'menu'), 
            ('div', 'navigation'),
            ('ul', 'nav-list'),
            ('div', 'categories'),
            ('header', ''),
            ('div', 'header')
        ]
        
        for tag, class_part in nav_containers:
            if class_part:
                elements = soup.find_all(tag, class_=lambda x: x and class_part in x.lower())
            else:
                elements = soup.find_all(tag)
            
            for element in elements:
                for link in element.find_all('a', href=True):
                    name = link.get_text(strip=True)
                    url = link['href']
                    if self.is_target_category(name) and len(name) > 3:
                        full_url = urljoin(self.base_url, url)
                        categories.append({
                            'name': self.normalize_category_name(name),
                            'url': full_url,
                            'parent': None
                        })
        
        # Estrategia 2: Buscar enlaces con texto que coincida con categorías objetivo
        if not categories:
            for link in soup.find_all('a', href=True):
                name = link.get_text(strip=True)
                if self.is_target_category(name) and len(name) > 3:
                    url = link['href']
                    full_url = urljoin(self.base_url, url)
                    categories.append({
                        'name': self.normalize_category_name(name),
                        'url': full_url,
                        'parent': None
                    })
        
        # Eliminar duplicados
        unique_categories = []
        seen_urls = set()
        
        for cat in categories:
            if cat['url'] not in seen_urls and '/categoria' in cat['url'] or '/category' in cat['url']:
                seen_urls.add(cat['url'])
                unique_categories.append(cat)
                logger.info(f"✅ Categoría encontrada: {cat['name']}")
        
        return unique_categories[:9]  # Limitar a máximo 9 categorías principales
    
    def is_target_category(self, name):
        """Determinar si el nombre coincide con nuestras categorías objetivo"""
        name_lower = name.lower()
        for category, keywords in self.target_categories.items():
            if any(keyword in name_lower for keyword in keywords):
                return True
        return False
    
    def normalize_category_name(self, name):
        """Normalizar el nombre de la categoría según nuestro mapeo"""
        name_lower = name.lower()
        for category, keywords in self.target_categories.items():
            if any(keyword in name_lower for keyword in keywords):
                return category.title()
        return name.strip().title()
    
    def find_subcategories(self, category):
        """Buscar subcategorías - SOLO primera página"""
        soup = self.get_page(category['url'])
        if not soup:
            return []
        
        subcategories = []
        
        # Estrategia 1: Buscar en sidebars y menús laterales
        sidebar_selectors = [
            ('div', 'sidebar'),
            ('div', 'filters'), 
            ('div', 'categories'),
            ('div', 'menu-lateral'),
            ('nav', 'category-nav'),
            ('ul', 'category-list')
        ]
        
        for tag, class_part in sidebar_selectors:
            elements = soup.find_all(tag, class_=lambda x: x and class_part in x.lower())
            for element in elements:
                for link in element.find_all('a', href=True):
                    name = link.get_text(strip=True)
                    if name and len(name) > 2 and not any(x in name.lower() for x in ['ver todo', 'ver más', 'volver', 'todo', 'home', 'inicio']):
                        url = link['href']
                        full_url = urljoin(self.base_url, url)
                        subcategories.append({
                            'name': name,
                            'url': full_url,
                            'parent': category['name']
                        })
        
        # Estrategia 2: Buscar en secciones de categorías
        if not subcategories:
            category_sections = soup.find_all('div', class_=lambda x: x and ('category' in x.lower() or 'subcategory' in x.lower()))
            for section in category_sections[:3]:  # Solo primeras 3 secciones
                for link in section.find_all('a', href=True):
                    name = link.get_text(strip=True)
                    if name and len(name) > 2:
                        url = link['href']
                        full_url = urljoin(self.base_url, url)
                        subcategories.append({
                            'name': name,
                            'url': full_url,
                            'parent': category['name']
                        })
        
        # Eliminar duplicados y limitar cantidad
        unique_subcategories = []
        seen_urls = set()
        
        for sub in subcategories:
            if sub['url'] not in seen_urls and len(unique_subcategories) < 10:  # Máximo 5 subcategorías por categoría
                seen_urls.add(sub['url'])
                unique_subcategories.append(sub)
                logger.info(f"   ↳ Subcategoría encontrada: {sub['name']}")
        
        return unique_subcategories
    
    def extract_products_from_page(self, category):
        """Extraer productos SOLO de la primera página"""
        soup = self.get_page(category['url'])
        if not soup:
            return []
        
        products = []
        
        # Múltiples selectores para encontrar productos
        product_selectors = [
            # Selectores específicos comunes
            'div[class*="product-item"]',
            'div[class*="product-card"]', 
            'div[class*="product-grid"]',
            'div[class*="item-product"]',
            'li[class*="product"]',
            'div[class*="product"]',
            # Selectores más generales
            '.product-item',
            '.product-card',
            '.product',
            '[data-product]'
        ]
        
        # Intentar cada selector
        for selector in product_selectors:
            containers = soup.select(selector)
            if containers:
                logger.info(f"🔍 Usando selector: {selector} - Encontrados: {len(containers)}")
                for container in containers[:30]:  # Máximo 20 productos por página
                    product = self.extract_product_data(container, category)
                    if product:
                        products.append(product)
                break  # Si encontramos productos con un selector, no probar otros
        
        # Si no encontramos nada, buscar por estructura HTML típica
        if not products:
            # Buscar contenedores que tengan imagen + texto
            potential_products = soup.find_all('div', class_=True)
            for container in potential_products[:30]:
                if container.find('img') and (container.find('h2') or container.find('h3') or container.find('h4')):
                    product = self.extract_product_data(container, category)
                    if product and len(products) < 30:  # Máximo 15 productos
                        products.append(product)
        
        logger.info(f"📦 Extraídos {len(products)} productos de {category['name']}")
        return products
    
    def extract_product_data(self, container, category):
        """Extraer datos del producto desde el contenedor"""
        try:
            # Extraer nombre del producto
            name = None
            name_selectors = [
                'h1', 'h2', 'h3', 'h4', 
                '[class*="name"]', '[class*="title"]', 
                '[class*="product-name"]', 'a[title]'
            ]
            
            for selector in name_selectors:
                element = container.select_one(selector)
                if element:
                    text = element.get_text(strip=True)
                    if text and len(text) > 3:
                        name = text
                        break
            
            # Si no encontramos nombre, intentar con atributos de imagen
            if not name:
                img = container.find('img')
                if img and img.get('alt'):
                    name = img['alt'].strip()
                elif img and img.get('title'):
                    name = img['title'].strip()
            
            if not name or not self.is_valid_product_name(name):
                return None
            
            # Extraer precio
            price = None
            price_selectors = [
                '[class*="price"]', '[class*="precio"]',
                '.currency', '[data-price]', '.cost'
            ]
            
            for selector in price_selectors:
                elements = container.select(selector)
                for element in elements:
                    price_text = element.get_text(strip=True)
                    if price_text:
                        parsed_price = self.parse_price(price_text)
                        if parsed_price:
                            price = parsed_price
                            break
                if price:
                    break
            
            # Construir categoría completa
            full_category = category['name']
            if category.get('parent'):
                full_category = f"{category['parent']} > {category['name']}"
            
            return {
                'nombre': name[:150],  # Limitar longitud
                'precio': price or 'Precio no disponible',
                'categoria': full_category
            }
            
        except Exception as e:
            logger.debug(f"Error extrayendo producto: {e}")
            return None
    
    def parse_price(self, price_text):
        """Parsear y formatear precio"""
        try:
            # Limpiar texto y buscar números
            clean_text = re.sub(r'[^\d.,]', '', price_text)
            
            # Buscar patrón de precio
            price_patterns = [
                r'(\d{1,3}(?:[,.]\d{3})*(?:[.,]\d{2})?)',  # 1,234.56 o 1.234,56
                r'(\d+[.,]\d{2})',  # 123.45 o 123,45
                r'(\d+)'  # Solo números
            ]
            
            for pattern in price_patterns:
                match = re.search(pattern, clean_text)
                if match:
                    num_str = match.group(1)
                    # Normalizar formato
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
                    
                    # Validar rango razonable (1 peso a 500,000 pesos)
                    if 1 <= price <= 500000:
                        return f"RD${price:,.2f}"
                    
            return None
        except:
            return None
    
    def is_valid_product_name(self, name):
        """Validar que el nombre sea de un producto real"""
        if not name or len(name) < 3 or len(name) > 150:
            return False
        
        # Términos que indican que NO es un producto
        invalid_terms = [
            'ver más', 'ver todo', 'comprar', 'añadir', 'agregar',
            'oferta', 'promoción', 'descuento', 'volver',
            'página', 'siguiente', 'anterior', 'mostrar', 'ordenar',
            'filtro', 'filtros', 'categoría', 'marca', 'buscar',
            'carrito', 'cuenta', 'login', 'iniciar', 'registrar'
        ]
        
        name_lower = name.lower()
        if any(term in name_lower for term in invalid_terms):
            return False
        
        # Debe tener al menos una letra
        return bool(re.search(r'[a-zA-ZáéíóúÁÉÍÓÚñÑ]', name))
    
    def scrape_all_products(self):
        """Scrapear productos - SOLO primera página de cada categoría/subcategoría"""
        logger.info("🚀 Iniciando scraping de productos (solo primera página)...")
        
        if not self.setup_driver():
            return False
        
        try:
            # Obtener categorías principales
            main_categories = self.find_main_categories()
            if not main_categories:
                logger.error("❌ No se encontraron categorías principales")
                return False
            
            logger.info(f"📂 Se procesarán {len(main_categories)} categorías principales")
            
            # Procesar cada categoría principal
            for i, category in enumerate(main_categories, 1):
                if category['url'] in self.processed_urls:
                    continue
                
                self.processed_urls.add(category['url'])
                logger.info(f"\n📦 [{i}/{len(main_categories)}] Procesando: {category['name']}")
                
                # Extraer productos de la categoría principal (primera página)
                products = self.extract_products_from_page(category)
                self.products_data.extend(products)
                
                # Buscar y procesar subcategorías (solo primera página de cada una)
                subcategories = self.find_subcategories(category)
                
                if subcategories:
                    logger.info(f"   📁 Encontradas {len(subcategories)} subcategorías")
                    
                    for j, subcategory in enumerate(subcategories, 1):
                        if subcategory['url'] in self.processed_urls:
                            continue
                        
                        self.processed_urls.add(subcategory['url'])
                        logger.info(f"      ↳ [{j}/{len(subcategories)}] {subcategory['name']}")
                        
                        # Extraer productos de la subcategoría (primera página)
                        sub_products = self.extract_products_from_page(subcategory)
                        self.products_data.extend(sub_products)
                        time.sleep(0.5)  # Pausa mínima entre subcategorías
                else:
                    logger.info("   📁 No se encontraron subcategorías")
                
                time.sleep(1)  # Pausa entre categorías principales
                
                # Mostrar progreso
                total_products = len(self.products_data)
                logger.info(f"   📊 Total acumulado: {total_products} productos")
            
            return len(self.products_data) > 0
            
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("🔚 Driver cerrado")
    
    def save_results(self, filename='jumbo_productos_single_page.csv'):
        """Guardar resultados en CSV"""
        if not self.products_data:
            logger.warning("⚠️ No hay productos para guardar")
            return
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['nombre', 'precio', 'categoria'])
                writer.writeheader()
                writer.writerows(self.products_data)
            
            logger.info(f"💾 Datos guardados en {filename}")
            print(f"\n✅ Resultados guardados en {filename}")
            print(f"📊 Total de productos: {len(self.products_data)}")
            
            # Estadísticas por categoría principal
            main_categories = Counter()
            for product in self.products_data:
                main_cat = product['categoria'].split('>')[0].strip()
                main_categories[main_cat] += 1
            
            print("\n📦 Productos por categoría principal:")
            for cat, count in main_categories.most_common():
                print(f"   {cat}: {count} productos")
                
            # Mostrar algunos ejemplos
            print("\n🔍 Ejemplos de productos encontrados:")
            for i, product in enumerate(self.products_data[:5], 1):
                print(f"   {i}. {product['nombre']} - {product['precio']} ({product['categoria']})")
            
        except Exception as e:
            logger.error(f"❌ Error guardando CSV: {e}")

def main():
    print("🛒 JUMBO.COM.DO - EXTRACTOR DE PRIMERA PÁGINA")
    print("=" * 60)
    print("🔍 Este script extraerá productos SOLO de la primera página")
    print("   de cada categoría y subcategoría encontrada.")
    print("   Sin paginación - Más rápido y eficiente.")
    print("=" * 60)
    
    # Configurar modo headless
    headless = True
    respuesta = input("¿Ejecutar en modo visible? (s/N): ").lower()
    if respuesta in ['s', 'si', 'sí']:
        headless = False
    
    # Ejecutar scraper
    start_time = time.time()
    scraper = JumboSinglePageScraper(headless=headless)
    
    print("\n🚀 Iniciando extracción...")
    if scraper.scrape_all_products():
        scraper.save_results()
        elapsed_time = time.time() - start_time
        print(f"\n⏱️  Tiempo total: {elapsed_time:.1f} segundos")
        print("🎉 ¡Proceso completado exitosamente!")
    else:
        print("❌ No se pudieron extraer productos")
    
    print("=" * 60)

if __name__ == "__main__":
    main()