#!/bin/bash
# oo.sh - Script pour télécharger Odoo Enterprise
# Usage: ./oo.sh <token> <version> [browser]

# Vérifier les paramètres
if [ $# -lt 2 ]; then
  echo "Usage: ./oo.sh <token> <version> [browser]"
  echo "Exemple: ./oo.sh M231207111776235 18.0"
  exit 1
fi

TOKEN=$1
VERSION=$2
BROWSER_MODE=$3
OUTPUT_DIR="odoo-enterprise-${VERSION}"
OUTPUT_FILE="odoo-enterprise-${VERSION}.tar.gz"

# Créer le répertoire de destination s'il n'existe pas
mkdir -p "$OUTPUT_DIR"

echo "Téléchargement de Odoo Enterprise ${VERSION} avec le token ${TOKEN}..."

# Si l'option browser est spécifiée, ouvrir dans le navigateur
if [ "$BROWSER_MODE" = "browser" ]; then
  # URL directe pour le téléchargement
  if [[ "$VERSION" == "18.0" || "$VERSION" == "18" ]]; then
    # URL spécifique pour la version 18
    DOWNLOAD_URL="https://www.odoo.com/fr_FR/thanks/download?code=${TOKEN}&platform_version=src_18e"
  else
    # URL générique pour les autres versions
    DOWNLOAD_URL="https://www.odoo.com/fr_FR/page/download?token=${TOKEN}&platform_version=src_${VERSION}e"
  fi

  # Ouvrir dans le navigateur
  if command -v xdg-open &> /dev/null; then
    echo "Ouverture de l'URL dans votre navigateur par défaut..."
    xdg-open "$DOWNLOAD_URL"
  elif command -v open &> /dev/null; then
    echo "Ouverture de l'URL dans votre navigateur par défaut..."
    open "$DOWNLOAD_URL"
  else
    echo "Impossible d'ouvrir automatiquement un navigateur."
    echo "Veuillez copier et coller cette URL dans votre navigateur:"
    echo "$DOWNLOAD_URL"
  fi

  echo ""
  echo "Instructions après téléchargement:"
  echo "1. Attendez que le téléchargement se termine dans votre navigateur"
  echo "2. Le fichier sera probablement sauvegardé dans votre dossier Téléchargements"
  echo "3. Déplacez-le dans le répertoire de travail actuel:"
  echo "   mv ~/Téléchargements/odoo_enterprise-*.tar.gz ."
  echo "4. Extrayez l'archive dans le répertoire $OUTPUT_DIR:"
  echo "   tar -xzf odoo_enterprise-*.tar.gz -C $OUTPUT_DIR --strip-components=1"
  exit 0
fi

# Sinon, essayer de télécharger automatiquement

# URL pour la page de remerciement
if [[ "$VERSION" == "18.0" || "$VERSION" == "18" ]]; then
  # URL spécifique pour la version 18
  THANKS_URL="https://www.odoo.com/fr_FR/thanks/download?code=${TOKEN}&platform_version=src_18e"
else
  # URL générique pour les autres versions
  THANKS_URL="https://www.odoo.com/fr_FR/thanks/download?code=${TOKEN}&platform_version=src_${VERSION}e"
fi

# Télécharger la page de remerciement et analyser pour trouver l'URL directe
echo "Récupération de l'URL de téléchargement direct..."
echo "thanks_url: $THANKS_URL"
HTML_CONTENT=$(curl -s "$THANKS_URL")

# Extraire l'URL directe de téléchargement à partir du contenu HTML
DIRECT_URL=$(echo "$HTML_CONTENT" | grep -o "https://download.odoocdn.com/download/[^'\"]*" | head -n 1)

if [ -z "$DIRECT_URL" ]; then
  echo "Impossible de trouver l'URL directe de téléchargement dans la page."
  echo "Essai avec la méthode payload..."
  
  # Essayer de trouver le payload
  PAYLOAD=$(echo "$HTML_CONTENT" | grep -o "payload=[^'\"]*" | head -n 1)
  
  if [ -n "$PAYLOAD" ]; then
    # Construire l'URL avec le payload
    DIRECT_URL="https://download.odoocdn.com/download/18e/src?${PAYLOAD}"
    echo "URL avec payload trouvée: $DIRECT_URL"
  else
    echo "Impossible de trouver le payload dans la page HTML."
    echo "Essai avec d'autres méthodes..."
  fi
fi

# Si nous avons trouvé une URL directe, l'utiliser pour télécharger
if [ -n "$DIRECT_URL" ]; then
  echo "URL directe trouvée: $DIRECT_URL"
  echo "Téléchargement direct de l'archive..."
  
  curl -L -o "$OUTPUT_FILE" "$DIRECT_URL"
  
  # Vérifier si curl a réussi
  if [ $? -eq 0 ] && [ -f "$OUTPUT_FILE" ]; then
    FILE_TYPE=$(file -b "$OUTPUT_FILE" | cut -d' ' -f1)
    if [[ "$FILE_TYPE" == "HTML" ]]; then
      echo "Le fichier téléchargé semble être une page HTML et non une archive."
      mv "$OUTPUT_FILE" "error-${OUTPUT_FILE}-direct.html"
      echo "La page a été enregistrée dans error-${OUTPUT_FILE}-direct.html"
    else
      # Le téléchargement semble avoir réussi
      echo "Téléchargement réussi: $OUTPUT_FILE ($(du -h "$OUTPUT_FILE" | cut -f1))"
      echo "Extraction de l'archive..."
      tar -xzf "$OUTPUT_FILE" -C "$OUTPUT_DIR" --strip-components=1
      
      if [ $? -eq 0 ]; then
        echo "Extraction réussie dans le dossier $OUTPUT_DIR"
        echo ""
        echo "Vous pouvez maintenant utiliser ce dossier avec odoo_docker_generator.py:"
        echo "python odoo_docker_generator.py --version $VERSION --edition enterprise --addons-path $(pwd)/$OUTPUT_DIR --build"
        exit 0
      else
        echo "Erreur lors de l'extraction de l'archive."
      fi
    fi
  else
    echo "Échec du téléchargement direct."
  fi
fi

echo "Toutes les méthodes automatiques ont échoué."
echo "Veuillez utiliser l'option du navigateur en exécutant:"
echo "./oo.sh $TOKEN $VERSION browser"

exit 1
