# recetas/utils.py
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
import html as html_lib
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation

import requests
from bs4 import BeautifulSoup

def analizar_y_limpiar_url(url_sucia):
    """Limpia los parámetros de seguimiento de la URL."""
    parsed = urlparse(url_sucia)
    dominio = parsed.netloc.lower()
    
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    params_a_excluir = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'fbclid', '_q']
    query_limpia = {k: v for k, v in query_params.items() if k not in params_a_excluir}
    
    nueva_query = urlencode(query_limpia, doseq=True)
    
    url_limpia = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        nueva_query,
        parsed.fragment
    ))
    
    return {
        "dominio": dominio,
        "url_limpia": url_limpia
    }


def probar_semaforo_url(url_limpia):
    """Hace un request real para comprobar si el sitio bloquea al bot o responde."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9",
    }

    try:
        response = requests.get(url_limpia, headers=headers, timeout=5)
        
        if response.status_code == 200:
            return {
                "semaforo": "VERDE 🟢",
                "codigo": 200,
                "mensaje": "¡Acceso exitoso! El sitio respondió correctamente."
            }
        elif response.status_code in [403, 401]:
            return {
                "semaforo": "ROJO 🔴",
                "codigo": response.status_code,
                "mensaje": "Acceso denegado (Bloqueo de seguridad / Cloudflare)."
            }
        else:
            return {
                "semaforo": "AMARILLO 🟡",
                "codigo": response.status_code,
                "mensaje": f"El servidor respondió con un código inusual ({response.status_code})."
            }

    except requests.exceptions.Timeout:
        return {
            "semaforo": "ROJO 🔴",
            "codigo": "Timeout",
            "mensaje": "La petición tardó demasiado en responder."
        }
    except requests.exceptions.RequestException as e:
        return {
            "semaforo": "ROJO 🔴",
            "codigo": "Error de Red",
            "mensaje": f"Ocurrió un error al conectar: {e}"
        }


# ---------------------------------------------------------------------------
# Extracción de datos del producto (JSON-LD + metadatos como respaldo)
# ---------------------------------------------------------------------------
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9",
}


def _datos_vacios():
    return {
        "nombre": None, "descripcion": None,
        "precio": None, "moneda": None, "precio_lista": None,
        "en_oferta": False, "oferta_hasta": None,
        "fuente": None, "error": None,
    }


def _limpiar_texto(texto):
    """Decodifica entidades, quita etiquetas HTML y colapsa espacios."""
    if not texto:
        return None
    texto = html_lib.unescape(str(texto))
    texto = BeautifulSoup(texto, "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", texto).strip() or None


def _a_decimal(valor):
    """Convierte 1234.5 / '1.234,50' / '$ 1,234.50' a Decimal; None si no se puede."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor))
    texto = re.sub(r"[^\d.,]", "", str(valor))
    if not texto:
        return None
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):          # 1.234,50
            texto = texto.replace(".", "").replace(",", ".")
        else:                                            # 1,234.50
            texto = texto.replace(",", "")
    elif texto.count(",") > 1:                           # 1,234,567
        texto = texto.replace(",", "")
    elif "," in texto:                                   # 1234,50
        texto = texto.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", texto):       # 1.234 (miles)
        texto = texto.replace(".", "")
    try:
        return Decimal(texto)
    except InvalidOperation:
        return None


def _a_fecha(valor):
    try:
        return date.fromisoformat(str(valor)[:10])
    except (ValueError, TypeError):
        return None


def _aplanar(data):
    if isinstance(data, list):
        for x in data:
            yield from _aplanar(x)
    elif isinstance(data, dict):
        yield data
        if "@graph" in data:
            yield from _aplanar(data["@graph"])


def _nodos_jsonld(soup):
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except (ValueError, TypeError):
            continue
        yield from _aplanar(data)


def _es_tipo(nodo, tipo):
    t = nodo.get("@type")
    return tipo in (t if isinstance(t, list) else [t])


def _extraer_oferta(offers):
    """(precio, moneda, precio_lista, valido_hasta) desde un Offer/AggregateOffer/lista."""
    if isinstance(offers, list):
        offers = next((o for o in offers if isinstance(o, dict)), None)
    if not isinstance(offers, dict):
        return None, None, None, None

    precio = _a_decimal(offers.get("price", offers.get("lowPrice")))
    moneda = offers.get("priceCurrency")
    lista = None

    specs = offers.get("priceSpecification") or []
    for spec in (specs if isinstance(specs, list) else [specs]):
        if not isinstance(spec, dict):
            continue
        tipo = str(spec.get("priceType", ""))
        valor = _a_decimal(spec.get("price"))
        if "ListPrice" in tipo or "Strikethrough" in tipo:
            lista = valor
        elif precio is None:
            precio = valor
        moneda = moneda or spec.get("priceCurrency")

    if precio is None and offers.get("offers"):            # AggregateOffer anidado
        return _extraer_oferta(offers["offers"])
    return precio, moneda, lista, offers.get("priceValidUntil")


def _meta(soup, *claves):
    for c in claves:
        tag = soup.find("meta", attrs={"property": c}) or soup.find("meta", attrs={"name": c})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


def _parsear_producto(html_texto):
    """Parsea el HTML y devuelve el diccionario de datos del producto."""
    soup = BeautifulSoup(html_texto, "html.parser")
    datos = _datos_vacios()
    hasta = None

    producto = next((n for n in _nodos_jsonld(soup) if _es_tipo(n, "Product")), None)
    if producto:
        datos["fuente"] = "json-ld"
        datos["nombre"] = _limpiar_texto(producto.get("name"))
        datos["descripcion"] = _limpiar_texto(producto.get("description"))
        datos["precio"], datos["moneda"], datos["precio_lista"], hasta = _extraer_oferta(producto.get("offers"))

    # Respaldo con metadatos Open Graph / microdatos
    if not datos["nombre"]:
        h1 = soup.find("h1")
        datos["nombre"] = _limpiar_texto(
            _meta(soup, "og:title", "twitter:title")
            or (h1.get_text() if h1 else None)
            or (soup.title.string if soup.title else None))
    if not datos["descripcion"]:
        datos["descripcion"] = _limpiar_texto(_meta(soup, "og:description", "description"))
    if datos["precio"] is None:
        bruto = _meta(soup, "product:price:amount", "og:price:amount")
        if bruto is None:
            tag = soup.find(attrs={"itemprop": "price"})
            bruto = (tag.get("content") or tag.get_text()) if tag else None
        datos["precio"] = _a_decimal(bruto)
        datos["moneda"] = datos["moneda"] or _meta(soup, "product:price:currency", "og:price:currency")
    if datos["fuente"] is None and (datos["precio"] is not None or datos["nombre"]):
        datos["fuente"] = "meta"

    # Oferta: solo se afirma si hay un precio de lista mayor al precio actual
    lista, precio = datos["precio_lista"], datos["precio"]
    datos["en_oferta"] = bool(lista and precio is not None and lista > precio)
    if datos["en_oferta"]:
        datos["oferta_hasta"] = _a_fecha(hasta)
    return datos


def extraer_datos_producto(url_limpia):
    """
    Descarga la página y extrae nombre, precio, descripción y estado de oferta.
    Devuelve siempre un diccionario; si algo falla, el motivo queda en datos["error"].
    """
    datos = _datos_vacios()
    try:
        r = requests.get(url_limpia, headers=_HEADERS, timeout=8)
        r.raise_for_status()
        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding
        datos = _parsear_producto(r.text)
    except requests.exceptions.RequestException as e:
        datos["error"] = f"No se pudo descargar la página: {e}"
        return datos
    except Exception as e:  # HTML inesperado
        datos["error"] = f"No se pudo interpretar la página: {e}"
        return datos

    if not datos["fuente"]:
        datos["error"] = "No se encontraron datos de producto (puede que el sitio los cargue con JavaScript)."
    return datos