#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour automatiser la création de fichiers docker-compose.yml 
pour différentes versions d'Odoo (Enterprise et Community),
avec téléchargement automatique du code Enterprise depuis odoo.com.
"""

import os
import argparse
import yaml
import requests
import re
import subprocess
import time
import tarfile
import socket
from pathlib import Path
from bs4 import BeautifulSoup
import configparser
import jinja2


class OdooDockerGenerator:
    """
    Génère des fichiers docker-compose.yml pour Odoo
    et télécharge/extrait automatiquement l'édition Enterprise
    depuis odoo.com via votre token.
    """

    DOWNLOAD_PAGE_URL = "https://www.odoo.com/fr_FR/page/download"
    THANKS_URL_FORMAT = "https://www.odoo.com/fr_FR/thanks/download?code={token}&platform_version=src_{version}e"

    def __init__(self, base_output_dir=None):
        self.base_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        self.output_dir = Path(base_output_dir) if base_output_dir else self.base_dir / "docker-compose-files"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Créer un répertoire cache pour stocker les archives téléchargées
        self.cache_dir = self.base_dir / "enterprise_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        print(f"Dossier cache pour les archives Enterprise: {self.cache_dir}")
        
        # Configuration du moteur de template Jinja2
        self.templates_dir = self.base_dir / "templates"
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.templates_dir)),
            autoescape=jinja2.select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Créer les templates par défaut s'ils n'existent pas
        self._ensure_default_templates()
    
    def _ensure_default_templates(self):
        """Crée les templates par défaut s'ils n'existent pas"""
        # Ne plus créer de templates par défaut dans le code
        # Les templates sont maintenant dans des fichiers dédiés
        pass

    def _create_odoo_config(self, config_dir, is_enterprise=False, db_name='postgres', fresh_install=True):
        """
        Crée le fichier de configuration odoo.conf
        
        Args:
            config_dir: Chemin vers le dossier de configuration
            is_enterprise: Si True, ajoute la configuration Enterprise
            db_name: Nom de la base de données
            fresh_install: Si True, permet de configurer Odoo via l'interface web
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

    def _download_enterprise_archive(self, version: str, token: str, target_dir: Path, browser_fallback=False):
        """
        Télécharge et extrait l'archive Enterprise pour la version depuis odoo.com.
        Utilise le cache si disponible pour éviter les téléchargements redondants.
        
        Args:
            version: Version d'Odoo (ex: "18.0")
            token: Token d'accès Enterprise
            target_dir: Répertoire où extraire l'archive
            browser_fallback: Paramètre conservé pour compatibilité mais ignoré
            
        Returns:
            bool: True si le téléchargement/extraction a réussi, False sinon
        """
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Vérifier si cette version est déjà en cache
        cached_archive_path = self.cache_dir / f"odoo-enterprise-{version}.tar.gz"
        if cached_archive_path.exists():
            print(f"Archive Odoo Enterprise {version} trouvée dans le cache ({cached_archive_path})")
            print(f"Extraction de l'archive depuis le cache vers {target_dir}...")
            try:
                # Extraire depuis le cache
                with tarfile.open(cached_archive_path, 'r:gz') as tar:
                    # Extraire le contenu directement dans le répertoire cible
                    members = tar.getmembers()
                    # Si l'archive a un dossier racine (comme "enterprise"), extraire son contenu
                    root_dirs = {m.name.split('/')[0] for m in members if '/' in m.name}
                    if len(root_dirs) == 1:
                        # Extraire en ignorant le dossier racine
                        top_dir = next(iter(root_dirs))
                        print(f"Extraction du contenu du dossier {top_dir} directement dans {target_dir}")
                        for m in members:
                            if m.name.startswith(f"{top_dir}/"):
                                # Renommer pour ignorer le dossier racine
                                m.name = m.name[len(top_dir)+1:]
                                # Ne pas extraire les dossiers vides
                                if m.name:
                                    tar.extract(m, path=target_dir)
                    else:
                        # Extraire directement
                        tar.extractall(path=target_dir)
                print(f"Extraction depuis le cache réussie dans {target_dir}")
                return True
            except Exception as e:
                print(f"Erreur lors de l'extraction depuis le cache: {e}")
                # Continuer avec le téléchargement en ligne en cas d'erreur
        
        # Si pas en cache ou extraction échouée, télécharger
        # Version courte pour les URLs
        short_version = version.replace('.0', '')
        
        # URL de la page de remerciement (qui contient le lien direct)
        thanks_url = self.THANKS_URL_FORMAT.format(token=token, version=short_version)
        
        print(f"Téléchargement d'Odoo Enterprise {version}...")
        print(f"Récupération de la page de téléchargement ({thanks_url})...")
        
        try:
            # Étape 1: Récupérer la page de remerciement
            response = requests.get(thanks_url)
            response.raise_for_status()
            html_content = response.text
            
            # Étape 2: Extraire l'URL directe de téléchargement
            direct_url = None
            
            # Méthode 1: Chercher une URL complète
            url_match = re.search(r'https://download\.odoocdn\.com/download/[^"\'&\s]+', html_content)
            if url_match:
                direct_url = url_match.group(0)
                print(f"URL directe trouvée: {direct_url}")
            
            # Méthode 2: Chercher un payload
            if not direct_url:
                payload_match = re.search(r'payload=([^"\'&\s]+)', html_content)
                if payload_match:
                    payload = payload_match.group(1)
                    direct_url = f"https://download.odoocdn.com/download/{short_version}e/src?payload={payload}"
                    print(f"URL avec payload construite: {direct_url}")
            
            # Si on a trouvé une URL directe, télécharger
            if direct_url:
                print(f"Téléchargement de l'archive depuis l'URL directe...")
                download_response = requests.get(direct_url, stream=True)
                download_response.raise_for_status()
                
                # Vérifier que ce n'est pas une réponse HTML
                content_type = download_response.headers.get('Content-Type', '')
                if 'text/html' in content_type:
                    print("ERREUR: Le serveur a renvoyé une page HTML au lieu de l'archive.")
                    with open(target_dir / "error_response.html", 'wb') as f:
                        f.write(download_response.content)
                    return False
                
                # Télécharger le fichier
                total_size = int(download_response.headers.get('Content-Length', 0))
                print(f"Taille de l'archive: {total_size/1024/1024:.1f} MB")
                
                # Télécharger dans le cache d'abord
                with open(cached_archive_path, 'wb') as f:
                    for chunk in download_response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                print(f"Archive téléchargée et mise en cache dans {cached_archive_path}")
                
                # Extraire l'archive depuis le cache vers le dossier cible
                try:
                    print(f"Extraction de l'archive vers {target_dir}...")
                    with tarfile.open(cached_archive_path, 'r:gz') as tar:
                        # Extraire le contenu directement dans le répertoire cible
                        members = tar.getmembers()
                        # Si l'archive a un dossier racine (comme "enterprise"), extraire son contenu
                        root_dirs = {m.name.split('/')[0] for m in members if '/' in m.name}
                        if len(root_dirs) == 1:
                            # Extraire en ignorant le dossier racine
                            top_dir = next(iter(root_dirs))
                            print(f"Extraction du contenu du dossier {top_dir} directement dans {target_dir}")
                            for m in members:
                                if m.name.startswith(f"{top_dir}/"):
                                    # Renommer pour ignorer le dossier racine
                                    m.name = m.name[len(top_dir)+1:]
                                    # Ne pas extraire les dossiers vides
                                    if m.name:
                                        tar.extract(m, path=target_dir)
                        else:
                            # Extraire directement
                            tar.extractall(path=target_dir)
                    print(f"Extraction réussie dans {target_dir}")
                    return True
                except Exception as e:
                    print(f"Erreur lors de l'extraction: {e}")
                    return False
            else:
                print("Impossible de trouver l'URL directe dans la page.")
        except Exception as e:
            print(f"Erreur lors du téléchargement: {e}")
        
        print("\nLes méthodes automatiques de téléchargement ont échoué.")
        print(f"Conseil: Téléchargez manuellement Odoo Enterprise {version} depuis le site d'Odoo")
        print(f"puis utilisez l'option --addons-path pour spécifier l'emplacement.")
        
        return False

    def generate_docker_compose(self, version, edition,
                              port=8069, external_addons_path=None,
                              enterprise_token=None, fresh_install=True):
        """
        Génère docker-compose.yml et télécharge le code Enterprise si demandé.
        
        Args:
            version: Version d'Odoo (ex: "18.0")
            edition: Edition ('enterprise' ou 'community')
            port: Port à exposer
            external_addons_path: Chemin vers des addons externes
            enterprise_token: Token pour l'édition Enterprise
            fresh_install: Si True, permet de configurer Odoo via l'interface web
            
        Returns:
            Path: Chemin vers le fichier docker-compose.yml généré
        """
        # Normaliser la version
        if not version.endswith('.0'):
            version = f"{version}.0"
        
        is_ee = edition.lower() == 'enterprise'
        
        # Créer le dossier d'instance
        name = f"odoo-{version}-{edition}"
        inst = self.output_dir / name
        
        # Générer un nom de base de données unique pour cette instance
        # en utilisant la version, l'édition et le port
        db_name = f"odoo_{version.replace('.', '_')}_{edition}_{port}"
        
        # Si le dossier existe déjà, ajouter un suffixe pour garantir l'unicité
        suffix = 1
        original_inst = inst
        while inst.exists():
            inst = original_inst.with_name(f"{original_inst.name}_{suffix}")
            db_name = f"odoo_{version.replace('.', '_')}_{edition}_{port}_{suffix}"
            suffix += 1
        
        inst.mkdir(parents=True, exist_ok=True)
        print(f"Création d'une nouvelle instance Odoo dans {inst}")
        print(f"Base de données unique: {db_name}")
        
        # Générer un nom de projet Docker Compose unique pour cette instance
        # pour isoler complètement les réseaux et volumes
        project_name = f"odoo_{version.replace('.', '')}_{edition}_{port}"
        if suffix > 1:
            project_name = f"{project_name}_{suffix}"
        
        # Créer les sous-dossiers
        dirs = {k: inst / f"odoo-data/{k}" for k in ['addons', 'etc', 'filestore']}
        dirs['postgres'] = inst / 'postgresql'
        # Créer un dossier custom-addons pour éviter l'erreur de montage dans Docker
        dirs['custom-addons'] = inst / 'custom-addons'
        for d in dirs.values(): 
            d.mkdir(parents=True, exist_ok=True)
        
        # Créer le fichier de configuration avec le nom de la DB
        # Si fresh_install est True, ne pas spécifier de DB ni de mot de passe admin
        self._create_odoo_config(dirs['etc'], is_enterprise=is_ee, db_name=db_name, fresh_install=fresh_install)
        
        # Générer des noms de volumes uniques basés sur le nom du projet Docker Compose
        odoo_volume_name = f"{project_name}_odoo_data"
        postgres_volume_name = f"{project_name}_postgres_data"
        
        # Préparer les volumes
        vols = [
            f'{odoo_volume_name}:/var/lib/odoo',
            './odoo-data/etc:/etc/odoo',
            './odoo-data/addons:/mnt/extra-addons:rw',
            './custom-addons:/mnt/custom-addons:rw'  # Monter le dossier custom-addons par défaut
        ]
        
        # Gérer les addons Enterprise ou externes
        enterprise_path = None
        if is_ee:
            if not enterprise_token and not external_addons_path:
                raise ValueError("Token requis pour l'édition Enterprise")
            
            # Créer le dossier enterprise au même niveau que docker-compose.yml
            enterprise_dir = inst / "enterprise"
            enterprise_dir.mkdir(parents=True, exist_ok=True)
            
            # Ajouter le volume pour monter le dossier enterprise complet
            vols.append('./enterprise:/mnt/enterprise:ro')
            
            # Variable pour suivre si on a configuré les addons Enterprise
            enterprise_addons_configured = False
            
            if enterprise_token:
                if self._download_enterprise_archive(version, enterprise_token, enterprise_dir):
                    print(f"Modules Enterprise téléchargés dans {enterprise_dir}")
                    # Vérifier si le dossier odoo/addons existe dans le dossier enterprise après extraction
                    addons_path = enterprise_dir / "odoo" / "addons"
                    if addons_path.exists():
                        # Monter le chemin spécifique vers odoo/addons
                        vols.append('./enterprise/odoo/addons:/mnt/enterprise-addons:rw')
                        enterprise_addons_configured = True
                        enterprise_path = './enterprise/odoo/addons'
                        print(f"Module Enterprise détecté dans {addons_path}, montage configuré")
                    else:
                        # Chercher les addons au premier niveau
                        print("Structure odoo/addons non trouvée, recherche d'une structure alternative...")
                        # Vérifier si des modules sont directement dans le dossier enterprise
                        modules_direct = [f for f in enterprise_dir.glob("*/__manifest__.py")]
                        if modules_direct:
                            vols.append('./enterprise:/mnt/enterprise-addons:rw')
                            enterprise_addons_configured = True
                            enterprise_path = './enterprise'
                            print(f"Modules Enterprise trouvés directement dans {enterprise_dir}, montage configuré")
                        else:
                            # Chercher tous les sous-dossiers qui pourraient contenir des addons
                            potential_addons_dirs = [d for d in enterprise_dir.glob("**/addons") if d.is_dir()]
                            if potential_addons_dirs:
                                # Prendre le premier trouvé
                                relative_path = os.path.relpath(potential_addons_dirs[0], inst)
                                vols.append(f'./{relative_path}:/mnt/enterprise-addons:rw')
                                enterprise_addons_configured = True
                                enterprise_path = f'./{relative_path}'
                                print(f"Dossier addons trouvé à {relative_path}, montage configuré")
                            else:
                                print("AVERTISSEMENT: Aucun dossier addons trouvé dans l'archive Enterprise!")
                                # Monter quand même le dossier enterprise complet au cas où
                                vols.append('./enterprise:/mnt/enterprise-addons:rw')
                                enterprise_addons_configured = True
                                enterprise_path = './enterprise'
                else:
                    print("AVERTISSEMENT: Le téléchargement Enterprise a échoué.")
            
            # Gestion du chemin d'addons externe (indépendamment du token Enterprise)
            if external_addons_path:
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
            elif not enterprise_addons_configured:
                # Si aucun addons externes et pas d'addons Enterprise, afficher un avertissement
                print("AVERTISSEMENT: Aucun chemin d'addons Enterprise configuré!")
        elif external_addons_path:
            path = Path(external_addons_path)
            if path.is_dir():
                # Remplacer le montage par défaut de custom-addons par le chemin externe
                custom_addons_index = next((i for i, v in enumerate(vols) if '/mnt/custom-addons' in v), None)
                if custom_addons_index is not None:
                    vols[custom_addons_index] = f"{path.resolve()}:/mnt/custom-addons:rw"
                else:
                    vols.append(f"{path.resolve()}:/mnt/custom-addons:rw")
                print(f"Addons externes montés depuis {path}")
            else:
                print(f"Warning: Le chemin d'addons externe '{path}' n'existe pas")
        
        # Préparation des données pour le template
        template_data = {
            'odoo_version': version,
            'edition_name': edition.capitalize(),
            'is_enterprise': is_ee,
            'external_port': port,
            'db_name': db_name,
            'postgres_db': 'postgres',
            'postgres_user': 'odoo',
            'postgres_password': 'odoo',
            'postgres_volume': postgres_volume_name,
            'odoo_volumes': vols,
            'odoo_command': '--config=/etc/odoo/odoo.conf',
            'volumes': {
                odoo_volume_name: None,
                postgres_volume_name: None
            },
            'enterprise_path': enterprise_path if is_ee else None,
            'project_name': project_name
        }
        
        # Importer notre module d'utilitaires de templates
        from templates_utils import render_template, render_with_yaml, load_template
        
        try:
            # Générer le docker-compose.yml avec le template dédié
            docker_compose_template = load_template('docker-compose.yml.j2')
            docker_compose_content = render_with_yaml(docker_compose_template, template_data)
            
            # Écrire le fichier docker-compose.yml
            out = inst / 'docker-compose.yml'
            with open(out, 'w') as f:
                f.write(docker_compose_content)
            
            # Générer le README.md avec le template dédié
            readme_content = render_template('README.md.j2', template_data)
            
            # Créer un fichier README.md pour expliquer la configuration
            readme_path = inst / 'README.md'
            with open(readme_path, 'w') as f:
                f.write(readme_content)
            
            # Créer un fichier .env pour définir le nom du projet Docker Compose
            env_file = inst / '.env'
            with open(env_file, 'w') as f:
                f.write(f"COMPOSE_PROJECT_NAME={project_name}\n")
            
            # Créer un fichier .gitignore dans le dossier custom-addons
            try:
                gitignore_content = load_template('custom-addons.gitignore.j2')
                gitignore_path = inst / 'custom-addons' / '.gitignore'
                with open(gitignore_path, 'w') as f:
                    f.write(gitignore_content)
            except Exception as e:
                print(f"Note: Impossible de créer le fichier .gitignore pour custom-addons: {e}")
            
            # Générer le script list_modules.py pour lister les modules clients
            list_modules_content = render_template('list_modules.py.j2', template_data)
            list_modules_path = inst / 'list_modules.py'
            with open(list_modules_path, 'w') as f:
                f.write(list_modules_content)
            # Rendre le script exécutable
            os.chmod(list_modules_path, 0o755)
            print(f"Script de liste des modules créé: {list_modules_path}")
            
            print(f"Généré: {out}")
            print(f"Volumes Docker uniques créés: {odoo_volume_name}, {postgres_volume_name}")
            return out, db_name
            
        except FileNotFoundError as e:
            print(f"Erreur: {e}")
            print("Assurez-vous que les templates existent dans le dossier 'templates'")
            raise
        except Exception as e:
            print(f"Erreur lors de la génération des fichiers à partir des templates: {e}")
            import traceback
            traceback.print_exc()
            raise

    def build_and_run(self, compose_file: Path, db_name: str, fresh_install=True):
        """
        Construit et démarre les conteneurs Docker
        
        Args:
            compose_file: Chemin vers le fichier docker-compose.yml
            db_name: Nom de la base de données à utiliser
            fresh_install: Si True, ne pas initialiser la base de données
        """
        if not compose_file or not compose_file.exists():
            print("Erreur: Fichier docker-compose.yml non trouvé")
            return
        
        # Extraire le nom du projet à partir du docker-compose.yml
        yaml_content = yaml.safe_load(compose_file.read_text())
        port = yaml_content['services']['odoo']['ports'][0].split(':')[0]
        
        # Générer le nom du projet à partir du yaml pour garantir l'unicité
        volumes = yaml_content['volumes']
        project_name = None
        for vol_name in volumes.keys():
            if vol_name.endswith('_odoo_data'):
                project_name = vol_name.replace('_odoo_data', '')
                break
        
        if not project_name:
            # Fallback: utiliser le nom du dossier parent
            project_name = compose_file.parent.name.replace('-', '_').replace('.', '_')
        
        print(f"Utilisation du nom de projet Docker Compose: {project_name}")
        
        # Créer un fichier .env pour définir le nom du projet Docker Compose
        env_file = compose_file.parent / '.env'
        with open(env_file, 'w') as f:
            f.write(f"COMPOSE_PROJECT_NAME={project_name}\n")
        
        print(f"Fichier .env créé avec COMPOSE_PROJECT_NAME={project_name}")
        
        os.chdir(compose_file.parent)
        try:
            print(f"Construction des conteneurs depuis {compose_file}...")
            subprocess.run(['docker-compose', 'up', '-d', '--build'], check=True)
            
            print("Attente de 10 secondes pour le démarrage complet des conteneurs...")
            time.sleep(10)
            
            # Vérifier si les conteneurs sont bien démarrés
            result = subprocess.run(['docker-compose', 'ps'], stdout=subprocess.PIPE, check=True)
            if "Up" not in result.stdout.decode():
                print("AVERTISSEMENT: Les conteneurs ne semblent pas être démarrés correctement.")
            
            # En mode installation fraîche, ne pas initialiser la base de données
            # pour permettre l'affichage de l'écran de configuration initial
            if not fresh_install:
                print(f"Initialisation de la base de données Odoo '{db_name}'...")
                # Utiliser le nom de base de données spécifique à cette instance
                subprocess.run(
                    f"docker-compose exec -T odoo odoo -d {db_name} --stop-after-init -i base",
                    shell=True, check=False
                )
            else:
                print("Mode installation fraîche: Odoo va démarrer sans base de données préconfiguré")
                print("Vous pourrez créer une nouvelle base de données via l'interface web")
            
            print(f"Odoo accessible: http://localhost:{port}")
            if not fresh_install:
                print(f"Base de données: {db_name}")
            print(f"Pour arrêter et supprimer uniquement cette instance, exécutez:")
            print(f"cd {compose_file.parent} && docker-compose down -v")
        except subprocess.CalledProcessError as e:
            print(f"Erreur lors du démarrage des conteneurs: {e}")
        except Exception as e:
            print(f"Erreur inattendue: {e}")
            import traceback
            traceback.print_exc()


def main():
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
        gen = OdooDockerGenerator(args.output_dir)
        comp, db_name = gen.generate_docker_compose(
            args.version, 
            args.edition, 
            args.port,
            external_addons_path=args.addons_path,
            enterprise_token=args.enterprise_token,
            fresh_install=args.fresh_install
        )
        
        if args.build and comp:
            gen.build_and_run(comp, db_name, fresh_install=args.fresh_install)
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
