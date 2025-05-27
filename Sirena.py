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
    
    def get_page_with_js(self, url, wait_seconds=10):
        """Cargar página y esperar que se renderice el JavaScript"""
        try:
            logger.info(f"🌐 Cargando página: {url}")
            self.driver.get(url)
            
            # Esperar que la página cargue
            time.sleep(3)
            
            # Intentar detectar cuando el contenido se ha cargado
            try:
                # Esperar por elementos que indiquen que la página se cargó
                WebDriverWait(self.driver, wait_seconds).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
                
                # Esperar un poco más por el contenido dinámico
                time.sleep(2)
                
                # Hacer scroll para activar lazy loading si existe
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(1)
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)
                
            except TimeoutException:
                logger.warning("⚠️ Timeout esperando carga completa, continuando...")
            
            # Obtener el HTML renderizado
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            logger.info("✅ Página cargada y renderizada")
            return soup
            
        except Exception as e:
            logger.error(f"❌ Error cargando página {url}: {e}")
            return None
    
    def analyze_spa_structure(self, soup):
        """Analizar la estructura de la SPA para entender cómo funciona"""
        logger.info("=== ANÁLISIS DE APLICACIÓN WEB (SPA) ===")
        
        # Buscar elementos que se cargan dinámicamente
        dynamic_elements = [
            "div[id*='app']", "div[id*='root']", "div[id*='main']",
            "div[class*='app']", "div[class*='container']", "div[class*='content']",
            "[ng-app]", "[data-react-root]", "[data-vue-root]"
        ]
        
        for selector in dynamic_elements:
            elements = soup.select(selector)
            if elements:
                logger.info(f"✅ Encontrado contenedor SPA: {selector} ({len(elements)} elementos)")
                for elem in elements[:3]:
                    classes = elem.get('class', [])
                    elem_id = elem.get('id', '')
                    logger.info(f"   - ID: {elem_id}, Clases: {classes}")
        
        # Analizar scripts para entender el framework
        scripts = soup.find_all('script')
        frameworks = {
            'React': ['react', 'jsx', 'ReactDOM'],
            'Vue': ['vue', 'v-', 'Vue.js'],
            'Angular': ['angular', 'ng-', '@angular'],
            'Next.js': ['next', '_next'],
            'Nuxt': ['nuxt', '_nuxt'],
            'jQuery': ['jquery', '$']
        }
        
        detected_frameworks = []
        for script in scripts:
            script_content = str(script)
            for framework, indicators in frameworks.items():
                if any(indicator.lower() in script_content.lower() for indicator in indicators):
                    if framework not in detected_frameworks:
                        detected_frameworks.append(framework)
        
        if detected_frameworks:
            logger.info(f"🔍 Frameworks detectados: {', '.join(detected_frameworks)}")
        
        # Buscar elementos de navegación después del renderizado
        nav_selectors = [
            'nav', 'header', '.navbar', '.navigation', '.menu',
            '.nav', '.header', '.top-bar', '.main-nav'
        ]
        
        total_nav_elements = 0
        for selector in nav_selectors:
            elements = soup.select(selector)
            if elements:
                total_nav_elements += len(elements)
                logger.info(f"📋 Navegación '{selector}': {len(elements)} elementos")
                
                # Mostrar contenido de navegación
                for i, elem in enumerate(elements[:2]):
                    links = elem.find_all('a', href=True)
                    if links:
                        logger.info(f"   Nav {i+1}: {len(links)} enlaces")
                        for link in links[:5]:
                            text = link.get_text(strip=True)
                            href = link.get('href')
                            if text and len(text) < 30:
                                logger.info(f"      → {text} ({href})")
        
        logger.info(f"📊 Total elementos de navegación encontrados: {total_nav_elements}")
        
        # Buscar contenido de productos
        product_indicators = soup.find_all(text=lambda t: t and 
            any(word in str(t).lower() for word in ['producto', 'product', 'precio', 'price', '$', 'rd']))
        
        logger.info(f"💰 Indicadores de productos encontrados: {len(product_indicators)}")
        
        # Buscar imágenes (productos suelen tener muchas imágenes)
        images = soup.find_all('img')
        logger.info(f"🖼️ Imágenes encontradas: {len(images)}")
        
        if images:
            product_images = [img for img in images if 
                any(term in (img.get('src', '') + img.get('alt', '')).lower() 
                    for term in ['product', 'producto', 'item'])]
            logger.info(f"🖼️ Imágenes que parecen productos: {len(product_images)}")
        
        logger.info("=== FIN ANÁLISIS SPA ===")
    
    def wait_for_dynamic_content(self, timeout=15):
        """Esperar que el contenido dinámico se cargue"""
        logger.info("⏳ Esperando contenido dinámico...")
        
        # Estrategias para detectar contenido cargado
        strategies = [
            # Esperar por enlaces de navegación
            (By.CSS_SELECTOR, "nav a, .navbar a, .menu a", "enlaces de navegación"),
            # Esperar por productos
            (By.CSS_SELECTOR, ".product, .item, [data-product]", "elementos de producto"),
            # Esperar por imágenes de productos
            (By.CSS_SELECTOR, "img[alt*='product'], img[src*='product']", "imágenes de productos"),
            # Esperar por precios
            (By.XPATH, "//*[contains(text(), '$') or contains(text(), 'RD') or contains(text(), 'precio')]", "elementos con precios")
        ]
        
        for by, selector, description in strategies:
            try:
                logger.info(f"🔍 Buscando {description}...")
                elements = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_all_elements_located((by, selector))
                )
                if elements:
                    logger.info(f"✅ Encontrados {len(elements)} {description}")
                    return True
            except TimeoutException:
                logger.info(f"⏳ No se encontraron {description} en {timeout}s")
                continue
        
        logger.warning("⚠️ No se detectó contenido dinámico específico, continuando...")
        return False
    
    def extract_categories_selenium(self):
        """Extraer categorías usando Selenium"""
        soup = self.get_page_with_js(self.base_url, wait_seconds=15)
        if not soup:
            return []
        
        # Analizar estructura SPA
        self.analyze_spa_structure(soup)
        
        # Esperar contenido dinámico
        self.wait_for_dynamic_content()
        
        # Obtener HTML actualizado después de esperar
        time.sleep(3)
        updated_html = self.driver.page_source
        soup = BeautifulSoup(updated_html, 'html.parser')
        
        logger.info("🔍 Extrayendo categorías del contenido renderizado...")
        
        # Selectores expandidos para SPA
        category_selectors = [
            # Selectores generales
            'nav a', 'header a', '.navbar a', '.menu a',
            '.navigation a', '.nav-link', '.menu-item a',
            # Selectores específicos de categorías
            'a[href*="categoria"]', 'a[href*="category"]',
            'a[href*="/c/"]', 'a[href*="/cat/"]',
            'a[href*="productos"]', 'a[href*="products"]',
            # Selectores de dropdown/menú
            '.dropdown-item', '.dropdown-menu a',
            '.mega-menu a', '.submenu a',
            # Selectores por contenido
            'a[title*="categoria"]', 'a[aria-label*="categoria"]'
        ]
        
        all_links = []
        
        # Recopilar enlaces con todos los selectores
        for selector in category_selectors:
            try:
                elements = soup.select(selector)
                if elements:
                    logger.info(f"🔗 Selector '{selector}': {len(elements)} enlaces")
                    for elem in elements:
                        href = elem.get('href', '')
                        text = elem.get_text(strip=True)
                        if href and text and len(text) > 1:
                            all_links.append({
                                'text': text,
                                'href': href,
                                'selector': selector
                            })
            except Exception as e:
                logger.debug(f"Error con selector {selector}: {e}")
        
        # Si no encuentra enlaces específicos, buscar TODOS los enlaces
        if not all_links:
            logger.info("🔍 Buscando TODOS los enlaces en la página renderizada...")
            all_page_links = soup.find_all('a', href=True)
            logger.info(f"🔗 Total enlaces encontrados: {len(all_page_links)}")
            
            for link in all_page_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                if href and text:
                    all_links.append({
                        'text': text,
                        'href': href,
                        'selector': 'all_links'
                    })
        
        logger.info(f"📊 Total enlaces recopilados: {len(all_links)}")
        
        # Mostrar muestra de enlaces
        logger.info("=== MUESTRA DE ENLACES ENCONTRADOS ===")
        for i, link in enumerate(all_links[:15]):
            logger.info(f"{i+1}. '{link['text'][:40]}' → {link['href'][:50]} [{link['selector']}]")
        
        # Filtrar y procesar enlaces
        categories = self.filter_category_links(all_links)
        
        logger.info(f"✅ Categorías finales encontradas: {len(categories)}")
        for i, cat in enumerate(categories[:10]):
            logger.info(f"{i+1}. {cat['name']} → {cat['url']}")
        
        return categories
    
    def filter_category_links(self, all_links):
        """Filtrar enlaces para encontrar categorías válidas"""
        categories = []
        
        # Filtros para categorías
        skip_terms = [
            'login', 'registro', 'sign', 'account', 'cuenta', 'perfil',
            'carrito', 'cart', 'checkout', 'pago', 'payment',
            'contacto', 'contact', 'about', 'acerca', 'nosotros',
            'ayuda', 'help', 'support', 'soporte', 'faq',
            'terminos', 'terms', 'privacidad', 'privacy', 'politicas',
            'facebook', 'twitter', 'instagram', 'youtube', 'whatsapp'
        ]
        
        category_indicators = [
            'categoria', 'category', 'departamento', 'seccion',
            'productos', 'products', 'tienda', 'shop', 'store'
        ]
        
        seen_urls = set()
        
        for link_data in all_links:
            text = link_data['text']
            href = link_data['href']
            
            # Filtros básicos
            if (not text or not href or 
                len(text) < 2 or len(text) > 100 or
                href.startswith('#') or 
                href.startswith('javascript:') or
                href.startswith('mailto:') or
                href.startswith('tel:')):
                continue
            
            # Filtrar términos no deseados
            if any(term in text.lower() for term in skip_terms):
                continue
            
            # Crear URL completa
            if href.startswith('/'):
                full_url = urljoin(self.base_url, href)
            elif href.startswith('http'):
                full_url = href
            else:
                full_url = urljoin(self.base_url, href)
            
            # Evitar duplicados
            url_key = full_url.lower().rstrip('/')
            if url_key in seen_urls or url_key == self.base_url.rstrip('/').lower():
                continue
            
            seen_urls.add(url_key)
            
            # Priorizar enlaces que parezcan categorías
            is_likely_category = (
                any(indicator in text.lower() for indicator in category_indicators) or
                any(indicator in href.lower() for indicator in category_indicators) or
                (len(text.split()) <= 4 and len(text) > 3)
            )
            
            categories.append({
                'name': text,
                'url': full_url,
                'priority': 1 if is_likely_category else 2
            })
        
        # Ordenar por prioridad y limitar
        categories.sort(key=lambda x: (x['priority'], len(x['name'])))
        return categories[:20]
    
    def extract_products_selenium(self, category_url, category_name):
        """Extraer productos de una categoría usando Selenium"""
        logger.info(f"🛒 Extrayendo productos de: {category_name}")
        
        soup = self.get_page_with_js(category_url, wait_seconds=10)
        if not soup:
            return []
        
        # Buscar productos con múltiples estrategias
        products = []
        
        # Estrategia 1: Selectores específicos
        product_selectors = [
            '.product', '.product-item', '.product-card',
            '.item', '.grid-item', '.catalog-item',
            '[data-product]', '[data-product-id]',
            '.card', '.shop-item'
        ]
        
        found_products = False
        for selector in product_selectors:
            elements = soup.select(selector)
            if elements and len(elements) > 2:
                logger.info(f"✅ Productos encontrados con '{selector}': {len(elements)}")
                
                for elem in elements[:30]:  # Limitar para evitar ruido
                    product_data = self.extract_product_info(elem, category_name)
                    if product_data:
                        products.append(product_data)
                
                found_products = True
                break
        
        # Estrategia 2: Análisis heurístico si no encuentra productos
        if not found_products:
            logger.info("🔍 Usando análisis heurístico para productos...")
            
            # Buscar elementos que contengan imágenes y precios
            all_divs = soup.find_all('div')
            for div in all_divs:
                has_image = div.find('img')
                has_price_text = div.find(text=lambda t: t and 
                    any(symbol in str(t) for symbol in ['$', 'RD', 'precio', 'price']))
                
                if has_image and has_price_text:
                    product_data = self.extract_product_info(div, category_name)
                    if product_data:
                        products.append(product_data)
        
        logger.info(f"📦 Productos extraídos de '{category_name}': {len(products)}")
        return products
    
    def extract_product_info(self, element, category_name):
        """Extraer información de un producto"""
        product = {
            'nombre': '',
            'precio': '',
            'categoria': category_name,
            'imagen': '',
            'enlace': ''
        }
        
        # Extraer nombre
        name_selectors = ['h1', 'h2', 'h3', 'h4', '.product-name', '.name', '.title', 'a']
        for selector in name_selectors:
            name_elem = element.select_one(selector)
            if name_elem:
                name_text = name_elem.get_text(strip=True)
                if name_text and 3 <= len(name_text) <= 150:
                    product['nombre'] = name_text
                    break
        
        # Extraer precio
        price_patterns = [
            r'RD\$\s*[\d,]+\.?\d*',
            r'\$\s*[\d,]+\.?\d*',
            r'[\d,]+\.\d{2}',
            r'[\d,]+\s*pesos?'
        ]
        
        element_text = element.get_text()
        for pattern in price_patterns:
            match = re.search(pattern, element_text, re.IGNORECASE)
            if match:
                product['precio'] = match.group().strip()
                break
        
        # Extraer imagen
        img_elem = element.find('img')
        if img_elem:
            img_src = img_elem.get('src') or img_elem.get('data-src')
            if img_src:
                product['imagen'] = urljoin(self.base_url, img_src)
        
        # Extraer enlace
        link_elem = element.find('a', href=True)
        if link_elem:
            href = link_elem.get('href')
            if href:
                product['enlace'] = urljoin(self.base_url, href)
        
        # Solo devolver si tiene nombre válido
        if product['nombre'] and len(product['nombre']) >= 3:
            return product
        
        return None
    
    def run_selenium_scraping(self):
        """Ejecutar scraping completo con Selenium"""
        logger.info("🚀 Iniciando scraping con Selenium...")
        
        if not self.setup_driver():
            return False
        
        try:
            # Extraer categorías
            categories = self.extract_categories_selenium()
            if not categories:
                logger.error("❌ No se encontraron categorías")
                return False
            
            # Procesar categorías
            for i, category in enumerate(categories, 1):
                logger.info(f"📂 [{i}/{len(categories)}] Procesando: {category['name']}")
                
                try:
                    products = self.extract_products_selenium(category['url'], category['name'])
                    self.products_data.extend(products)
                    
                    # Pausa entre categorías
                    time.sleep(3)
                    
                except Exception as e:
                    logger.error(f"❌ Error en categoría {category['name']}: {e}")
                    continue
            
            logger.info(f"🎉 Scraping completado. Total productos: {len(self.products_data)}")
            return True
            
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("🔚 Driver de Selenium cerrado")
    
    def save_to_csv(self, filename='sirena_productos_selenium.csv'):
        """Guardar productos en CSV"""
        if not self.products_data:
            logger.warning("⚠️ No hay productos para guardar")
            return
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['nombre', 'precio', 'categoria', 'imagen', 'enlace']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for product in self.products_data:
                    writer.writerow(product)
            
            logger.info(f"💾 Productos guardados en: {filename}")
            print(f"✅ Archivo creado: {filename}")
            print(f"📊 Total productos: {len(self.products_data)}")
            
        except Exception as e:
            logger.error(f"❌ Error guardando CSV: {e}")
    
    def print_sample_products(self):
        """Mostrar muestra de productos"""
        if not self.products_data:
            return
        
        print("\n📋 MUESTRA DE PRODUCTOS:")
        print("=" * 60)
        
        for i, product in enumerate(self.products_data[:5], 1):
            print(f"{i}. {product['nombre']}")
            print(f"   💰 {product['precio']}")
            print(f"   📂 {product['categoria']}")
            print("-" * 40)

def main():
    print("🤖 Sirena.do Scraper con Selenium")
    print("=" * 50)
    print("📋 Este scraper maneja contenido JavaScript dinámico")
    print("⚙️  Requiere: pip install selenium")
    print("🔧 Requiere: ChromeDriver instalado")
    print("=" * 50)
    
    # Preguntar si usar modo headless
    try:
        headless_input = input("¿Ejecutar en modo headless? (s/N): ").lower()
        headless = headless_input in ['s', 'y', 'yes', 'sí']
    except:
        headless = True
    
    scraper = SirenaSeleniumScraper(headless=headless)
    
    if scraper.run_selenium_scraping():
        scraper.print_sample_products()
        scraper.save_to_csv()
    else:
        print("❌ Error en el scraping. Revisa los logs.")
    
    print("=" * 50)
    print("✨ Proceso completado")

if __name__ == "__main__":
    main()