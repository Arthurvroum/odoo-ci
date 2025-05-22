import os
import jinja2
import yaml
from pathlib import Path


def load_template(template_name):
    """Charge un template depuis le dossier templates"""
    template_dir = Path(__file__).parent / 'templates'
    template_path = template_dir / template_name
    
    if not template_path.exists():
        raise FileNotFoundError(f"Template {template_name} introuvable dans {template_dir}")
    
    with open(template_path, 'r') as f:
        return f.read()


def render_with_yaml(template_str, context):
    """Rendu d'un template Jinja2 avec un contexte, résultat en YAML"""
    template = jinja2.Template(template_str)
    rendered = template.render(**context)
    
    # Conversion en objet YAML puis formatage correct
    yaml_obj = yaml.safe_load(rendered)
    return yaml.dump(yaml_obj, default_flow_style=False, sort_keys=False)


def render_template(template_name, context):
    """Charge et rend un template avec un contexte donné"""
    template_str = load_template(template_name)
    return jinja2.Template(template_str).render(**context)