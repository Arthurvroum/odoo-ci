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

    def _create_odoo_config(self, config_dir, is_enterprise=False):
        """
        Crée le fichier de configuration odoo.conf
        
        Args:
            config_dir: Chemin vers le dossier de configuration
            is_enterprise: Si True, ajoute la configuration Enterprise
        """
        config_path = config_dir / 'odoo.conf'
        addons_path = '/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons'
        
        # Ajouter les chemins d'addons Enterprise
        if is_enterprise:
            addons_path += ',/mnt/enterprise,/mnt/custom-addons'
        
        config = configparser.ConfigParser()
        config['options'] = {
            '; password admin': '',
            'admin_passwd': 'admin',
            '; chemins addons': '',
            'addons_path': addons_path,
            '; DB': '',
            'db_host': 'db',
            'db_port': '5432',
            'db_user': 'odoo',
            'db_password': 'odoo',
            'http_port': '8069'
        }
        
        with open(config_path, 'w') as f:
            config.write(f)

    def _download_enterprise_archive(self, version: str, token: str, target_dir: Path, browser_fallback=False):
        """
        Télécharge et extrait l'archive Enterprise pour la version depuis odoo.com.
        Utilise plusieurs méthodes et tente d'extraire l'URL directe depuis la page de remerciement.
        
        Args:
            version: Version d'Odoo (ex: "18.0")
            token: Token d'accès Enterprise
            target_dir: Répertoire où télécharger/extraire l'archive
            browser_fallback: Paramètre conservé pour compatibilité mais ignoré
            
        Returns:
            bool: True si le téléchargement a réussi, False sinon
        """
        target_dir.mkdir(parents=True, exist_ok=True)
        archive_path = target_dir / f"odoo-enterprise-{version}.tar.gz"
        
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
                
                with open(archive_path, 'wb') as f:
                    for chunk in download_response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # Extraire l'archive
                try:
                    print(f"Extraction de l'archive dans {target_dir}...")
                    with tarfile.open(archive_path, 'r:gz') as tar:
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
                              enterprise_token=None):
        """
        Génère docker-compose.yml et télécharge le code Enterprise si demandé.
        
        Args:
            version: Version d'Odoo (ex: "18.0")
            edition: Edition ('enterprise' ou 'community')
            port: Port à exposer
            external_addons_path: Chemin vers des addons externes
            enterprise_token: Token pour l'édition Enterprise
            
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
        inst.mkdir(parents=True, exist_ok=True)
        
        # Créer les sous-dossiers
        dirs = {k: inst / f"odoo-data/{k}" for k in ['addons', 'etc', 'filestore']}
        dirs['postgres'] = inst / 'postgresql'
        for d in dirs.values(): 
            d.mkdir(parents=True, exist_ok=True)
        
        # Créer le fichier de configuration
        self._create_odoo_config(dirs['etc'], is_enterprise=is_ee)
        
        # Préparer les volumes
        vols = [
            'odoo-data:/var/lib/odoo',
            './odoo-data/etc:/etc/odoo',
            './odoo-data/addons:/mnt/extra-addons:rw'
        ]
        
        # Gérer les addons Enterprise ou externes
        if is_ee:
            if not enterprise_token and not external_addons_path:
                raise ValueError("Token requis pour l'édition Enterprise")
            
            # Créer le dossier enterprise au même niveau que docker-compose.yml
            enterprise_dir = inst / "enterprise"
            enterprise_dir.mkdir(parents=True, exist_ok=True)
            
            # Ajouter le volume pour monter le dossier enterprise complet
            vols.append('./enterprise:/mnt/enterprise:ro')
            
            if enterprise_token:
                if self._download_enterprise_archive(version, enterprise_token, enterprise_dir):
                    print(f"Modules Enterprise téléchargés dans {enterprise_dir}")
                    # Vérifier si le dossier odoo/addons existe dans le dossier enterprise après extraction
                    addons_path = enterprise_dir / "odoo" / "addons"
                    if addons_path.exists():
                        # Monter le chemin spécifique vers odoo/addons
                        vols.append('./enterprise/odoo/addons:/mnt/custom-addons:rw')
                        print(f"Module Enterprise détecté dans {addons_path}, montage configuré")
                    else:
                        # Chercher les addons au premier niveau
                        print("Structure odoo/addons non trouvée, recherche d'une structure alternative...")
                        # Vérifier si des modules sont directement dans le dossier enterprise
                        modules_direct = [f for f in enterprise_dir.glob("*/__manifest__.py")]
                        if modules_direct:
                            vols.append('./enterprise:/mnt/custom-addons:rw')
                            print(f"Modules Enterprise trouvés directement dans {enterprise_dir}, montage configuré")
                        else:
                            # Chercher tous les sous-dossiers qui pourraient contenir des addons
                            potential_addons_dirs = [d for d in enterprise_dir.glob("**/addons") if d.is_dir()]
                            if potential_addons_dirs:
                                # Prendre le premier trouvé
                                relative_path = os.path.relpath(potential_addons_dirs[0], inst)
                                vols.append(f'./{relative_path}:/mnt/custom-addons:rw')
                                print(f"Dossier addons trouvé à {relative_path}, montage configuré")
                            else:
                                print("AVERTISSEMENT: Aucun dossier addons trouvé dans l'archive Enterprise!")
                                # Monter quand même le dossier enterprise complet au cas où
                                vols.append('./enterprise:/mnt/custom-addons:rw')
                else:
                    print("AVERTISSEMENT: Le téléchargement Enterprise a échoué.")
                    if external_addons_path:
                        path = Path(external_addons_path)
                        if path.is_dir():
                            print(f"Utilisation du chemin direct: {path}")
                            vols.append(f"{path.resolve()}:/mnt/custom-addons:rw")
                        else:
                            print(f"Warning: Le chemin d'addons externe '{path}' n'existe pas")
            elif external_addons_path:
                path = Path(external_addons_path)
                if path.is_dir():
                    print(f"Utilisation du chemin direct: {path}")
                    vols.append(f"{path.resolve()}:/mnt/custom-addons:rw")
                else:
                    print(f"Warning: Le chemin d'addons externe '{path}' n'existe pas")
        elif external_addons_path:
            path = Path(external_addons_path)
            if path.is_dir():
                vols.append(f"{path.resolve()}:/mnt/custom-addons:rw")
            else:
                print(f"Warning: Le chemin d'addons externe '{path}' n'existe pas")
        
        # Configuration du service Odoo
        db_env = {
            'POSTGRES_DB': 'postgres',
            'POSTGRES_USER': 'odoo',
            'POSTGRES_PASSWORD': 'odoo',
            'PGHOST': 'db'
        }
        
        # Convertir les variables d'environnement en liste comme attendu par Docker Compose
        env_list = [f"{k}={v}" for k, v in db_env.items()]
        
        svc = {
            'image': f"odoo:{version}",
            'depends_on': ['db'],
            'ports': [f"{port}:8069"],
            'environment': env_list,
            # Ajouter les paramètres de connexion à la commande de démarrage d'Odoo
            'command': '--config=/etc/odoo/odoo.conf',
            'volumes': vols,
            'restart': 'always'
        }
        
        # Configuration docker-compose complète
        comp = {
            'services': {
                'db': {
                    'image': 'postgres:13',
                    'environment': [
                        'POSTGRES_DB=postgres',
                        'POSTGRES_USER=odoo',
                        'POSTGRES_PASSWORD=odoo'
                    ],
                    'volumes': ['postgres-data:/var/lib/postgresql/data'],
                    'restart': 'always'
                },
                'odoo': svc
            },
            'volumes': {
                'odoo-data': None,
                'postgres-data': None
            }
        }
        
        # Écrire le fichier docker-compose.yml
        out = inst / 'docker-compose.yml'
        with open(out, 'w') as f:
            yaml.dump(comp, f, default_flow_style=False)
        
        # Créer un fichier README.md pour expliquer la configuration
        readme_path = inst / 'README.md'
        with open(readme_path, 'w') as f:
            f.write(f"""# Odoo {version} {edition.capitalize()}

## Configuration

Cette installation est configurée pour utiliser Odoo {edition.capitalize()} {version}.

- Port: {port}
- Base de données: PostgreSQL 13
- Répertoire des modules Enterprise: ./enterprise/odoo/addons

## Démarrage

```bash
docker-compose up -d
```

## Utilisation

Accédez à Odoo via votre navigateur à l'adresse:
http://localhost:{port}

Identifiants par défaut: admin / admin
""")
        
        print(f"Généré: {out}")
        return out

    def build_and_run(self, compose_file: Path):
        """
        Construit et démarre les conteneurs Docker
        """
        if not compose_file or not compose_file.exists():
            print("Erreur: Fichier docker-compose.yml non trouvé")
            return
        
        os.chdir(compose_file.parent)
        try:
            print(f"Construction des conteneurs depuis {compose_file}...")
            subprocess.run(['docker-compose', 'up', '-d', '--build'], check=True)
            
            print("Attente de 5 secondes pour le démarrage des conteneurs...")
            time.sleep(5)
            
            print("Mise à jour de la liste des modules...")
            subprocess.run(
                "docker-compose exec -T odoo odoo -d postgres --stop-after-init -u base",
                shell=True, check=False
            )
            
            port = yaml.safe_load(compose_file.read_text())['services']['odoo']['ports'][0].split(':')[0]
            print(f"Odoo accessible: http://localhost:{port}")
            print("Identifiants par défaut: admin / admin")
        except subprocess.CalledProcessError as e:
            print(f"Erreur lors du démarrage des conteneurs: {e}")
        except Exception as e:
            print(f"Erreur inattendue: {e}")


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
    
    args = parser.parse_args()
    
    # Vérifier le token si edition enterprise
    if args.edition.lower() == 'enterprise' and not args.enterprise_token and not args.addons_path:
        print("ATTENTION: L'édition Enterprise nécessite un token ou un chemin vers les addons déjà téléchargés.")
        if input("Continuer quand même? (o/N): ").lower() != 'o':
            return
    
    try:
        gen = OdooDockerGenerator(args.output_dir)
        comp = gen.generate_docker_compose(
            args.version, 
            args.edition, 
            args.port,
            external_addons_path=args.addons_path,
            enterprise_token=args.enterprise_token
        )
        
        if args.build and comp:
            gen.build_and_run(comp)
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
