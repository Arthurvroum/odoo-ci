# Odoo Docker Generator

Ce projet permet d'automatiser la création de fichiers docker-compose.yml pour différentes versions d'Odoo (Enterprise et Community). Il utilise une architecture modulaire avec des classes dédiées pour chaque responsabilité.

## Structure du projet

Le projet est organisé en modules:

- `modules/templating`: Gestion des templates (Jinja2)
- `modules/odoo_versioning`: Gestion des versions d'Odoo et téléchargement des archives Enterprise
- `modules/odoo_config`: Génération des fichiers de configuration d'Odoo
- `modules/docker_compose`: Génération des fichiers docker-compose.yml
- `modules/docker_manager`: Construction et démarrage des conteneurs Docker
- `modules/ui_logger`: Gestion des logs avec animations, couleurs et barres de progression

## Prérequis

- Python 3.6+
- Docker et Docker Compose installés
- Modules Python requis: PyYAML, Jinja2, requests, tqdm, colorama

## Installation

```bash
# Installer les dépendances
pip install pyyaml jinja2 requests tqdm colorama
```

## Utilisation

Le script peut être utilisé pour générer des fichiers docker-compose.yml pour différentes versions d'Odoo:

```bash
# Générer un fichier docker-compose pour Odoo 16 Community
python odoo_docker_gen.py --version 16 --edition community

# Générer un fichier docker-compose pour Odoo 17 Enterprise
python odoo_docker_gen.py --version 17 --edition enterprise

# Spécifier un port personnalisé (par défaut: 8069)
python odoo_docker_gen.py --version 16 --edition community --port 8080

# Générer et démarrer les conteneurs immédiatement
python odoo_docker_gen.py --version 16 --edition community --build

# Utiliser un chemin spécifique pour les addons personnalisés
python odoo_docker_gen.py --version 17 --edition enterprise --addons-path ~/path/to/addons

# Télécharger l'édition Enterprise avec un token d'accès
python odoo_docker_gen.py --version 18 --edition enterprise --enterprise-token YOUR_TOKEN
```

## Structure des fichiers générés

Le script génère pour chaque instance:

1. Un dossier dans `docker-compose-files` (par défaut) contenant:
   - `docker-compose.yml`: Configuration Docker Compose
   - `README.md`: Instructions d'utilisation
   - `list_modules.py`: Script pour lister les modules clients
   - `.env`: Configuration du nom du projet Docker Compose
   - `custom-addons/`: Dossier pour vos modules personnalisés
   - `odoo-data/addons/`: Pour les modules additionnels
   - `odoo-data/etc/`: Configuration Odoo (odoo.conf)
   - `odoo-data/filestore/`: Stockage des fichiers
   - `postgresql/`: Données PostgreSQL
   - `enterprise/`: Code source Odoo Enterprise (si édition Enterprise)

## Fonctionnalités spécifiques

### Téléchargement et cache Enterprise

Pour l'édition Enterprise, le script:
1. Télécharge le code source depuis odoo.com avec votre token
2. Stocke une copie dans le cache (`enterprise_cache/`) pour éviter les téléchargements redondants
3. Configure automatiquement les chemins d'addons dans odoo.conf

### Script de listing des modules

Chaque instance générée inclut un script `list_modules.py` qui:
- Identifie tous les modules par leur fichier `__manifest__.py`
- Affiche les informations des modules (nom, description, dépendances)
- Génère un rapport JSON pour une utilisation programmatique

### Interface utilisateur améliorée

Le module `ui_logger` fournit une expérience utilisateur améliorée avec:

- **Logs colorés**: Messages formatés avec différentes couleurs selon leur type (info, succès, erreur, etc.)
- **Animations**: Spinners pendant les opérations longues et barres de progression pour les téléchargements
- **Sections visuelles**: Séparation claire des différentes étapes du processus
- **Barres de progression personnalisées**: Affichage optimisé pendant l'extraction d'archives
- **Mode verbeux/silencieux**: Contrôle du niveau de détail des logs
- **Détection automatique du terminal**: Adapte l'affichage selon l'environnement d'exécution

Exemple d'utilisation du logger:
```python
from modules.ui_logger import logger

# Affichage de messages colorés
logger.info("Information standard")
logger.success("Opération réussie")
logger.warning("Attention")
logger.error("Erreur détectée")

# Créer une section visuelle
logger.section("Configuration d'Odoo")

# Afficher un spinner pendant une opération longue
logger.start_spinner("Téléchargement en cours")
# ... opération longue ...
logger.stop_spinner(success=True, message="Téléchargement terminé")

# Afficher une barre de progression
with logger.progress_bar(total=100, desc="Installation") as pbar:
    for i in range(100):
        # ... traitement ...
        pbar.update(1)
```

## Personnalisation avancée

Pour personnaliser davantage les conteneurs ou ajouter des services supplémentaires:
1. Modifiez les templates dans le dossier `templates/`
2. Étendez les modules existants ou créez de nouveaux modules dans le dossier `modules/`

## Extension du projet

### Création d'un nouveau module

Pour créer un nouveau module, suivez ces étapes:

1. Créez un nouveau dossier dans `modules/`:
```bash
mkdir -p modules/mon_module
touch modules/mon_module/__init__.py
```

2. Créez une classe pour votre module dans `modules/mon_module/__init__.py`:
```python
class MonModule:
    def __init__(self):
        # Initialisation
        pass
    
    def ma_fonction(self):
        # Fonctionnalité
        pass
```

3. Importez et utilisez votre module dans `odoo_docker_gen.py`:
```python
from modules.mon_module import MonModule

# Dans une fonction
mon_module = MonModule()
mon_module.ma_fonction()
```

### Modification des templates

Les templates utilisent Jinja2 et sont situés dans le dossier `templates/`. Vous pouvez:

1. Modifier les templates existants:
   - `docker-compose.yml.j2`: Structure du fichier docker-compose
   - `README.md.j2`: Documentation générée
   - `list_modules.py.j2`: Script de listing des modules

2. Ajouter de nouveaux templates et les utiliser via le TemplateManager:
```python
# Dans votre code
template_content = template_manager.render_template('mon_template.j2', context)
```

### Personnalisation de l'interface utilisateur

Vous pouvez personnaliser l'interface utilisateur en modifiant l'instance du logger :

```python
from modules.ui_logger import UILogger

# Créer une instance personnalisée
custom_logger = UILogger(
    verbose=True,      # True pour afficher tous les messages, False pour un mode minimal
    use_animations=True,  # True pour activer les spinners et animations
    use_colors=True    # True pour utiliser les couleurs dans le terminal
)

# Utiliser l'instance personnalisée
custom_logger.info("Message personnalisé")
```

Le logger est compatible avec différents environnements:
- Détecte automatiquement si le script s'exécute dans un terminal interactif
- Désactive automatiquement les animations si redirigé vers un fichier
- S'adapte à la largeur du terminal pour l'affichage des barres de progression

## Commandes utiles

### Gestion des instances Odoo

Pour chaque instance générée, vous pouvez:

```bash
# Démarrer les conteneurs
cd docker-compose-files/odoo-18.0-enterprise
docker-compose up -d

# Arrêter les conteneurs (sans supprimer les données)
docker-compose down

# Supprimer complètement l'instance et ses données
docker-compose down -v

# Lister les modules clients
./list_modules.py

# Voir les logs en temps réel
docker-compose logs -f

# Exécuter une commande dans le conteneur Odoo
docker-compose exec odoo odoo --help
```

## Nouvelles fonctionnalités

Cette version modulaire apporte plusieurs améliorations:

- **Architecture modulaire**: Code organisé en modules séparés avec des responsabilités claires
- **Cache Enterprise**: Téléchargement optimisé du code Enterprise avec mise en cache
- **Script de listing des modules**: Outil pour explorer les modules disponibles
- **Template personnalisables**: Facile à adapter à vos besoins spécifiques
- **Documentation générée**: README automatiquement créé pour chaque instance
- **Interface utilisateur améliorée**: Logs colorés, animations et barres de progression
- **Feedback visuel**: Spinners et indicateurs d'état lors des opérations longues
- **Barres de progression robustes**: Affichage stable des barres de progression lors de l'extraction d'archives

## Contribution

Les contributions sont les bienvenues! Voici comment vous pouvez contribuer:

1. Fork le projet
2. Créez une branche pour votre fonctionnalité (`git checkout -b feature/amazing-feature`)
3. Commitez vos changements (`git commit -m 'Add some amazing feature'`)
4. Push vers la branche (`git push origin feature/amazing-feature`)
5. Ouvrez une Pull Request