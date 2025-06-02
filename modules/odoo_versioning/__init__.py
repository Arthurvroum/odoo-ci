#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module de gestion des versions d'Odoo et du téléchargement des archives Enterprise.
"""

import os
import re
import requests
import tarfile
import time
import sys
from pathlib import Path
import shutil

# Importer notre logger avec animation
from ..ui_logger import logger


class OdooVersionManager:
    """
    Classe de gestion des versions d'Odoo.
    Permet de télécharger et d'extraire les archives Enterprise pour différentes versions.
    """
    
    # URLs pour le téléchargement des archives Enterprise
    DOWNLOAD_PAGE_URL = "https://www.odoo.com/fr_FR/page/download"
    THANKS_URL_FORMAT = "https://www.odoo.com/fr_FR/thanks/download?code={token}&platform_version=src_{version}e"
    
    def __init__(self, cache_dir=None):
        """
        Initialise le gestionnaire de versions d'Odoo.
        
        Args:
            cache_dir (str, optional): Chemin vers le dossier de cache pour les archives téléchargées.
                                      Si None, utilise le dossier 'enterprise_cache' dans le dossier parent.
        """
        # Définir le dossier de cache
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            # Utiliser le dossier 'enterprise_cache' dans le dossier parent du module
            module_path = Path(os.path.dirname(os.path.abspath(__file__)))
            self.cache_dir = module_path.parent.parent / "enterprise_cache"
        
        # S'assurer que le dossier de cache existe
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Dossier cache pour les archives Enterprise: {self.cache_dir}")
    
    def normalize_version(self, version):
        """
        Normalise le numéro de version d'Odoo (ajoute '.0' si nécessaire).
        
        Args:
            version (str): Numéro de version à normaliser (ex: '18' ou '18.0').
            
        Returns:
            str: Version normalisée (ex: '18.0').
        """
        if not version.endswith('.0'):
            version = f"{version}.0"
        return version
    
    def get_short_version(self, version):
        """
        Convertit la version complète en version courte pour les URLs.
        
        Args:
            version (str): Version complète (ex: '18.0').
            
        Returns:
            str: Version courte (ex: '18').
        """
        return version.replace('.0', '')
    
    def download_enterprise_archive(self, version, token, target_dir):
        """
        Télécharge et extrait l'archive Enterprise pour la version depuis odoo.com.
        Utilise le cache si disponible pour éviter les téléchargements redondants.
        
        Args:
            version (str): Version d'Odoo (ex: '18.0').
            token (str): Token d'accès Enterprise.
            target_dir (Path): Répertoire où extraire l'archive.
            
        Returns:
            bool: True si le téléchargement/extraction a réussi, False sinon.
        """
        # Normaliser la version et créer le répertoire cible
        version = self.normalize_version(version)
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Créer une section pour le téléchargement
        logger.section(f"Préparation d'Odoo Enterprise {version}")
        
        # Vérifier si cette version est déjà en cache
        cached_archive_path = self.cache_dir / f"odoo-enterprise-{version}.tar.gz"
        if cached_archive_path.exists():
            logger.success(f"Archive Odoo Enterprise {version} trouvée dans le cache")
            logger.start_spinner(f"Extraction de l'archive depuis le cache vers {target_dir}")
            
            try:
                result = self._extract_archive(cached_archive_path, target_dir)
                if result:
                    logger.stop_spinner(success=True, message=f"Extraction réussie dans {target_dir}")
                    return True
                else:
                    logger.stop_spinner(success=False, message="Échec de l'extraction depuis le cache")
            except Exception as e:
                logger.stop_spinner(success=False, message=f"Erreur lors de l'extraction: {str(e)}")
                # Continuer avec le téléchargement en ligne en cas d'erreur
        else:
            logger.info(f"Aucune archive en cache pour Odoo Enterprise {version}")
        
        # Si pas en cache ou extraction échouée, télécharger
        short_version = self.get_short_version(version)
        
        # URL de la page de remerciement (qui contient le lien direct)
        thanks_url = self.THANKS_URL_FORMAT.format(token=token, version=short_version)
        
        logger.download(f"Téléchargement d'Odoo Enterprise {version}")
        logger.start_spinner(f"Récupération de la page de téléchargement")
        
        try:
            # Étape 1: Récupérer la page de remerciement
            response = requests.get(thanks_url)
            response.raise_for_status()
            html_content = response.text
            logger.stop_spinner(success=True, message="Page de téléchargement récupérée")
            
            # Étape 2: Extraire l'URL directe de téléchargement
            logger.start_spinner("Analyse de la page pour trouver l'URL de téléchargement")
            direct_url = self._extract_direct_url(html_content, short_version)
            
            # Si on a trouvé une URL directe, télécharger
            if direct_url:
                logger.stop_spinner(success=True, message="URL de téléchargement trouvée")
                
                # Vérification du type de réponse
                logger.start_spinner("Vérification du type de contenu")
                download_response = requests.get(direct_url, stream=True)
                download_response.raise_for_status()
                content_type = download_response.headers.get('Content-Type', '')
                
                if 'text/html' in content_type:
                    logger.stop_spinner(success=False, message="Erreur: Le serveur a renvoyé une page HTML au lieu de l'archive")
                    with open(target_dir / "error_response.html", 'wb') as f:
                        f.write(download_response.content)
                    return False
                
                logger.stop_spinner(success=True)
                
                # Télécharger le fichier avec barre de progression
                total_size = int(download_response.headers.get('Content-Length', 0))
                logger.info(f"Taille de l'archive: {total_size/1024/1024:.1f} MB")
                
                # Télécharger dans le cache d'abord avec barre de progression
                with logger.progress_bar(total=total_size, desc="Téléchargement", unit="B", unit_scale=True) as pbar:
                    with open(cached_archive_path, 'wb') as f:
                        for chunk in download_response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                pbar.update(len(chunk))
                
                logger.success(f"Archive téléchargée et mise en cache dans {cached_archive_path}")
                
                # Extraire l'archive depuis le cache vers le dossier cible
                return self._extract_archive(cached_archive_path, target_dir)
            else:
                logger.stop_spinner(success=False, message="Impossible de trouver l'URL directe dans la page")
        except Exception as e:
            logger.stop_spinner(success=False)
            logger.error(f"Erreur lors du téléchargement: {e}")
        
        logger.warning("\nLes méthodes automatiques de téléchargement ont échoué.")
        logger.info(f"Conseil: Téléchargez manuellement Odoo Enterprise {version} depuis le site d'Odoo")
        logger.info(f"puis utilisez l'option --addons-path pour spécifier l'emplacement.")
        
        return False
    
    def _extract_direct_url(self, html_content, short_version):
        """
        Extrait l'URL directe de téléchargement depuis le contenu HTML.
        
        Args:
            html_content (str): Contenu HTML de la page.
            short_version (str): Version courte d'Odoo (ex: '18').
            
        Returns:
            str: URL directe de téléchargement, ou None si non trouvée.
        """
        direct_url = None
        
        # Méthode 1: Chercher une URL complète
        url_match = re.search(r'https://download\.odoocdn\.com/download/[^"\'&\s]+', html_content)
        if url_match:
            direct_url = url_match.group(0)
            logger.info(f"URL directe trouvée")
        
        # Méthode 2: Chercher un payload
        if not direct_url:
            payload_match = re.search(r'payload=([^"\'&\s]+)', html_content)
            if payload_match:
                payload = payload_match.group(1)
                direct_url = f"https://download.odoocdn.com/download/{short_version}e/src?payload={payload}"
                logger.info(f"URL avec payload construite")
        
        return direct_url
    
    def _extract_archive(self, archive_path, target_dir):
        """
        Extrait une archive tar.gz vers un répertoire cible.
        
        Args:
            archive_path (Path): Chemin vers l'archive à extraire.
            target_dir (Path): Répertoire où extraire l'archive.
            
        Returns:
            bool: True si l'extraction a réussi, False sinon.
        """
        try:
            # Création d'une section distincte pour l'extraction
            logger.section("Extraction de l'archive")
            
            with tarfile.open(archive_path, 'r:gz') as tar:
                # Analyse préliminaire du contenu de l'archive
                members = tar.getmembers()
                total_members = len(members)
                logger.info(f"Archive contenant {total_members} fichiers")
                
                # Vérifier si l'archive a un dossier racine unique (comme "enterprise")
                root_dirs = {m.name.split('/')[0] for m in members if '/' in m.name}
                
                if len(root_dirs) == 1:
                    # Cas où l'archive a un dossier racine unique
                    top_dir = next(iter(root_dirs))
                    logger.extract(f"Extraction du contenu du dossier {top_dir} directement dans {target_dir}")
                    
                    # Filtrer les membres à extraire (ignorer le dossier racine)
                    filtered_members = []
                    for m in members:
                        if m.name.startswith(f"{top_dir}/"):
                            # On garde une référence au membre original et sa nouvelle destination
                            new_name = m.name[len(top_dir)+1:]
                            if new_name:  # Ne pas extraire les dossiers vides
                                filtered_members.append((m, new_name))
                    
                    # Extraction avec barre de progression
                    total = len(filtered_members)
                    logger.info(f"Préparation de {total} fichiers à extraire")
                    
                    # Petite pause pour laisser le message précédent s'afficher complètement
                    time.sleep(0.2)
                    
                    for i, (orig_member, new_name) in enumerate(filtered_members, 1):
                        # Afficher la progression avec notre méthode personnalisée
                        logger.extraction_progress(i, total, "Extraction des fichiers")
                        
                        # Extraire le fichier
                        tar.extract(orig_member, path=target_dir)
                        
                        # Renommer pour ignorer le dossier racine
                        extracted_path = target_dir / orig_member.name
                        new_path = target_dir / new_name
                        
                        if extracted_path.exists() and str(extracted_path) != str(new_path):
                            if not new_path.parent.exists():
                                new_path.parent.mkdir(parents=True, exist_ok=True)
                            if extracted_path.is_file():
                                shutil.move(str(extracted_path), str(new_path))
                    
                    # Supprimer le dossier racine vide
                    root_dir_path = target_dir / top_dir
                    if root_dir_path.exists():
                        try:
                            shutil.rmtree(str(root_dir_path))
                        except Exception:
                            # Ignorer les erreurs lors de la suppression du dossier racine
                            pass
                    
                else:
                    # Cas où l'archive n'a pas de dossier racine unique
                    logger.extract(f"Extraction directe dans {target_dir}")
                    
                    # Extraction avec barre de progression
                    total = total_members
                    
                    # Petite pause pour laisser le message précédent s'afficher complètement
                    time.sleep(0.2)
                    
                    for i, member in enumerate(members, 1):
                        # Afficher la progression avec notre méthode personnalisée
                        logger.extraction_progress(i, total, "Extraction des fichiers")
                        
                        # Extraire le fichier
                        tar.extract(member, path=target_dir)
            
            # Laisser un petit délai pour que la barre de progression soit bien affichée
            time.sleep(0.2)
            logger.success(f"Extraction réussie dans {target_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction: {e}")
            return False
