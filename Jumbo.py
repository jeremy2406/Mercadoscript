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

class JumboFastScraper:
    def __init__(self, headless=True):
        self.base_url = "https://jumbo.com.do/"
        self.driver = None
        self.products_data = []
        self.headless = headless
        self.processed_urls = set()
        
        # Categorías principales objetivo
        self.target_categories = {
            "supermercado": ["supermercado", "mercado", "alimentos", "comida"],
            "belleza y salud": ["belleza", "salud", "cuidado personal", "higiene"],
            "hogar": ["hogar", "cocina", "limpieza", "muebles"],
            "electrodomésticos": ["electrodomésticos", "electrodomestico", "electro"],
            "ferretería": ["ferretería", "ferreteria", "herramientas"],
            "deportes": ["deportes", "fitness", "ejercicio"],
            "bebés": ["bebés", "bebes", "niños", "niñas"],
            "escolares y oficina": ["escolares", "oficina", "útiles", "libros"],
            "juguetería": ["juguetería", "juguetes", "juegos"]
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
            self.driver.implicitly_wait(5)  # Reducido para mayor velocidad
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
                WebDriverWait(self.driver, 10).until(  # Tiempo reducido
                    EC.presence_of_element_located((By.TAG_NAME, 'body'))
                )
                time.sleep(2)  # Menos tiempo de espera
                return BeautifulSoup(self.driver.page_source, 'html.parser')
            except Exception as e:
                logger.warning(f"⚠️ Intento {attempt + 1} fallido para {url}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(3)
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
            ('div', 'categories')
        ]
        
        for tag, class_part in nav_containers:
            elements = soup.find_all(tag, class_=lambda x: x and class_part in x.lower())
            for element in elements:
                for link in element.find_all('a', href=True):
                    name = link.get_text(strip=True)
                    url = link['href']
                    if self.is_target_category(name):
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
                if self.is_target_category(name):
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
            if cat['url'] not in seen_urls:
                seen_urls.add(cat['url'])
                unique_categories.append(cat)
                logger.info(f"✅ Categoría encontrada: {cat['name']}")
        
        return unique_categories
    
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
        return name.strip()
    
    def find_subcategories(self, category):
        """Buscar subcategorías con múltiples estrategias"""
        soup = self.get_page(category['url'])
        if not soup:
            return []
        
        subcategories = []
        
        # Estrategia 1: Buscar en sidebars
        sidebar = soup.find('div', class_=lambda x: x and ('sidebar' in x.lower() or 'filters' in x.lower()))
        if sidebar:
            for link in sidebar.find_all('a', href=True):
                name = link.get_text(strip=True)
                if name and not any(x in name.lower() for x in ['ver todo', 'ver más', 'volver', 'todo']):
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
            for section in category_sections:
                for link in section.find_all('a', href=True):
                    name = link.get_text(strip=True)
                    if name:
                        url = link['href']
                        full_url = urljoin(self.base_url, url)
                        subcategories.append({
                            'name': name,
                            'url': full_url,
                            'parent': category['name']
                        })
        
        # Eliminar duplicados
        unique_subcategories = []
        seen_urls = set()
        
        for sub in subcategories:
            if sub['url'] not in seen_urls:
                seen_urls.add(sub['url'])
                unique_subcategories.append(sub)
                logger.info(f"   ↳ Subcategoría encontrada: {sub['name']}")
        
        return unique_subcategories
    
    def extract_products_from_page(self, category):
        """Extraer productos directamente de la página de categoría"""
        soup = self.get_page(category['url'])
        if not soup:
            return []
        
        products = []
        
        # Identificar productos por múltiples patrones
        product_selectors = [
            ('div', 'product-item'), 
            ('div', 'product'),
            ('li', 'product'),
            ('div', 'item'),
            ('div', 'product-grid-item'),
            ('div', 'product-card')
        ]
        
        for tag, class_part in product_selectors:
            containers = soup.find_all(tag, class_=lambda x: x and class_part in x.lower())
            for container in containers:
                product = self.extract_product_data(container, category)
                if product:
                    products.append(product)
        
        # Si no encontramos con selectores, buscar por estructura
        if not products:
            grid_items = soup.select('[class*="grid"] > div, [class*="row"] > div')
            for item in grid_items:
                if item.find('img') and (item.find('h2') or item.find('h3')):
                    product = self.extract_product_data(item, category)
                    if product:
                        products.append(product)
        
        logger.info(f"📦 Encontrados {len(products)} productos en {category['name']}")
        return products
    
    def extract_product_data(self, container, category):
        """Extraer datos del producto desde el contenedor"""
        try:
            # Extraer nombre
            name = None
            name_elements = [
                container.find('h2'),
                container.find('h3'),
                container.find('div', class_=lambda x: x and 'name' in x.lower()),
                container.find('a', class_=lambda x: x and 'name' in x.lower())
            ]
            
            for elem in name_elements:
                if elem and elem.get_text(strip=True):
                    name = elem.get_text(strip=True)
                    break
            
            if not name and container.find('img', alt=True):
                name = container.find('img')['alt']
            
            if not name or not self.is_valid_product_name(name):
                return None
            
            # Extraer precio
            price = None
            price_elements = [
                container.find('span', class_=lambda x: x and 'price' in x.lower()),
                container.find('div', class_=lambda x: x and 'price' in x.lower()),
                container.find('p', class_=lambda x: x and 'price' in x.lower())
            ]
            
            for elem in price_elements:
                if elem and elem.get_text(strip=True):
                    price_text = elem.get_text(strip=True)
                    price = self.parse_price(price_text)
                    if price:
                        break
            
            # Construir categoría completa
            full_category = category['name']
            if category['parent']:
                full_category = f"{category['parent']} > {category['name']}"
            
            return {
                'nombre': name[:200],  # Limitar longitud
                'precio': price or 'Precio no disponible',
                'categoria': full_category
            }
        except Exception as e:
            logger.debug(f"Error extrayendo producto: {e}")
            return None
    
    def parse_price(self, price_text):
        """Parsear y formatear precio"""
        try:
            # Buscar el valor numérico
            match = re.search(r'(\d[\d,.]*)', price_text.replace(' ', ''))
            if not match:
                return None
            
            num_str = match.group(1).replace(',', '')
            price = float(num_str)
            
            # Validar rango razonable
            if 1 <= price <= 100000:
                return f"RD${price:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            return None
        except:
            return None
    
    def is_valid_product_name(self, name):
        """Validar que el nombre sea de un producto real"""
        if not name or len(name) < 4 or len(name) > 200:
            return False
        
        invalid_terms = [
            'ver más', 'ver todo', 'comprar', 'añadir', 'agregar',
            'oferta', 'promoción', 'descuento', 'nuevo', 'volver',
            'página', 'siguiente', 'anterior', 'mostrar', 'ordenar',
            'filtro', 'filtros', 'categoría', 'marca'
        ]
        
        name_lower = name.lower()
        return (not any(term in name_lower for term in invalid_terms) and bool(re.search(r'[a-zA-Z]', name)))
    
    def scrape_all_products(self):
        """Scrapear todos los productos de categorías y subcategorías"""
        logger.info("🚀 Iniciando scraping de productos...")
        
        if not self.setup_driver():
            return False
        
        try:
            # Obtener categorías principales
            main_categories = self.find_main_categories()
            if not main_categories:
                logger.error("❌ No se encontraron categorías principales")
                return False
            
            # Procesar cada categoría principal
            for category in main_categories:
                if category['url'] in self.processed_urls:
                    continue
                
                self.processed_urls.add(category['url'])
                logger.info(f"\n📦 Procesando categoría: {category['name']}")
                
                # Extraer productos de la categoría principal
                products = self.extract_products_from_page(category)
                self.products_data.extend(products)
                
                # Buscar y procesar subcategorías
                subcategories = self.find_subcategories(category)
                for subcategory in subcategories:
                    if subcategory['url'] in self.processed_urls:
                        continue
                    
                    self.processed_urls.add(subcategory['url'])
                    logger.info(f"   ↳ Procesando subcategoría: {subcategory['name']}")
                    
                    # Extraer productos de la subcategoría
                    sub_products = self.extract_products_from_page(subcategory)
                    self.products_data.extend(sub_products)
                    time.sleep(1)  # Pausa mínima
                
                time.sleep(2)  # Pausa entre categorías principales
            
            return len(self.products_data) > 0
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("🔚 Driver cerrado")
    
    def save_results(self, filename='jumbo_productos.csv'):
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
            
        except Exception as e:
            logger.error(f"❌ Error guardando CSV: {e}")

def main():
    print("🛒 JUMBO.COM.DO - EXTRACTOR RÁPIDO DE PRODUCTOS")
    print("=" * 60)
    print("🔍 Este script extraerá productos de las categorías principales")
    print("   sin entrar a páginas individuales de productos.")
    print("=" * 60)
    
    # Configurar modo headless
    headless = True
    respuesta = input("¿Ejecutar en modo visible? (s/N): ").lower()
    if respuesta in ['s', 'si', 'sí']:
        headless = False
    
    # Ejecutar scraper
    start_time = time.time()
    scraper = JumboFastScraper(headless=headless)
    
    if scraper.scrape_all_products():
        scraper.save_results()
        print(f"\n⏱️  Tiempo total: {time.time() - start_time:.1f} segundos")
        print("🎉 ¡Proceso completado exitosamente!")
    else:
        print("❌ No se pudieron extraer productos")
    
    print("=" * 60)

if __name__ == "__main__":
    main()