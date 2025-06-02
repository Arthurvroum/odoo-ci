#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour automatiser la création de fichiers docker-compose.yml 
pour différentes versions d'Odoo (Enterprise et Community),
avec téléchargement automatique du code Enterprise depuis odoo.com.

Cette version utilise une architecture modulaire avec des classes dédiées 
pour chaque responsabilité.
"""

import argparse
import sys
import os
from pathlib import Path

# Ajouter le dossier parent au chemin de recherche des modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importer les modules
from modules.templating import TemplateManager
from modules.odoo_versioning import OdooVersionManager
from modules.docker_compose import DockerComposeGenerator
from modules.odoo_config import OdooConfigManager
from modules.docker_manager import DockerManager
from modules.ui_logger import logger


def main():
    """
    Fonction principale qui gère les arguments en ligne de commande 
    et lance la génération des fichiers Docker Compose.
    """
    parser = argparse.ArgumentParser(description='Génère docker-compose pour Odoo avec support Enterprise amélioré')
    parser.add_argument('--version', required=True, help="Version d'Odoo (ex: 18)")
    parser.add_argument('--edition', choices=['enterprise','community'], default='community', 
                        help="Édition d'Odoo (enterprise ou community)")
    parser.add_argument('--port', type=int, default=8069, help="Port à exposer")
    parser.add_argument('--output-dir', help="Répertoire de sortie pour les fichiers générés")
    parser.add_argument('--addons-path', help="Chemin vers des addons externes ou Enterprise déjà téléchargés")
    parser.add_argument('--enterprise-token', help="Token d'accès pour l'édition Enterprise")
    parser.add_argument('--build', action='store_true', help="Construire et démarrer les conteneurs après génération")
    parser.add_argument('--configured', action='store_false', dest='fresh_install',
                        help="Configurer Odoo avec une DB prédéfinie (par défaut: installation fraîche)")
    
    args = parser.parse_args()
    
    # Vérifier le token si edition enterprise
    if args.edition.lower() == 'enterprise' and not args.enterprise_token and not args.addons_path:
        print("ATTENTION: L'édition Enterprise nécessite un token ou un chemin vers les addons déjà téléchargés.")
        if input("Continuer quand même? (o/N): ").lower() != 'o':
            return
    
    try:
        # Initialiser les gestionnaires
        template_manager = TemplateManager()
        odoo_version_manager = OdooVersionManager()
        odoo_config_manager = OdooConfigManager()
        
        # Créer le générateur Docker Compose
        docker_compose_generator = DockerComposeGenerator(
            base_output_dir=args.output_dir,
            template_manager=template_manager,
            odoo_version_manager=odoo_version_manager,
            odoo_config_manager=odoo_config_manager
        )
        
        # Générer les fichiers Docker Compose
        compose_file, db_name = docker_compose_generator.generate_docker_compose(
            args.version,
            args.edition,
            args.port,
            external_addons_path=args.addons_path,
            enterprise_token=args.enterprise_token,
            fresh_install=args.fresh_install
        )
        
        # Si demandé, construire et démarrer les conteneurs
        if args.build and compose_file:
            docker_manager = DockerManager()
            docker_manager.build_and_run(compose_file, db_name, fresh_install=args.fresh_install)
    
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
