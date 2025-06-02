#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module de génération des fichiers Docker Compose pour Odoo.
"""

import os
import re
import yaml
from pathlib import Path
from ..templating import TemplateManager
from ..odoo_config import OdooConfigManager
from ..odoo_versioning import OdooVersionManager


class DockerComposeGenerator:
    """
    Classe de génération des fichiers Docker Compose pour Odoo.
    """
    
    def __init__(self, base_output_dir=None, template_manager=None, odoo_version_manager=None, odoo_config_manager=None):
        """
        Initialise le générateur de Docker Compose.
        
        Args:
            base_output_dir (str, optional): Répertoire de sortie pour les fichiers générés.
            template_manager (TemplateManager, optional): Gestionnaire de templates.
            odoo_version_manager (OdooVersionManager, optional): Gestionnaire de versions d'Odoo.
            odoo_config_manager (OdooConfigManager, optional): Gestionnaire de configuration d'Odoo.
        """
        # Définir le dossier de sortie
        if base_output_dir:
            self.output_dir = Path(base_output_dir)
        else:
            # Utiliser le dossier 'docker-compose-files' dans le dossier parent du module
            module_path = Path(os.path.dirname(os.path.abspath(__file__)))
            self.output_dir = module_path.parent.parent / "docker-compose-files"
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialiser les gestionnaires
        self.template_manager = template_manager or TemplateManager()
        self.odoo_version_manager = odoo_version_manager or OdooVersionManager()
        self.odoo_config_manager = odoo_config_manager or OdooConfigManager()
    
    def generate_docker_compose(self, version, edition, port=8069, external_addons_path=None, enterprise_token=None, fresh_install=True):
        """
        Génère docker-compose.yml et télécharge le code Enterprise si demandé.
        
        Args:
            version (str): Version d'Odoo (ex: "18.0").
            edition (str): Edition ('enterprise' ou 'community').
            port (int): Port à exposer.
            external_addons_path (str, optional): Chemin vers des addons externes.
            enterprise_token (str, optional): Token pour l'édition Enterprise.
            fresh_install (bool): Si True, permet de configurer Odoo via l'interface web.
            
        Returns:
            tuple: (Path du fichier docker-compose.yml généré, nom de la base de données)
        """
        # Normaliser la version
        version = self.odoo_version_manager.normalize_version(version)
        
        # Déterminer si c'est l'édition Enterprise
        is_ee = edition.lower() == 'enterprise'
        
        # Créer le dossier d'instance
        name = f"odoo-{version}-{edition}"
        inst_dir = self._create_instance_directory(name)
        
        # Générer un nom de base de données unique pour cette instance
        db_name = self._generate_unique_db_name(version, edition, port, inst_dir)
        
        # Générer un nom de projet Docker Compose unique pour cette instance
        project_name = self._generate_project_name(version, edition, port, inst_dir)
        
        # Créer les sous-dossiers nécessaires
        dirs = self._create_subdirectories(inst_dir)
        
        # Créer le fichier de configuration d'Odoo
        self.odoo_config_manager.create_odoo_config(dirs['etc'], is_enterprise=is_ee, db_name=db_name, fresh_install=fresh_install)
        
        # Générer des noms de volumes uniques basés sur le nom du projet Docker Compose
        volume_names = self._generate_volume_names(project_name)
        
        # Préparer les volumes Docker
        vols = self._prepare_volumes(volume_names['odoo'])
        
        # Gérer les addons Enterprise ou externes
        enterprise_path = self._handle_addons(inst_dir, is_ee, version, enterprise_token, external_addons_path, vols)
        
        # Préparer les données pour le template
        template_data = self._prepare_template_data(version, edition, is_ee, port, db_name, 
                                                   project_name, volume_names, vols, enterprise_path)
        
        # Générer les fichiers à partir des templates
        docker_compose_path = self._generate_files(inst_dir, template_data, project_name)
        
        return docker_compose_path, db_name
    
    def _create_instance_directory(self, name):
        """
        Crée un dossier d'instance unique pour la configuration Docker Compose.
        
        Args:
            name (str): Nom de base du dossier.
            
        Returns:
            Path: Chemin vers le dossier d'instance créé.
        """
        inst = self.output_dir / name
        
        # Si le dossier existe déjà, ajouter un suffixe pour garantir l'unicité
        suffix = 1
        original_inst = inst
        while inst.exists():
            inst = original_inst.with_name(f"{original_inst.name}_{suffix}")
            suffix += 1
        
        inst.mkdir(parents=True, exist_ok=True)
        print(f"Création d'une nouvelle instance Odoo dans {inst}")
        
        return inst
    
    def _generate_unique_db_name(self, version, edition, port, inst_dir):
        """
        Génère un nom de base de données unique pour l'instance.
        
        Args:
            version (str): Version d'Odoo.
            edition (str): Edition d'Odoo.
            port (int): Port exposé.
            inst_dir (Path): Dossier d'instance.
            
        Returns:
            str: Nom de base de données unique.
        """
        # Extraire le suffixe du dossier d'instance s'il existe
        suffix_match = re.search(r'_(\d+)$', inst_dir.name)
        suffix = int(suffix_match.group(1)) if suffix_match else None
        
        db_name = f"odoo_{version.replace('.', '_')}_{edition}_{port}"
        if suffix:
            db_name = f"{db_name}_{suffix}"
        
        print(f"Base de données unique: {db_name}")
        return db_name
    
    def _generate_project_name(self, version, edition, port, inst_dir):
        """
        Génère un nom de projet Docker Compose unique.
        
        Args:
            version (str): Version d'Odoo.
            edition (str): Edition d'Odoo.
            port (int): Port exposé.
            inst_dir (Path): Dossier d'instance.
            
        Returns:
            str: Nom de projet unique.
        """
        # Extraire le suffixe du dossier d'instance s'il existe
        suffix_match = re.search(r'_(\d+)$', inst_dir.name)
        suffix = int(suffix_match.group(1)) if suffix_match else None
        
        project_name = f"odoo_{version.replace('.', '')}_{edition}_{port}"
        if suffix:
            project_name = f"{project_name}_{suffix}"
        
        return project_name
    
    def _create_subdirectories(self, inst_dir):
        """
        Crée les sous-dossiers requis pour l'instance.
        
        Args:
            inst_dir (Path): Dossier d'instance.
            
        Returns:
            dict: Dictionnaire des chemins des sous-dossiers.
        """
        dirs = {k: inst_dir / f"odoo-data/{k}" for k in ['addons', 'etc', 'filestore']}
        dirs['postgres'] = inst_dir / 'postgresql'
        # Créer un dossier custom-addons pour éviter l'erreur de montage dans Docker
        dirs['custom-addons'] = inst_dir / 'custom-addons'
        
        for d in dirs.values(): 
            d.mkdir(parents=True, exist_ok=True)
        
        return dirs
    
    def _generate_volume_names(self, project_name):
        """
        Génère des noms uniques pour les volumes Docker.
        
        Args:
            project_name (str): Nom du projet Docker Compose.
            
        Returns:
            dict: Dictionnaire des noms de volumes.
        """
        return {
            'odoo': f"{project_name}_odoo_data",
            'postgres': f"{project_name}_postgres_data"
        }
    
    def _prepare_volumes(self, odoo_volume_name):
        """
        Prépare la liste des volumes pour le montage Docker.
        
        Args:
            odoo_volume_name (str): Nom du volume Odoo.
            
        Returns:
            list: Liste des montages de volumes.
        """
        return [
            f'{odoo_volume_name}:/var/lib/odoo',
            './odoo-data/etc:/etc/odoo',
            './odoo-data/addons:/mnt/extra-addons:rw',
            './custom-addons:/mnt/custom-addons:rw'
        ]
    
    def _handle_addons(self, inst_dir, is_ee, version, enterprise_token, external_addons_path, vols):
        """
        Gère les addons Enterprise et externes.
        
        Args:
            inst_dir (Path): Dossier d'instance.
            is_ee (bool): True si édition Enterprise.
            version (str): Version d'Odoo.
            enterprise_token (str): Token d'accès Enterprise.
            external_addons_path (str): Chemin vers des addons externes.
            vols (list): Liste des montages de volumes à modifier.
            
        Returns:
            str: Chemin relatif des addons Enterprise, ou None.
        """
        enterprise_path = None
        
        if is_ee:
            if not enterprise_token and not external_addons_path:
                raise ValueError("Token requis pour l'édition Enterprise")
            
            # Créer le dossier enterprise au même niveau que docker-compose.yml
            enterprise_dir = inst_dir / "enterprise"
            enterprise_dir.mkdir(parents=True, exist_ok=True)
            
            # Ajouter le volume pour monter le dossier enterprise complet
            vols.append('./enterprise:/mnt/enterprise:ro')
            
            # Variable pour suivre si on a configuré les addons Enterprise
            enterprise_addons_configured = False
            
            if enterprise_token:
                if self.odoo_version_manager.download_enterprise_archive(version, enterprise_token, enterprise_dir):
                    print(f"Modules Enterprise téléchargés dans {enterprise_dir}")
                    enterprise_path, vols = self._configure_enterprise_addons(enterprise_dir, inst_dir, vols)
                    enterprise_addons_configured = (enterprise_path is not None)
                else:
                    print("AVERTISSEMENT: Le téléchargement Enterprise a échoué.")
            
            # Gestion du chemin d'addons externe (indépendamment du token Enterprise)
            if external_addons_path:
                self._configure_external_addons(external_addons_path, vols)
            elif not enterprise_addons_configured:
                # Si aucun addons externes et pas d'addons Enterprise, afficher un avertissement
                print("AVERTISSEMENT: Aucun chemin d'addons Enterprise configuré!")
        elif external_addons_path:
            self._configure_external_addons(external_addons_path, vols)
        
        return enterprise_path
    
    def _configure_enterprise_addons(self, enterprise_dir, inst_dir, vols):
        """
        Configure les montages pour les addons Enterprise.
        
        Args:
            enterprise_dir (Path): Dossier des addons Enterprise.
            inst_dir (Path): Dossier d'instance.
            vols (list): Liste des montages de volumes à modifier.
            
        Returns:
            tuple: (chemin relatif des addons Enterprise, liste des volumes mise à jour)
        """
        # Vérifier si le dossier odoo/addons existe dans le dossier enterprise
        addons_path = enterprise_dir / "odoo" / "addons"
        if addons_path.exists():
            # Monter le chemin spécifique vers odoo/addons
            vols.append('./enterprise/odoo/addons:/mnt/enterprise-addons:rw')
            enterprise_path = './enterprise/odoo/addons'
            print(f"Module Enterprise détecté dans {addons_path}, montage configuré")
        else:
            # Chercher les addons au premier niveau
            print("Structure odoo/addons non trouvée, recherche d'une structure alternative...")
            # Vérifier si des modules sont directement dans le dossier enterprise
            modules_direct = [f for f in enterprise_dir.glob("*/__manifest__.py")]
            if modules_direct:
                vols.append('./enterprise:/mnt/enterprise-addons:rw')
                enterprise_path = './enterprise'
                print(f"Modules Enterprise trouvés directement dans {enterprise_dir}, montage configuré")
            else:
                # Chercher tous les sous-dossiers qui pourraient contenir des addons
                potential_addons_dirs = [d for d in enterprise_dir.glob("**/addons") if d.is_dir()]
                if potential_addons_dirs:
                    # Prendre le premier trouvé
                    relative_path = os.path.relpath(potential_addons_dirs[0], inst_dir)
                    vols.append(f'./{relative_path}:/mnt/enterprise-addons:rw')
                    enterprise_path = f'./{relative_path}'
                    print(f"Dossier addons trouvé à {relative_path}, montage configuré")
                else:
                    print("AVERTISSEMENT: Aucun dossier addons trouvé dans l'archive Enterprise!")
                    # Monter quand même le dossier enterprise complet au cas où
                    vols.append('./enterprise:/mnt/enterprise-addons:rw')
                    enterprise_path = './enterprise'
        
        return enterprise_path, vols
    
    def _configure_external_addons(self, external_addons_path, vols):
        """
        Configure les montages pour les addons externes.
        
        Args:
            external_addons_path (str): Chemin vers les addons externes.
            vols (list): Liste des montages de volumes à modifier.
            
        Returns:
            list: Liste des volumes mise à jour.
        """
        path = Path(external_addons_path)
        if path.is_dir():
            print(f"Utilisation du chemin d'addons externe: {path}")
            # Remplacer le montage par défaut de custom-addons par le chemin externe
            custom_addons_index = next((i for i, v in enumerate(vols) if '/mnt/custom-addons' in v), None)
            if custom_addons_index is not None:
                vols[custom_addons_index] = f"{path.resolve()}:/mnt/custom-addons:rw"
            else:
                vols.append(f"{path.resolve()}:/mnt/custom-addons:rw")
            print(f"Addons externes montés depuis {path}")
        else:
            print(f"Warning: Le chemin d'addons externe '{path}' n'existe pas")
        
        return vols
    
    def _prepare_template_data(self, version, edition, is_ee, port, db_name, project_name, volume_names, vols, enterprise_path):
        """
        Prépare les données pour les templates.
        
        Args:
            version (str): Version d'Odoo.
            edition (str): Edition d'Odoo.
            is_ee (bool): True si édition Enterprise.
            port (int): Port exposé.
            db_name (str): Nom de la base de données.
            project_name (str): Nom du projet Docker Compose.
            volume_names (dict): Noms des volumes Docker.
            vols (list): Liste des montages de volumes.
            enterprise_path (str): Chemin des addons Enterprise.
            
        Returns:
            dict: Données pour les templates.
        """
        return {
            'odoo_version': version,
            'edition_name': edition.capitalize(),
            'is_enterprise': is_ee,
            'external_port': port,
            'db_name': db_name,
            'postgres_db': 'postgres',
            'postgres_user': 'odoo',
            'postgres_password': 'odoo',
            'postgres_volume': volume_names['postgres'],
            'odoo_volumes': vols,
            'odoo_command': '--config=/etc/odoo/odoo.conf',
            'volumes': {
                volume_names['odoo']: None,
                volume_names['postgres']: None
            },
            'enterprise_path': enterprise_path if is_ee else None,
            'project_name': project_name
        }
    
    def _generate_files(self, inst_dir, template_data, project_name):
        """
        Génère tous les fichiers nécessaires à partir des templates.
        
        Args:
            inst_dir (Path): Dossier d'instance.
            template_data (dict): Données pour les templates.
            project_name (str): Nom du projet Docker Compose.
            
        Returns:
            Path: Chemin vers le fichier docker-compose.yml généré.
        """
        try:
            # Générer le docker-compose.yml
            docker_compose_template = self.template_manager.load_template('docker-compose.yml.j2')
            docker_compose_content = self.template_manager.render_with_yaml(docker_compose_template, template_data)
            docker_compose_path = inst_dir / 'docker-compose.yml'
            with open(docker_compose_path, 'w') as f:
                f.write(docker_compose_content)
            
            # Générer le README.md
            readme_content = self.template_manager.render_template('README.md.j2', template_data)
            readme_path = inst_dir / 'README.md'
            with open(readme_path, 'w') as f:
                f.write(readme_content)
            
            # Créer un fichier .env pour définir le nom du projet Docker Compose
            env_file = inst_dir / '.env'
            with open(env_file, 'w') as f:
                f.write(f"COMPOSE_PROJECT_NAME={project_name}\n")
            
            # Créer un fichier .gitignore dans le dossier custom-addons
            try:
                gitignore_content = self.template_manager.load_template('custom-addons.gitignore.j2')
                gitignore_path = inst_dir / 'custom-addons' / '.gitignore'
                with open(gitignore_path, 'w') as f:
                    f.write(gitignore_content)
            except Exception as e:
                print(f"Note: Impossible de créer le fichier .gitignore pour custom-addons: {e}")
            
            # Générer le script list_modules.py
            try:
                list_modules_content = self.template_manager.render_template('list_modules.py.j2', template_data)
                list_modules_path = inst_dir / 'list_modules.py'
                with open(list_modules_path, 'w') as f:
                    f.write(list_modules_content)
                # Rendre le script exécutable
                os.chmod(list_modules_path, 0o755)
                print(f"Script de liste des modules créé: {list_modules_path}")
            except Exception as e:
                print(f"Note: Impossible de créer le script de liste des modules: {e}")
            
            print(f"Généré: {docker_compose_path}")
            volume_names = template_data['volumes'].keys()
            print(f"Volumes Docker uniques créés: {', '.join(volume_names)}")
            
            return docker_compose_path
        
        except Exception as e:
            print(f"Erreur lors de la génération des fichiers à partir des templates: {e}")
            import traceback
            traceback.print_exc()
            raise
