"""Load signed local UI assets without depending on a loopback HTTP server."""
import base64
import re
import secrets
from pathlib import Path


def document(root):
    root=Path(root)
    html=(root/'index.html').read_text(encoding='utf-8')
    nonce=secrets.token_urlsafe(24)
    html=html.replace("script-src 'self'", "script-src 'nonce-"+nonce+"'")
    html=html.replace("style-src 'self'", "style-src 'nonce-"+nonce+"'")
    scripts=[]
    for name in ('i18n.js','assets/vendor/marked.js','assets/vendor/purify.js','assets/vendor/highlight.js','app.js'):
        pattern=r'<script\b[^>]*\bsrc="'+re.escape(name)+r'"[^>]*>\s*</script>'
        html,count=re.subn(pattern,'',html)
        if count!=1: raise ValueError('Missing or duplicated application script: '+name)
        source=(root/name).read_text(encoding='utf-8')
        source=re.sub(r'</script',r'<\\/script',source,flags=re.I)
        scripts.append('<script nonce="'+nonce+'">'+source+'</script>')
    for name in ('app.css','assets/vendor/atom-one-dark.css'):
        pattern=r'<link\b[^>]*\bhref="'+re.escape(name)+r'"[^>]*/?>'
        css=(root/name).read_text(encoding='utf-8')
        html,count=re.subn(pattern,lambda _: '<style nonce="'+nonce+'">'+css+'</style>',html)
        if count!=1: raise ValueError('Missing or duplicated application stylesheet: '+name)
    logo=base64.b64encode((root/'assets/brand/mark-dark.svg').read_bytes()).decode('ascii')
    html=html.replace('src="assets/brand/mark-dark.svg"','src="data:image/svg+xml;base64,'+logo+'"')
    # Inline scripts must run after the DOM exists; defer does not defer them.
    return html.replace('</body>','\n'.join(scripts)+'\n</body>')
