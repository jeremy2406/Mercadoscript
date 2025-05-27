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
    
    def get_page_with_js(self, url, wait_seconds=20):
        """Cargar página y esperar que se renderice el JavaScript"""
        try:
            logger.info(f"🌐 Cargando página: {url}")
            self.driver.get(url)
            
            # Esperar más tiempo para que cargue completamente
            time.sleep(8)
            
            try:
                WebDriverWait(self.driver, wait_seconds).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
                
                # Scroll más agresivo para activar lazy loading
                for i in range(5):
                    self.driver.execute_script(f"window.scrollTo(0, {i * 500});")
                    time.sleep(1)
                
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)
                
                # Esperar específicamente por productos
                try:
                    WebDriverWait(self.driver, 10).until(
                        lambda driver: len(driver.find_elements(By.CSS_SELECTOR, 
                            "img[src*='product'], img[alt*='product'], .product, [data-product]")) > 0
                    )
                except TimeoutException:
                    logger.warning("⚠️ No se detectaron productos específicos, continuando...")
                
            except TimeoutException:
                logger.warning("⚠️ Timeout esperando carga completa, continuando...")
            
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            logger.info("✅ Página cargada y renderizada")
            return soup
            
        except Exception as e:
            logger.error(f"❌ Error cargando página {url}: {e}")
            return None
    
    def is_product_container(self, element):
        """Determinar si un elemento es un contenedor de producto"""
        element_text = element.get_text().lower()
        element_html = str(element).lower()
        
        # Criterios positivos (debe tener al menos uno)
        positive_indicators = [
            # Imágenes de productos
            element.find('img'),
            # Texto relacionado con productos
            any(term in element_text for term in [
                'nevera', 'refrigerador', 'lavadora', 'secadora', 'estufa', 'horno',
                'microondas', 'aire acondicionado', 'tv', 'televisor', 'samsung',
                'lg', 'whirlpool', 'mabe', 'frigidaire', 'electrolux', 'haier'
            ]),
            # Precios típicos (números grandes)
            re.search(r'(?:rd\$?\s*)?[\d,]{4,}(?:\.\d{2})?', element_text),
            # Estructura HTML típica de productos
            any(term in element_html for term in [
                'product', 'item', 'card', 'tile'
            ])
        ]
        
        # Criterios negativos (si tiene alguno, no es producto)
        negative_indicators = [
            element_text in ['', 'loading...', 'sirena', 'categorías'],
            len(element_text) < 10,
            'página ya no está disponible' in element_text,
            'lo sentimos' in element_text,
            element_text.isdigit() and len(element_text) == 4,  # Años
            any(term in element_text for term in [
                'copyright', '©', 'todos los derechos', 'política', 'términos',
                'newsletter', 'suscribir', 'síguenos', 'redes sociales'
            ])
        ]
        
        has_positive = any(positive_indicators)
        has_negative = any(negative_indicators)
        
        return has_positive and not has_negative
    
    def extract_product_name(self, element):
        """Extraer nombre del producto con mejor precisión"""
        # Priorizar elementos con características de nombres de productos
        name_candidates = []
        
        # 1. Buscar en títulos y headings
        for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            titles = element.find_all(tag)
            for title in titles:
                text = title.get_text(strip=True)
                if self.is_valid_product_name(text):
                    name_candidates.append((text, 3))  # Alta prioridad
        
        # 2. Buscar en enlaces y atributos title
        links = element.find_all('a', title=True)
        for link in links:
            title = link.get('title', '').strip()
            if self.is_valid_product_name(title):
                name_candidates.append((title, 3))
        
        # 3. Buscar en imágenes alt
        images = element.find_all('img', alt=True)
        for img in images:
            alt = img.get('alt', '').strip()
            if self.is_valid_product_name(alt):
                name_candidates.append((alt, 2))  # Prioridad media
        
        # 4. Buscar en clases específicas
        for class_name in ['product-name', 'name', 'title', 'product-title']:
            elements_by_class = element.find_all(class_=class_name)
            for elem in elements_by_class:
                text = elem.get_text(strip=True)
                if self.is_valid_product_name(text):
                    name_candidates.append((text, 2))
        
        # 5. Buscar texto que contenga marcas conocidas
        full_text = element.get_text()
        lines = [line.strip() for line in full_text.split('\n') if line.strip()]
        
        brand_keywords = [
            'samsung', 'lg', 'whirlpool', 'mabe', 'frigidaire', 'electrolux',
            'haier', 'sony', 'panasonic', 'toshiba', 'hisense', 'tcl'
        ]
        
        for line in lines:
            if (len(line) > 10 and len(line) < 150 and
                any(brand in line.lower() for brand in brand_keywords) and
                self.is_valid_product_name(line)):
                name_candidates.append((line, 1))  # Prioridad baja
        
        # Retornar el candidato con mayor prioridad
        if name_candidates:
            name_candidates.sort(key=lambda x: x[1], reverse=True)
            return name_candidates[0][0]
        
        return None
    
    def is_valid_product_name(self, text):
        """Validar si un texto es un nombre de producto válido"""
        if not text or len(text) < 8 or len(text) > 200:
            return False
        
        # Excluir textos que claramente no son productos
        invalid_patterns = [
            r'^\d{4}$',  # Solo año
            r'^rd\$',    # Solo precio
            r'^loading',  # Loading
            r'^ver\s',   # Ver más, etc.
            r'^click',   # Click here
            r'^buscar',  # Buscar
            r'^categorías?$',  # Categorías
            r'^productos?$',   # Productos
            r'^ofertas?$',     # Ofertas
        ]
        
        text_lower = text.lower()
        
        for pattern in invalid_patterns:
            if re.match(pattern, text_lower):
                return False
        
        # Debe contener al menos una letra
        if not re.search(r'[a-zA-Z]', text):
            return False
        
        # Excluir textos de UI
        ui_texts = [
            'lo sentimos', 'página no disponible', 'error', 'cargando',
            'newsletter', 'suscribir', 'síguenos', 'contacto', 'ayuda'
        ]
        
        if any(ui_text in text_lower for ui_text in ui_texts):
            return False
        
        return True
    
    def extract_price_from_text(self, text):
        """Extraer precio del texto con patrones mejorados"""
        # Patrones de precio más específicos para República Dominicana
        price_patterns = [
            r'RD\$\s*[\d,]+(?:\.\d{2})?',          # RD$ 45,999.00
            r'\$\s*[\d,]+(?:\.\d{2})?',            # $ 45,999.00
            r'[\d,]+\.\d{2}\s*(?:RD|pesos?)',      # 45,999.00 RD
            r'Precio:\s*RD\$?\s*[\d,]+(?:\.\d{2})?', # Precio: RD$ 45,999
            r'(?:^|\s)([\d,]{4,}(?:\.\d{2})?)(?:\s|$)',  # Números grandes aislados
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Validar que sea un precio razonable (entre 1,000 y 999,999)
                price_num = re.sub(r'[^\d.]', '', str(match))
                if price_num and '.' in price_num:
                    try:
                        price_val = float(price_num.replace(',', ''))
                        if 1000 <= price_val <= 999999:
                            return match if isinstance(match, str) else str(match)
                    except:
                        continue
                elif price_num and len(price_num) >= 4:
                    try:
                        price_val = int(price_num.replace(',', ''))
                        if 1000 <= price_val <= 999999:
                            return match if isinstance(match, str) else str(match)
                    except:
                        continue
        
        return ''
    
    def extract_products_from_page(self, soup, category_name, page_url):
        """Extraer productos usando estrategia mejorada"""
        products = []
        
        logger.info(f"🔍 Analizando página para productos reales...")
        
        # Estrategia 1: Buscar contenedores típicos de productos
        potential_containers = []
        
        # Selectores más específicos para productos
        selectors = [
            'div[class*="product"]',
            'div[class*="item"]', 
            'article',
            'div[class*="card"]',
            'li[class*="product"]',
            'div[data-product]',
            'div[data-item]'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            potential_containers.extend(elements)
        
        # También buscar divs que contengan imágenes + texto con precios
        all_divs = soup.find_all('div')
        for div in all_divs:
            if (div.find('img') and 
                len(div.get_text()) > 20 and 
                len(div.get_text()) < 500 and
                re.search(r'[\d,]{4,}', div.get_text())):
                potential_containers.append(div)
        
        logger.info(f"📦 Analizando {len(potential_containers)} contenedores potenciales...")
        
        # Filtrar y extraer productos
        for container in potential_containers:
            if self.is_product_container(container):
                product_name = self.extract_product_name(container)
                
                if product_name:
                    container_text = container.get_text()
                    price = self.extract_price_from_text(container_text)
                    
                    product = {
                        'nombre': product_name,
                        'precio': price or 'Precio no disponible',
                        'categoria': category_name
                    }
                    
                    products.append(product)
        
        # Eliminar duplicados basados en el nombre
        unique_products = []
        seen_names = set()
        
        for product in products:
            name_key = product['nombre'].lower().strip()
            if name_key not in seen_names:
                seen_names.add(name_key)
                unique_products.append(product)
        
        logger.info(f"✅ Productos únicos encontrados: {len(unique_products)}")
        
        return unique_products
    
    def find_real_categories(self, soup):
        """Encontrar categorías reales de productos"""
        categories = []
        
        # Buscar enlaces en menús de navegación
        nav_elements = soup.find_all(['nav', 'ul', 'div'], class_=lambda x: x and any(
            term in str(x).lower() for term in ['menu', 'nav', 'category', 'categoria']
        ))
        
        category_keywords = [
            'electrodomésticos', 'electrónicos', 'hogar', 'cocina', 'refrigeración',
            'lavado', 'climatización', 'audio', 'video', 'televisores', 'celulares',
            'computadoras', 'gaming', 'muebles', 'decoración', 'jardín'
        ]
        
        for nav in nav_elements:
            links = nav.find_all('a', href=True)
            for link in links:
                text = link.get_text(strip=True)
                href = link.get('href', '')
                
                # Verificar si es una categoría real
                if (len(text) > 3 and len(text) < 50 and
                    (any(keyword in text.lower() for keyword in category_keywords) or
                     '/categoria' in href.lower() or '/category' in href.lower())):
                    
                    full_url = urljoin(self.base_url, href) if href.startswith('/') else href
                    
                    if self.base_url in full_url:  # Solo URLs del mismo dominio
                        categories.append({
                            'name': text,
                            'url': full_url
                        })
        
        # Si no encuentra categorías específicas, buscar enlaces principales
        if len(categories) < 3:
            logger.info("🔍 Buscando categorías en enlaces principales...")
            main_links = soup.find_all('a', href=True)
            
            for link in main_links:
                text = link.get_text(strip=True)
                href = link.get('href', '')
                
                if (len(text) > 5 and len(text) < 30 and
                    not any(skip in text.lower() for skip in [
                        'inicio', 'home', 'contacto', 'ayuda', 'cuenta', 'carrito'
                    ])):
                    
                    full_url = urljoin(self.base_url, href) if href.startswith('/') else href
                    
                    if self.base_url in full_url:
                        categories.append({
                            'name': text,
                            'url': full_url
                        })
        
        # Eliminar duplicados
        unique_categories = []
        seen_urls = set()
        
        for cat in categories:
            if cat['url'] not in seen_urls:
                seen_urls.add(cat['url'])
                unique_categories.append(cat)
        
        return unique_categories[:10]  # Máximo 10 categorías
    
    def run_selenium_scraping(self):
        """Ejecutar scraping completo mejorado"""
        logger.info("🚀 Iniciando scraping mejorado de Sirena.do...")
        
        if not self.setup_driver():
            return False
        
        try:
            # Cargar página principal
            soup = self.get_page_with_js(self.base_url, wait_seconds=25)
            if not soup:
                logger.error("❌ No se pudo cargar la página principal")
                return False
            
            # Buscar productos en la página principal primero
            logger.info("🏠 Extrayendo productos de la página principal...")
            main_products = self.extract_products_from_page(soup, "Destacados", self.base_url)
            if main_products:
                self.products_data.extend(main_products)
                logger.info(f"✅ Página principal: {len(main_products)} productos")
            
            # Encontrar categorías reales
            categories = self.find_real_categories(soup)
            
            if not categories:
                logger.warning("⚠️ No se encontraron categorías específicas")
                # Intentar URLs comunes de categorías
                common_categories = [
                    {'name': 'Electrodomésticos', 'url': f"{self.base_url}electrodomesticos"},
                    {'name': 'Electrónicos', 'url': f"{self.base_url}electronicos"},
                    {'name': 'Hogar', 'url': f"{self.base_url}hogar"},
                    {'name': 'Cocina', 'url': f"{self.base_url}cocina"},
                ]
                categories = common_categories
            
            logger.info(f"📂 Procesando {len(categories)} categorías...")
            
            # Procesar cada categoría
            for i, category in enumerate(categories, 1):
                logger.info(f"🔄 [{i}/{len(categories)}] {category['name']}")
                
                try:
                    if category['url'] not in self.processed_urls:
                        self.processed_urls.add(category['url'])
                        
                        # Cargar página de categoría
                        cat_soup = self.get_page_with_js(category['url'], wait_seconds=20)
                        if cat_soup:
                            products = self.extract_products_from_page(cat_soup, category['name'], category['url'])
                            
                            if products:
                                self.products_data.extend(products)
                                logger.info(f"✅ {category['name']}: {len(products)} productos")
                            else:
                                logger.info(f"⚠️ No se encontraron productos en {category['name']}")
                        
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
    
    def save_to_csv(self, filename='sirena_productos_reales.csv'):
        """Guardar productos reales en CSV"""
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
    
    def print_sample_products(self):
        """Mostrar muestra de productos"""
        if not self.products_data:
            print("❌ No hay productos para mostrar")
            return
        
        print("\n📋 PRODUCTOS REALES EXTRAÍDOS:")
        print("=" * 80)
        
        # Mostrar productos
        for i, product in enumerate(self.products_data[:15], 1):
            print(f"{i}. {product['nombre']}")
            print(f"   💰 Precio: {product['precio']}")
            print(f"   📂 Categoría: {product['categoria']}")
            print("-" * 60)
        
        # Estadísticas
        category_counts = Counter(p['categoria'] for p in self.products_data)
        
        print(f"\n📊 ESTADÍSTICAS:")
        print("=" * 50)
        print(f"Total de productos: {len(self.products_data)}")
        for category, count in category_counts.items():
            print(f"📂 {category}: {count} productos")

def main():
    print("🤖 Sirena.do Scraper - Versión Productos Reales")
    print("=" * 60)
    print("✅ Mejoras implementadas:")
    print("   • Detección inteligente de productos reales")
    print("   • Filtrado de elementos de UI/navegación")
    print("   • Extracción mejorada de nombres y precios")
    print("   • Validación estricta de contenido")
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
        print(f"\n🎉 ¡SCRAPING DE PRODUCTOS REALES COMPLETADO!")
    else:
        print("❌ No se pudieron extraer productos")
    
    print("=" * 60)

if __name__ == "__main__":
    main()