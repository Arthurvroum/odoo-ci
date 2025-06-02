#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module de gestion des templates pour la génération des fichiers de configuration.
"""

import os
import jinja2
import yaml
from pathlib import Path


class TemplateManager:
    """
    Classe de gestion des templates Jinja2.
    Permet de charger et de rendre des templates.
    """
    
    def __init__(self, templates_dir=None):
        """
        Initialise le gestionnaire de templates.
        
        Args:
            templates_dir (str, optional): Chemin vers le dossier des templates.
                                          Si None, utilise le dossier 'templates' dans le dossier parent.
        """
        if templates_dir:
            self.templates_dir = Path(templates_dir)
        else:
            # Utilise le dossier 'templates' dans le dossier racine du projet
            module_path = Path(os.path.dirname(os.path.abspath(__file__)))
            # Remonter deux niveaux: modules/templating -> modules -> racine
            self.templates_dir = module_path.parent.parent / 'templates'
        
        # S'assurer que le dossier des templates existe
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialiser l'environnement Jinja2
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.templates_dir)),
            autoescape=jinja2.select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def load_template(self, template_name):
        """
        Charge un template depuis le dossier des templates.
        
        Args:
            template_name (str): Nom du fichier template à charger.
            
        Returns:
            str: Contenu du template.
            
        Raises:
            FileNotFoundError: Si le template n'existe pas.
        """
        template_path = self.templates_dir / template_name
        
        if not template_path.exists():
            raise FileNotFoundError(f"Template {template_name} introuvable dans {self.templates_dir}")
        
        with open(template_path, 'r') as f:
            return f.read()
    
    def render_template(self, template_name, context):
        """
        Charge et rend un template avec un contexte donné.
        
        Args:
            template_name (str): Nom du fichier template à charger.
            context (dict): Variables à injecter dans le template.
            
        Returns:
            str: Template rendu avec les variables du contexte.
        """
        template_content = self.load_template(template_name)
        template = self.jinja_env.from_string(template_content)
        return template.render(**context)
    
    def render_with_yaml(self, template_str, context):
        """
        Rend un template Jinja2 avec un contexte et retourne le résultat formaté en YAML.
        
        Args:
            template_str (str): Contenu du template.
            context (dict): Variables à injecter dans le template.
            
        Returns:
            str: Template rendu et formaté en YAML.
        """
        template = self.jinja_env.from_string(template_str)
        rendered = template.render(**context)
        
        # Conversion en objet YAML puis formatage correct
        yaml_obj = yaml.safe_load(rendered)
        return yaml.dump(yaml_obj, default_flow_style=False, sort_keys=False)
    
    def ensure_default_templates(self):
        """
        Vérifie l'existence des templates par défaut.
        Cette méthode peut être étendue pour créer des templates par défaut si nécessaire.
        """
        # Liste des templates requis
        required_templates = [
            'docker-compose.yml.j2',
            'README.md.j2',
            'list_modules.py.j2',
            'custom-addons.gitignore.j2'
        ]
        
        missing_templates = []
        for template in required_templates:
            template_path = self.templates_dir / template
            if not template_path.exists():
                missing_templates.append(template)
        
        if missing_templates:
            template_list = ", ".join(missing_templates)
            raise FileNotFoundError(f"Les templates suivants sont manquants: {template_list}")
