#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module de gestion de la configuration d'Odoo.
"""

import os
import configparser
from pathlib import Path


class OdooConfigManager:
    """
    Classe de gestion de la configuration d'Odoo.
    Permet de créer les fichiers de configuration pour différentes versions d'Odoo.
    """
    
    def __init__(self):
        """
        Initialise le gestionnaire de configuration d'Odoo.
        """
        pass
    
    def create_odoo_config(self, config_dir, is_enterprise=False, db_name='postgres', fresh_install=True):
        """
        Crée le fichier de configuration odoo.conf
        
        Args:
            config_dir (Path): Chemin vers le dossier de configuration.
            is_enterprise (bool): Si True, ajoute la configuration Enterprise.
            db_name (str): Nom de la base de données.
            fresh_install (bool): Si True, permet de configurer Odoo via l'interface web.
            
        Returns:
            Path: Chemin vers le fichier de configuration créé.
        """
        config_path = config_dir / 'odoo.conf'
        addons_path = '/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons'
        
        # Ajouter les chemins d'addons selon l'édition
        if is_enterprise:
            # Pour l'édition Enterprise, on pointe vers les différents chemins d'addons
            addons_path += ',/mnt/enterprise/odoo/addons,/mnt/enterprise-addons,/mnt/custom-addons'
        else:
            # Pour l'édition Community
            addons_path += ',/mnt/custom-addons'
        
        config = configparser.ConfigParser()
        config['options'] = {
            '; chemins addons': '',
            'addons_path': addons_path,
            '; DB': '',
            'db_host': 'db',
            'db_port': '5432',
            'db_user': 'odoo',
            'db_password': 'odoo',
            'http_port': '8069'
        }
        
        # Configuration spécifique selon le mode d'installation
        if fresh_install:
            # En mode installation fraîche, on permet la création de base de données
            config['options']['list_db'] = 'True'
            config['options']['admin_passwd'] = 'admin'  # Mot de passe master pour créer des BDs
            # Ne pas spécifier de db_name pour afficher la page de création de BD
        else:
            # Mode préconfigué
            config['options']['admin_passwd'] = 'admin'
            config['options']['db_name'] = db_name
        
        with open(config_path, 'w') as f:
            config.write(f)
        
        return config_path
