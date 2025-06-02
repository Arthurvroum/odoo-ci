#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module pour la gestion des logs et de l'interface utilisateur.
Fournit des fonctions pour afficher des logs attractifs avec couleurs et animations.
"""

import sys
import time
import threading
import colorama
from colorama import Fore, Style, Back
from tqdm import tqdm
import shutil

# Initialiser colorama pour qu'il fonctionne correctement sur tous les OS
colorama.init(autoreset=True)


class UILogger:
    """
    Classe pour gérer l'affichage des logs avec des couleurs, animations et barres de progression.
    """
    
    def __init__(self, verbose=True, use_animations=True, use_colors=True):
        """
        Initialise le logger avec les options spécifiées.
        
        Args:
            verbose (bool): Si True, affiche tous les messages, sinon uniquement les messages importants.
            use_animations (bool): Si True, utilise des animations et barres de progression.
            use_colors (bool): Si True, utilise des couleurs dans les logs.
        """
        self.verbose = verbose
        self.use_animations = use_animations and sys.stdout.isatty()  # Utiliser les animations seulement si dans un terminal
        self.use_colors = use_colors
        self.spinner_thread = None
        self.spinner_stop_event = None
        self.terminal_width = shutil.get_terminal_size().columns
        self.animation_enabled = True
        
        # Styles de message
        self.styles = {
            'info': f"{Fore.BLUE}ℹ {Fore.RESET}",
            'success': f"{Fore.GREEN}✓ {Fore.RESET}",
            'warning': f"{Fore.YELLOW}⚠ {Fore.RESET}",
            'error': f"{Fore.RED}✗ {Fore.RESET}",
            'step': f"{Fore.CYAN}→ {Fore.RESET}",
            'download': f"{Fore.MAGENTA}↓ {Fore.RESET}",
            'extract': f"{Fore.YELLOW}⚙ {Fore.RESET}",
            'docker': f"{Fore.BLUE}🐳 {Fore.RESET}",
            'odoo': f"{Fore.GREEN}🌿 {Fore.RESET}",
        }
        
        # Désactiver les styles si les couleurs ne sont pas utilisées
        if not self.use_colors:
            for key in self.styles:
                self.styles[key] = ""
    
    def _format_message(self, message, style='info'):
        """
        Formate un message avec le style spécifié.
        """
        prefix = self.styles.get(style, "")
        if not self.use_colors:
            return f"{prefix}{message}"
        
        if style == 'info':
            return f"{prefix}{message}"
        elif style == 'success':
            return f"{prefix}{Fore.GREEN}{message}{Style.RESET_ALL}"
        elif style == 'warning':
            return f"{prefix}{Fore.YELLOW}{message}{Style.RESET_ALL}"
        elif style == 'error':
            return f"{prefix}{Fore.RED}{message}{Style.RESET_ALL}"
        elif style == 'step':
            return f"{prefix}{Fore.CYAN}{message}{Style.RESET_ALL}"
        elif style == 'download':
            return f"{prefix}{Fore.MAGENTA}{message}{Style.RESET_ALL}"
        elif style == 'extract':
            return f"{prefix}{Fore.YELLOW}{message}{Style.RESET_ALL}"
        elif style == 'docker':
            return f"{prefix}{Fore.BLUE}{message}{Style.RESET_ALL}"
        elif style == 'odoo':
            return f"{prefix}{Fore.GREEN}{message}{Style.RESET_ALL}"
        else:
            return f"{message}"
    
    def info(self, message):
        """
        Affiche un message d'information.
        """
        if self.verbose:
            print(self._format_message(message, 'info'))
    
    def success(self, message):
        """
        Affiche un message de succès.
        """
        print(self._format_message(message, 'success'))
    
    def warning(self, message):
        """
        Affiche un message d'avertissement.
        """
        print(self._format_message(message, 'warning'))
    
    def error(self, message):
        """
        Affiche un message d'erreur.
        """
        print(self._format_message(message, 'error'))
    
    def step(self, message):
        """
        Affiche un message d'étape.
        """
        print(self._format_message(message, 'step'))
    
    def download(self, message):
        """
        Affiche un message de téléchargement.
        """
        print(self._format_message(message, 'download'))
    
    def extract(self, message):
        """
        Affiche un message d'extraction.
        """
        print(self._format_message(message, 'extract'))
    
    def docker(self, message):
        """
        Affiche un message relatif à Docker.
        """
        print(self._format_message(message, 'docker'))
    
    def odoo(self, message):
        """
        Affiche un message relatif à Odoo.
        """
        print(self._format_message(message, 'odoo'))
    
    def progress_bar(self, iterable=None, total=None, desc="En cours", unit="it", **kwargs):
        """
        Crée et retourne une barre de progression.
        
        Args:
            iterable: Itérable à parcourir.
            total: Nombre total d'éléments (si iterable non fourni).
            desc: Description de la barre de progression.
            unit: Unité des éléments.
            **kwargs: Arguments supplémentaires pour tqdm.
            
        Returns:
            tqdm: Instance de tqdm (barre de progression).
        """
        if not self.use_animations:
            # Version simple sans animation
            class DummyTqdm:
                def __init__(self, *args, **kwargs):
                    self.total = kwargs.get('total', 0)
                    self.n = 0
                    self.desc = kwargs.get('desc', '')
                
                def update(self, n=1):
                    self.n += n
                
                def close(self):
                    pass
                
                def __enter__(self):
                    return self
                
                def __exit__(self, *args, **kwargs):
                    self.close()
            
            return DummyTqdm(iterable=iterable, total=total, desc=desc)
        else:
            # Version avec animation tqdm
            return tqdm(
                iterable=iterable, 
                total=total, 
                desc=desc,
                unit=unit,
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} {unit} [{elapsed}<{remaining}, {rate_fmt}]",
                **kwargs
            )
    
    def _spinner_animation(self, message, stop_event):
        """
        Fonction d'animation du spinner.
        """
        frames = ["⣷", "⣯", "⣟", "⡿", "⢿", "⣻", "⣽", "⣾"]
        i = 0
        while not stop_event.is_set():
            if self.animation_enabled:
                frame = frames[i % len(frames)]
                sys.stdout.write(f"\r{frame} {message}")
                sys.stdout.flush()
                i += 1
                time.sleep(0.1)
        # Nettoyer la ligne quand on termine
        sys.stdout.write("\r" + " " * (len(message) + 2) + "\r")
        sys.stdout.flush()
    
    def start_spinner(self, message):
        """
        Démarre un spinner avec un message.
        """
        if not self.use_animations:
            print(message)
            return
            
        # Arrêter le spinner précédent s'il existe
        self.stop_spinner()
        
        # Démarrer un nouveau spinner
        self.spinner_stop_event = threading.Event()
        self.spinner_thread = threading.Thread(
            target=self._spinner_animation,
            args=(message, self.spinner_stop_event)
        )
        self.spinner_thread.daemon = True
        self.spinner_thread.start()
    
    def stop_spinner(self, success=True, message=None):
        """
        Arrête le spinner et affiche éventuellement un message.
        """
        if self.spinner_thread and self.spinner_thread.is_alive():
            self.animation_enabled = False  # Désactiver l'animation
            self.spinner_stop_event.set()   # Signaler l'arrêt
            self.spinner_thread.join()      # Attendre la fin du thread
            
            # Afficher un message final si fourni
            if message:
                if success:
                    print(self._format_message(message, 'success'))
                else:
                    print(self._format_message(message, 'error'))
            
            # Réinitialiser
            self.spinner_thread = None
            self.spinner_stop_event = None
            self.animation_enabled = True
    
    def section(self, title):
        """
        Affiche un titre de section.
        """
        if self.use_colors:
            # Calculer la largeur de la ligne de séparation
            width = min(self.terminal_width - 2, 80)
            
            # Créer la ligne de séparation
            separator = f"{Fore.CYAN}{'═' * width}{Style.RESET_ALL}"
            
            # Afficher la section avec des séparateurs
            print(f"\n{separator}")
            print(f"{Fore.CYAN}{Style.BRIGHT}{title}{Style.RESET_ALL}")
            print(f"{separator}\n")
        else:
            # Version sans couleurs
            print(f"\n{title}\n{'=' * len(title)}")
    
    def clear_line(self):
        """
        Efface la ligne courante.
        """
        if self.use_animations:
            sys.stdout.write("\r" + " " * self.terminal_width + "\r")
            sys.stdout.flush()
    
    def extraction_progress(self, current, total, description="Extraction"):
        """
        Affiche une barre de progression personnalisée pour l'extraction de fichiers.
        Cette méthode est spécifiquement conçue pour ne pas interférer avec d'autres
        affichages dans le terminal.
        
        Args:
            current (int): Nombre d'éléments actuellement traités.
            total (int): Nombre total d'éléments à traiter.
            description (str): Description de l'opération en cours.
        """
        if not self.use_animations:
            # En mode sans animation, n'afficher qu'un message simple
            if current == 1:  # Afficher uniquement au début
                print(f"{description} en cours...")
            return
            
        # Calculer le pourcentage de progression
        percentage = int((current / total) * 100) if total > 0 else 0
        
        # Déterminer la largeur de la barre en fonction de la largeur du terminal
        bar_width = min(50, self.terminal_width - 30)
        filled_length = int(bar_width * current // total) if total > 0 else 0
        
        # Construire la barre de progression
        if self.use_colors:
            bar = (f"{Fore.GREEN}{'█' * filled_length}{Style.RESET_ALL}"
                  f"{Fore.WHITE}{'░' * (bar_width - filled_length)}{Style.RESET_ALL}")
        else:
            bar = '█' * filled_length + '░' * (bar_width - filled_length)
        
        # Construire le message complet
        progress_msg = f"\r{description}: {percentage}% {bar} {current}/{total}"
        
        # S'assurer que le message ne dépasse pas la largeur du terminal
        if len(progress_msg) > self.terminal_width - 2:
            progress_msg = progress_msg[:self.terminal_width - 5] + "..."
            
        # Afficher la progression
        sys.stdout.write(progress_msg)
        sys.stdout.flush()
        
        # Ajouter une nouvelle ligne si c'est la fin
        if current >= total:
            sys.stdout.write("\n")
            sys.stdout.flush()


# Instance globale du logger pour une utilisation facile
logger = UILogger()
