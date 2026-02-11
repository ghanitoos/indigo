"""
Translation utility for loading localized strings.
"""
import json
import os
from flask import current_app, g

_translations = {}

def load_translations(lang='de'):
    """Load translations from JSON file."""
    global _translations
    if lang not in _translations:
        lang_file = os.path.join(current_app.root_path, 'translations', f'{lang}.json')
        try:
            if os.path.exists(lang_file):
                with open(lang_file, 'r', encoding='utf-8') as f:
                    _translations[lang] = json.load(f)
            else:
                current_app.logger.warning(f"Translation file not found: {lang_file}")
                _translations[lang] = {}
        except Exception as e:
            current_app.logger.error(f"Failed to load translations for {lang}: {e}")
            _translations[lang] = {}
    return _translations[lang]

def get_text(key_path, lang='de'):
    """
    Get translated text for a given key path (e.g., 'auth.login_title').
    
    Args:
        key_path (str): Dot-separated key path
        lang (str): Language code (default: 'de')
        
    Returns:
        str: Translated text or the key itself if not found
    """
    translations = load_translations(lang)
    keys = key_path.split('.')
    value = translations
    
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k)
        else:
            return key_path
            
    if value is None:
        return key_path
        
    return str(value)
