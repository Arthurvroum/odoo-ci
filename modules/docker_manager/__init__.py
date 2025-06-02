#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module de gestion des conteneurs Docker pour Odoo.
"""

import os
import subprocess
import time
import yaml
from pathlib import Path

# Importer notre logger avec animation
from ..ui_logger import logger


class DockerManager:
    """
    Classe de gestion des conteneurs Docker pour Odoo.
    Permet de construire et d'exécuter les conteneurs Docker.
    """
    
    def __init__(self):
        """
        Initialise le gestionnaire Docker.
        """
        pass
    
    def build_and_run(self, compose_file, db_name, fresh_install=True):
        """
        Construit et démarre les conteneurs Docker.
        
        Args:
            compose_file (Path): Chemin vers le fichier docker-compose.yml.
            db_name (str): Nom de la base de données à utiliser.
            fresh_install (bool): Si True, ne pas initialiser la base de données.
            
        Returns:
            bool: True si les conteneurs ont démarré correctement, False sinon.
        """
        if not compose_file or not compose_file.exists():
            logger.error("Fichier docker-compose.yml non trouvé")
            return False
        
        # Créer une section pour le déploiement Docker
        logger.section(f"Déploiement des conteneurs Docker")
        
        # Extraire le nom du projet à partir du docker-compose.yml
        yaml_content = yaml.safe_load(compose_file.read_text())
        port = yaml_content['services']['odoo']['ports'][0].split(':')[0]
        
        # Générer le nom du projet à partir du yaml pour garantir l'unicité
        project_name = self._extract_project_name(yaml_content, compose_file)
        
        logger.docker(f"Utilisation du nom de projet Docker Compose: {project_name}")
        
        # Créer un fichier .env pour définir le nom du projet Docker Compose
        env_file = compose_file.parent / '.env'
        with open(env_file, 'w') as f:
            f.write(f"COMPOSE_PROJECT_NAME={project_name}\n")
        
        logger.info(f"Fichier .env créé avec COMPOSE_PROJECT_NAME={project_name}")
        
        os.chdir(compose_file.parent)
        try:
            # Construction des conteneurs
            logger.start_spinner(f"Construction des conteneurs depuis {compose_file}")
            process = subprocess.run(['docker-compose', 'up', '-d', '--build'], 
                                    stdout=subprocess.PIPE, 
                                    stderr=subprocess.PIPE, 
                                    check=True)
            logger.stop_spinner(success=True, message="Conteneurs construits et démarrés")
            
            # Attente avec animation
            wait_time = 10
            logger.start_spinner(f"Attente du démarrage complet des conteneurs ({wait_time} secondes)")
            for i in range(wait_time):
                time.sleep(1)
            logger.stop_spinner(success=True)
            
            # Vérifier si les conteneurs sont bien démarrés
            logger.start_spinner("Vérification de l'état des conteneurs")
            result = subprocess.run(['docker-compose', 'ps'], stdout=subprocess.PIPE, check=True)
            output = result.stdout.decode()
            
            if "Up" not in output:
                logger.stop_spinner(success=False, message="Les conteneurs ne semblent pas être démarrés correctement")
            else:
                logger.stop_spinner(success=True, message="Conteneurs démarrés avec succès")
            
            # En mode installation fraîche, ne pas initialiser la base de données
            # pour permettre l'affichage de l'écran de configuration initial
            if not fresh_install:
                logger.odoo(f"Initialisation de la base de données Odoo '{db_name}'...")
                # Utiliser le nom de base de données spécifique à cette instance
                try:
                    subprocess.run(
                        f"docker-compose exec -T odoo odoo -d {db_name} --stop-after-init -i base",
                        shell=True, check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    logger.success(f"Base de données '{db_name}' initialisée avec succès")
                except subprocess.CalledProcessError as e:
                    logger.error(f"Erreur lors de l'initialisation de la base de données: {e}")
            else:
                logger.odoo("Mode installation fraîche: Odoo va démarrer sans base de données préconfigurée")
                logger.info("Vous pourrez créer une nouvelle base de données via l'interface web")
            
            # Afficher les informations d'accès
            logger.section("Accès à l'instance Odoo")
            logger.success(f"Odoo accessible: http://localhost:{port}")
            if not fresh_install:
                logger.info(f"Base de données: {db_name}")
            
            # Afficher les commandes utiles
            logger.section("Commandes utiles")
            logger.info(f"Pour arrêter et supprimer uniquement cette instance, exécutez:")
            logger.info(f"cd {compose_file.parent} && docker-compose down -v")
            logger.info(f"Pour voir les logs en temps réel:")
            logger.info(f"cd {compose_file.parent} && docker-compose logs -f")
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Erreur lors du démarrage des conteneurs: {e}")
            return False
        except Exception as e:
            logger.error(f"Erreur inattendue: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _extract_project_name(self, yaml_content, compose_file):
        """
        Extrait le nom du projet Docker Compose à partir du contenu YAML.
        
        Args:
            yaml_content (dict): Contenu du fichier docker-compose.yml.
            compose_file (Path): Chemin vers le fichier docker-compose.yml.
            
        Returns:
            str: Nom du projet Docker Compose.
        """
        # Essayer d'extraire le nom du projet à partir des volumes
        volumes = yaml_content.get('volumes', {})
        for vol_name in volumes.keys():
            if vol_name.endswith('_odoo_data'):
                return vol_name.replace('_odoo_data', '')
        
        # Fallback: utiliser le nom du dossier parent
        return compose_file.parent.name.replace('-', '_').replace('.', '_')
