import requests
from bs4 import BeautifulSoup
import csv
import time
import logging
import re
from urllib.parse import urljoin, urlparse
import sys
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SirenaScraper:
    def __init__(self):
        self.base_url = "https://www.sirena.do/"
        self.session = self.create_session()
        self.products_data = []
        
    def create_session(self):
        """Crear sesión con reintentos y headers apropiados"""
        session = requests.Session()
        
        # Configurar reintentos
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Headers para parecer un navegador real
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-DO,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        return session
    
    def get_page(self, url):
        """Obtener contenido de una página con manejo de errores"""
        try:
            logger.info(f"Obteniendo página: {url}")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except requests.RequestException as e:
            logger.error(f"Error al obtener {url}: {e}")
            return None
    
    def extract_categories(self, soup):
        """Extraer categorías y subcategorías del menú principal"""
        categories = []
        
        # Debug: imprimir estructura HTML para análisis
        logger.info("Analizando estructura HTML...")
        
        # Selectores específicos para Sirena.do
        sirena_selectors = [
            # Selectores comunes para sitios de e-commerce dominicanos
            '.category-link',
            '.categoria',
            '.menu-categoria',
            '.departamento',
            '.section-link',
            # Selectores Bootstrap comunes
            '.navbar-nav a',
            '.nav-link',
            '.dropdown-item',
            # Selectores de menú lateral
            '.sidebar-menu a',
            '.side-menu a',
            '.menu-item a',
            # Selectores de navegación
            'nav a[href*="categoria"]',
            'nav a[href*="category"]',
            'nav a[href*="departamento"]',
            'a[href*="/c/"]',
            'a[href*="/cat/"]',
            'a[href*="/categoria/"]',
            # Mega menú
            '.mega-menu a',
            '.dropdown-menu a',
        ]
        
        menu_items = []
        
        # Intentar cada selector específico
        for selector in sirena_selectors:
            menu_items = soup.select(selector)
            if menu_items and len(menu_items) > 3:  # Al menos 3 categorías
                logger.info(f"Encontrado menú con selector: {selector} ({len(menu_items)} items)")
                break
        
        if not menu_items:
            # Análisis más profundo de la estructura
            logger.info("Analizando todos los enlaces para encontrar patrones...")
            all_links = soup.find_all('a', href=True)
            
            # Filtrar enlaces que podrían ser categorías
            potential_categories = []
            for link in all_links:
                href = link.get('href', '').lower()
                text = link.get_text(strip=True)
                
                # Patrones comunes en URLs de categorías
                category_patterns = [
                    '/categoria/', '/category/', '/cat/', '/c/',
                    '/departamento/', '/seccion/', '/productos/',
                    '/tienda/', '/shop/'
                ]
                
                if (text and len(text) > 2 and len(text) < 50 and
                    any(pattern in href for pattern in category_patterns)):
                    potential_categories.append(link)
            
            if potential_categories:
                menu_items = potential_categories
                logger.info(f"Encontradas {len(menu_items)} categorías potenciales por análisis de patrones")
            else:
                # Último recurso: buscar elementos del DOM que contengan listas de categorías
                logger.info("Buscando estructuras de navegación...")
                nav_elements = soup.find_all(['nav', 'ul', 'div'], 
                                           class_=lambda x: x and any(term in x.lower() for term in 
                                           ['menu', 'nav', 'categoria', 'category', 'sidebar']))
                
                for nav in nav_elements:
                    links = nav.find_all('a', href=True)
                    if len(links) > 2:  # Al menos 2 enlaces
                        menu_items.extend(links)
                        logger.info(f"Encontrados {len(links)} enlaces en elemento de navegación")
                
                if not menu_items:
                    logger.warning("No se encontraron categorías. Mostrando estructura HTML para debug...")
                    # Mostrar los primeros elementos para debug
                    nav_tags = soup.find_all(['nav', 'header'])[:3]
                    for i, tag in enumerate(nav_tags):
                        logger.info(f"Estructura {i+1}: {tag.name} - clases: {tag.get('class', [])}")
                        links = tag.find_all('a')[:5]
                        for link in links:
                            logger.info(f"  - Link: {link.get_text(strip=True)[:30]} -> {link.get('href', '')[:50]}")
        
        # Procesar enlaces encontrados
        for item in menu_items:
            href = item.get('href', '')
            text = item.get_text(strip=True)
            
            # Filtros más específicos para Sirena.do
            if (href and text and 
                len(text) > 1 and len(text) < 100 and
                not href.startswith('#') and 
                not href.startswith('javascript:') and
                not href.startswith('mailto:') and
                not href.startswith('tel:') and
                'contacto' not in text.lower() and
                'login' not in text.lower() and
                'carrito' not in text.lower() and
                'cuenta' not in text.lower() and
                'ayuda' not in text.lower()):
                
                full_url = urljoin(self.base_url, href)
                
                # Evitar URLs de la misma página
                if full_url != self.base_url.rstrip('/'):
                    categories.append({
                        'name': text,
                        'url': full_url
                    })
        
        # Eliminar duplicados y filtrar mejor
        seen_urls = set()
        unique_categories = []
        
        for cat in categories:
            url_key = cat['url'].lower().rstrip('/')
            if (url_key not in seen_urls and 
                len(cat['name']) > 2 and
                not any(skip in cat['name'].lower() for skip in 
                       ['facebook', 'twitter', 'instagram', 'whatsapp', 'youtube',
                        'términos', 'privacidad', 'políticas', 'sobre nosotros'])):
                seen_urls.add(url_key)
                unique_categories.append(cat)
        
        # Limitar a las primeras 20 categorías para evitar ruido
        unique_categories = unique_categories[:20]
        
        logger.info(f"Encontradas {len(unique_categories)} categorías únicas")
        
        # Mostrar las categorías encontradas para debug
        for cat in unique_categories[:10]:  # Mostrar primeras 10
            logger.info(f"Categoría: {cat['name']} -> {cat['url']}")
        
        return unique_categories
    
    def extract_products_from_page(self, soup, category_name):
        """Extraer productos de una página de categoría"""
        products = []
        
        # Selectores específicos para sitios de e-commerce dominicanos y Sirena.do
        product_selectors = [
            # Selectores comunes de productos
            '.product-item',
            '.product',
            '.item-product',
            '.product-card',
            '.producto',
            '.articulo',
            '[data-product]',
            '.grid-item',
            '.product-box',
            '.item-box',
            # Selectores de tarjetas de producto
            '.card.product',
            '.product-tile',
            '.product-thumb',
            '.item',
            # Selectores para sitios Bootstrap
            '.col .product',
            '.col-md-3',
            '.col-md-4',
            '.col-sm-6',
            # Selectores específicos de grids
            '.products-grid .item',
            '.catalog-item',
            '.shop-item',
        ]
        
        product_elements = []
        
        # Intentar selectores específicos primero
        for selector in product_selectors:
            product_elements = soup.select(selector)
            if product_elements and len(product_elements) > 2:
                logger.info(f"Productos encontrados con selector: {selector} ({len(product_elements)} items)")
                break
        
        if not product_elements:
            logger.info("Buscando productos con análisis más profundo...")
            
            # Buscar divs que contengan imágenes y precios (patrón común de productos)
            potential_products = []
            
            # Buscar contenedores que tengan imagen + precio
            containers = soup.find_all('div')
            for container in containers:
                has_image = container.find('img')
                has_price = container.find(text=lambda text: text and any(symbol in str(text) for symbol in 
                                          ['$', 'RD', 'pesos', 'DOP']))
                
                if has_image and has_price:
                    potential_products.append(container)
            
            if potential_products:
                product_elements = potential_products[:30]  # Limitar para evitar ruido
                logger.info(f"Encontrados {len(product_elements)} productos potenciales por análisis de imagen+precio")
            
            # Si aún no encuentra, buscar patrones de clase CSS
            if not product_elements:
                product_divs = soup.find_all('div', class_=lambda x: x and 
                    any(term in ' '.join(x).lower() for term in ['product', 'item', 'card', 'box', 'tile']))
                
                # Filtrar los que realmente parecen productos
                for div in product_divs:
                    if (div.find('img') and 
                        (div.find(text=lambda t: t and '$' in str(t)) or 
                         div.find(class_=lambda x: x and 'price' in str(x).lower()))):
                        product_elements.append(div)
                
                if product_elements:
                    logger.info(f"Encontrados {len(product_elements)} productos por análisis de clases CSS")
        
        if not product_elements:
            logger.warning(f"No se encontraron productos en la categoría: {category_name}")
            # Debug: mostrar estructura de la página
            logger.info("Mostrando elementos con imágenes para debug:")
            images = soup.find_all('img')[:5]
            for img in images:
                parent = img.parent
                logger.info(f"Imagen: {img.get('alt', 'sin alt')[:30]} - Padre: {parent.name} {parent.get('class', [])}")
            
            return products
        
        # Procesar productos encontrados
        for element in product_elements:
            try:
                product_data = self.extract_product_info(element, category_name)
                if product_data and product_data['nombre']:  # Solo agregar si tiene nombre
                    products.append(product_data)
            except Exception as e:
                logger.error(f"Error extrayendo producto: {e}")
                continue
        
        logger.info(f"Extraídos {len(products)} productos válidos de {category_name}")
        return products
    
    def extract_product_info(self, element, category_name):
        """Extraer información específica de un producto"""
        product = {
            'nombre': '',
            'precio': '',
            'categoria': category_name
        }
        
        # Extraer nombre del producto con selectores más específicos
        name_selectors = [
            # Selectores comunes para títulos de productos
            '.product-name',
            '.product-title',
            '.titulo',
            '.name',
            '.title',
            'h1', 'h2', 'h3', 'h4',
            # Selectores para enlaces de productos
            'a[href*="product"]',
            'a[href*="producto"]',
            'a[href*="/p/"]',
            'a[href*="/item/"]',
            # Selectores alternativos
            '.item-title',
            '.card-title',
            '.product-link',
            '[data-product-name]'
        ]
        
        name_found = False
        for selector in name_selectors:
            name_element = element.select_one(selector)
            if name_element:
                name_text = name_element.get_text(strip=True)
                if name_text and len(name_text) > 2:
                    product['nombre'] = name_text
                    name_found = True
                    break
        
        # Si no encuentra nombre con selectores, buscar el texto más largo que no sea precio
        if not name_found:
            all_text_elements = element.find_all(text=True)
            longest_text = ""
            
            for text in all_text_elements:
                clean_text = text.strip()
                # Evitar textos que parezcan precios
                if (clean_text and 
                    len(clean_text) > len(longest_text) and 
                    len(clean_text) > 5 and
                    not any(symbol in clean_text for symbol in ['$', 'RD', 'pesos', 'DOP']) and
                    not clean_text.replace('.', '').replace(',', '').isdigit()):
                    longest_text = clean_text
            
            if longest_text:
                product['nombre'] = longest_text[:100]  # Limitar longitud
        
        # Extraer precio con selectores más específicos
        price_selectors = [
            # Selectores comunes para precios
            '.price',
            '.precio',
            '.product-price',
            '.item-price',
            '.cost',
            '.amount',
            '.valor',
            '[data-price]',
            # Selectores específicos para moneda dominicana
            '.rd-price',
            '.peso-price',
            '.dop-price',
            # Selectores para precios en ofertas
            '.sale-price',
            '.special-price',
            '.current-price'
        ]
        
        price_found = False
        for selector in price_selectors:
            price_element = element.select_one(selector)
            if price_element:
                price_text = price_element.get_text(strip=True)
                if price_text:
                    # Limpiar y formatear precio
                    # Buscar patrones de precio (números con símbolos de moneda)
                    price_patterns = [
                        r'RD\$?\s*[\d,]+\.?\d*',
                        r'\$\s*[\d,]+\.?\d*',
                        r'[\d,]+\.?\d*\s*pesos?',
                        r'[\d,]+\.?\d*\s*DOP',
                        r'[\d,]+\.?\d*'
                    ]
                    
                    for pattern in price_patterns:
                        match = re.search(pattern, price_text, re.IGNORECASE)
                        if match:
                            product['precio'] = match.group().strip()
                            price_found = True
                            break
                    
                    if price_found:
                        break
        
        # Si no encuentra precio con selectores, buscar en todo el texto
        if not price_found:
            all_text = element.get_text()
            
            # Buscar patrones de precio en todo el texto
            price_patterns = [
                r'RD\$\s*[\d,]+\.?\d*',
                r'\$\s*[\d,]+\.?\d*',
                r'[\d,]+\.?\d*\s*pesos?',
                r'[\d,]+\.\d{2}'
            ]
            
            for pattern in price_patterns:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    product['precio'] = match.group().strip()
                    break
        
        # Solo devolver el producto si tiene al menos nombre
        if product['nombre'] and len(product['nombre']) > 2:
            # Limpiar nombre de caracteres especiales
            product['nombre'] = product['nombre'].replace('\n', ' ').replace('\t', ' ')
            product['nombre'] = ' '.join(product['nombre'].split())  # Normalizar espacios
            return product
        
        return None
    
    def scrape_categories(self):
        """Función principal para extraer datos de todas las categorías"""
        logger.info("Iniciando scraping de Sirena.do")
        
        # Obtener página principal
        main_soup = self.get_page(self.base_url)
        if not main_soup:
            logger.error("No se pudo obtener la página principal")
            return
        
        # Extraer categorías
        categories = self.extract_categories(main_soup)
        if not categories:
            logger.error("No se encontraron categorías")
            return
        
        # Procesar cada categoría
        for i, category in enumerate(categories, 1):
            logger.info(f"Procesando categoría {i}/{len(categories)}: {category['name']}")
            
            category_soup = self.get_page(category['url'])
            if category_soup:
                products = self.extract_products_from_page(category_soup, category['name'])
                self.products_data.extend(products)
            
            # Pausa entre requests para ser respetuoso
            time.sleep(1)
        
        logger.info(f"Scraping completado. Total productos: {len(self.products_data)}")
    
    def save_to_csv(self, filename='sirena_productos.csv'):
        """Guardar datos en archivo CSV"""
        if not self.products_data:
            logger.warning("No hay datos para guardar")
            return
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['nombre', 'precio', 'categoria']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for product in self.products_data:
                    writer.writerow(product)
            
            logger.info(f"Datos guardados en {filename}")
            print(f"✅ Archivo CSV creado exitosamente: {filename}")
            print(f"📊 Total de productos guardados: {len(self.products_data)}")
            
        except Exception as e:
            logger.error(f"Error guardando CSV: {e}")
    
    def run(self):
        """Ejecutar el scraper completo"""
        try:
            self.scrape_categories()
            self.save_to_csv()
        except KeyboardInterrupt:
            logger.info("Scraping interrumpido por el usuario")
        except Exception as e:
            logger.error(f"Error general: {e}")

def main():
    print("🚀 Iniciando scraper de Sirena.do")
    print("=" * 50)
    
    scraper = SirenaScraper()
    scraper.run()
    
    print("=" * 50)
    print("✨ Proceso completado")

if __name__ == "__main__":
    main()