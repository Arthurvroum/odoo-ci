# Odoo Docker Generator

Ce script Python permet d'automatiser la création de fichiers docker-compose.yml pour différentes versions d'Odoo (Enterprise et Community).

## Prérequis

- Python 3.6+
- Docker et Docker Compose installés
- Le module PyYAML installé (`pip install pyyaml`)

## Installation

```bash
# Installer les dépendances
pip install pyyaml
```

## Utilisation

Le script peut être utilisé pour générer des fichiers docker-compose.yml pour différentes versions d'Odoo:

```bash
# Générer un fichier docker-compose pour Odoo 16 Community
python odoo_docker_generator.py --version 16 --edition community

# Générer un fichier docker-compose pour Odoo 17 Enterprise
python odoo_docker_generator.py --version 17 --edition enterprise

# Spécifier un port personnalisé (par défaut: 8069)
python odoo_docker_generator.py --version 16 --edition community --port 8080

# Générer et démarrer les conteneurs immédiatement
python odoo_docker_generator.py --version 16 --edition community --build
```

## Structure des fichiers générés

Le script génère:

1. Un dossier `docker-compose-files` contenant les fichiers docker-compose.yml générés
2. Des dossiers pour les addons personnalisés au format `odoo-{version}-{edition}-addons`
3. Lors de l'exécution, les dossiers suivants sont créés:
   - `odoo-data/addons`: pour les modules additionnels
   - `odoo-data/etc`: pour les fichiers de configuration
   - `odoo-data/filestore`: pour stocker les fichiers
   - `postgresql`: pour les données PostgreSQL

## Remarque importante

Pour l'édition Enterprise, vous aurez besoin d'accéder au dépôt privé d'Odoo ou d'adapter le script pour utiliser votre propre image Docker contenant l'édition Enterprise. Le script utilise actuellement un nom d'image fictif (`odoo/odoo-enterprise`) qui doit être remplacé par votre image réelle.

## Personnalisation avancée

Pour personnaliser davantage les conteneurs ou ajouter des services supplémentaires, vous pouvez modifier la méthode `generate_docker_compose` dans le script.