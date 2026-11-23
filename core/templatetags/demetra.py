from django import template

register = template.Library()

TOKEN_VALUES = {
    "compact": "Compacte", "comfortable": "Confortable", "spacious": "Aérée",
    "sharp": "Vifs", "soft": "Adoucis", "round": "Arrondis",
    "full": "Complet", "short": "Abrégé", "hidden": "Masqué (icône seule)",
    "tint": "Teinté", "solid": "Plein", "outline": "Contour",
    "plain": "Uni", "grid": "Quadrillé", "dots": "Pointé",
}


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def token_label(value):
    return TOKEN_VALUES.get(value, value)
