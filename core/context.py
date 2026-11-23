"""Variables communes à toutes les pages."""

from django.conf import settings
from django.utils.safestring import mark_safe

from .render import icon_sprite

_SPRITE = mark_safe(icon_sprite())

# Icônes de l'interface : dessinées pour Demetra, même trait (1,6) et même grille (16) que les icônes de
# statut.
_UI = {
    "studies": '<path d="M2.5 4.5h4l1.2 1.5h5.8v6.5h-11z"/>',
    "guide": '<path d="M3 3h4a1.5 1.5 0 011.5 1.5V13A1.5 1.5 0 007 11.5H3zM13 3H9.8a1.3 1.3 0 00-1.3 '
    '1.3"/><path d="M8.5 13a1.5 1.5 0 011.5-1.5h3V3"/>',
    "bricks": '<rect x="2.5" y="3" width="5" height="4"/><rect x="8.5" y="3" width="5" height="4"/><rect '
    'x="5.5" y="9" width="5" height="4"/>',
    "key": '<circle cx="5.2" cy="10.8" r="2.7"/><path d="M7.2 8.8L13 3M10.6 5.4l1.8 1.8M9 7l1.3 1.3"/>',
    "sun": '<circle cx="8" cy="8" r="2.8"/><path d="M8 1.8v1.4M8 12.8v1.4M1.8 8h1.4M12.8 8h1.4M3.6 3.6l1 '
    '1M11.4 11.4l1 1M3.6 12.4l1-1M11.4 4.6l1-1"/>',
    "moon": '<path d="M13 9.6A5.6 5.6 0 016.4 3 5.6 5.6 0 1013 9.6z"/>',
    "logout": '<path d="M6.5 2.5h-3v11h3M10 5l3 3-3 3M13 8H6.5"/>',
    "search": '<circle cx="7" cy="7" r="4.2"/><path d="M10.2 10.2L13.5 13.5"/>',
    "prev": '<path d="M9.8 3.5L5.3 8l4.5 4.5"/>',
    "play": '<path d="M5 3.2v9.6L12.6 8z"/>',
    "pause": '<path d="M5.5 3.5v9M10.5 3.5v9"/>',
    "next": '<path d="M6.2 3.5L10.7 8l-4.5 4.5"/>',
    "to": '<path d="M2.5 8h10.5M9.2 4.2L13 8l-3.8 3.8"/>',
    "dock": '<rect x="2.5" y="3" width="11" height="10"/><path d="M6.3 3v10"/>',
    "up": '<path d="M3.5 9.8L8 5.3l4.5 4.5"/>',
    "down": '<path d="M3.5 6.2L8 10.7l4.5-4.5"/>',
    "accepted": '<circle cx="8" cy="8" r="6"/><path d="M5.2 8.2l2 2 3.6-4"/>',
    "rejected": '<circle cx="8" cy="8" r="6"/><path d="M5.8 5.8l4.4 4.4M10.2 5.8l-4.4 4.4"/>',
    "to_analyze": '<circle cx="8" cy="8" r="6" stroke-dasharray="2.4 2.4"/><circle cx="8" cy="8" r="1" '
    'fill="currentColor" stroke="none"/>',
    "comment": '<path d="M2.5 3.5h11v7h-6l-3 2.5v-2.5h-2z"/>',
    "focus": '<path d="M2.5 6V2.5H6M10 2.5h3.5V6M13.5 10v3.5H10M6 13.5H2.5V10"/>',
    "unfocus": '<path d="M6 2.5V6H2.5M13.5 6H10V2.5M10 13.5V10h3.5M2.5 10H6v3.5"/>',
    "people": '<circle cx="6" cy="5.5" r="2.3"/><path d="M1.8 13c.3-2.4 2-3.7 4.2-3.7s3.9 1.3 4.2 3.7M10.5 '
    '3.4a2.3 2.3 0 010 4.3M12 9.6c1.3.5 2.1 1.7 2.3 3.4"/>',
    "history": '<path d="M2.6 8a5.4 5.4 0 101.7-3.9L2.5 5.8M2.5 2.8v3h3M8 5.2V8l2 1.3"/>',
    "plus": '<path d="M8 3v10M3 8h10"/>',
    "copy": '<rect x="5.5" y="5.5" width="8" height="8" rx="1"/><path d="M10.5 5.5v-3h-8v8h3"/>',
    "changed": '<path d="M13.2 6.2A5.4 5.4 0 003.4 5M2.8 9.8A5.4 5.4 0 0012.6 11M3.2 2.4V5h2.6M12.8 '
    '13.6V11h-2.6"/>',
    "token": '<path d="M5.5 2v3M10.5 2v3M4 5h8v2.5a4 4 0 01-8 0zM8 11.5V14"/>',
    "human": '<circle cx="8" cy="5" r="2.6"/><path d="M2.8 13.6c.4-2.8 2.5-4.3 5.2-4.3s4.8 1.5 5.2 4.3"/>',
    "close": '<path d="M4 4l8 8M12 4l-8 8"/>',
    "menu": '<path d="M2.5 4.5h11M2.5 8h11M2.5 11.5h11"/>',
    "coverage": '<rect x="2.5" y="2.5" width="11" height="11"/><path d="M2.5 6.2h11M2.5 9.8h11M6.2 '
    '2.5v11M9.8 2.5v11"/>',
    "rep": '<circle cx="4.5" cy="4.5" r="2"/><rect x="9" y="9" width="4.5" height="4.5"/><path d="M6.5 '
    '4.5H11v4.5"/>',
    "settings": '<path d="M2.5 4.5h6M11.5 4.5h2M2.5 11.5h2M7.5 11.5h6"/><circle cx="10" cy="4.5" '
    'r="1.5"/><circle cx="6" cy="11.5" r="1.5"/>',
    "keyboard": '<rect x="1.8" y="4" width="12.4" height="8" rx="1"/><path d="M4.3 6.6h.1M6.8 6.6h.1M9.2 '
    '6.6h.1M11.7 6.6h.1M5 9.4h6"/>',
    "cases": '<path d="M2.5 4h1M5.5 4h8M2.5 8h1M5.5 8h8M2.5 12h1M5.5 12h8"/>',
    "retired": '<path d="M3 5h10M4.2 5l.6 8.5h6.4l.6-8.5M6.3 5V2.8h3.4V5"/>',
    "live": '<path d="M8.8 1.8L3.5 9h4l-.6 5.2L12.5 7h-4z"/>',
    "lock": '<rect x="3.6" y="7.2" width="8.8" height="6.2" rx="1.3"/><path d="M5.5 7.2V5.3a2.5 2.5 0 015 '
    '0v1.9"/>',
    "arrow": '<path d="M3 8h10M9.5 4.5L13 8l-3.5 3.5"/>',
    "warning": '<path d="M8 2.4l6.2 10.8H1.8z"/><path d="M8 6.5v3.3M8 11.3v.3"/>',
    "info": '<circle cx="8" cy="8" r="6"/><path d="M8 7.3v3.6M8 5v.3"/>',
    "admin": '<path d="M8 1.8l5.2 2v4c0 3.2-2.2 5.4-5.2 6.4-3-1-5.2-3.2-5.2-6.4v-4z"/><path d="M5.6 8.1l1.7 '
    '1.7 3.2-3.4"/>',
    "check": '<path d="M3 8.5l3.2 3.2L13 4.6"/>',
}
_UI_ICONS = [(key, mark_safe(body)) for key, body in _UI.items()]


def shell(request):
    return {
        "status_sprite": _SPRITE,
        "ui_icons": _UI_ICONS,
        "guide_version": settings.DEMETRA_GUIDE_VERSION,
        "signup_open": settings.ACCOUNT_SIGNUP_OPEN and settings.DEMETRA_PASSWORD_LOGIN,
        "sso_name": (settings.DEMETRA_OIDC or {}).get("name"),
        "password_login": settings.DEMETRA_PASSWORD_LOGIN,
        "ldap_login": settings.DEMETRA_LDAP,
    }
