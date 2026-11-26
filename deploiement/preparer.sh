#!/bin/sh
# Prépare l'installation de Demetra sur ce serveur : fichiers d'environnement et dossiers de données.
# Usage (depuis le dossier deploiement/, en root ou avec sudo) : sh preparer.sh demetra.exemple.fr
#
# Écrit, sans jamais les afficher ni écraser l'existant :
#   .env          le domaine, lu par docker compose pour Caddy ;
#   demetra.env   la clé secrète (64 caractères aléatoires) et les réglages de production, en 0600 ;
#   data/ et backup/, appartenant à l'UID 1000 qui fait tourner le conteneur.
# Relancer le script ne change rien à ce qui existe déjà.
set -eu

DOMAIN="${1:-}"
case "$DOMAIN" in
  "" | *[!A-Za-z0-9.-]* | .* | *.)
    echo "Usage : sh preparer.sh <domaine>   (par exemple demetra.exemple.fr)" >&2
    exit 2
    ;;
esac

cd "$(dirname "$0")"
umask 077

if [ -e .env ]; then
  echo ".env existe déjà : laissé tel quel"
else
  printf 'DEMETRA_DOMAIN=%s\n' "$DOMAIN" > .env
  echo ".env écrit"
fi

if [ -e demetra.env ]; then
  echo "demetra.env existe déjà : laissé tel quel (il contient la clé secrète)"
else
  KEY=$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 64)
  [ "${#KEY}" -eq 64 ] || { echo "Impossible de générer la clé secrète" >&2; exit 1; }
  cat > demetra.env <<EOF
# Réglages de production de Demetra (voir DEPLOIEMENT.md). Fichier secret : ne pas versionner, ne pas afficher.
DEMETRA_SECRET_KEY=$KEY
DEMETRA_ALLOWED_HOSTS=$DOMAIN
DEMETRA_CSRF_TRUSTED_ORIGINS=https://$DOMAIN
DEMETRA_BEHIND_PROXY=1
DEMETRA_HSTS_SECONDS=0
DEMETRA_SIGNUP_OPEN=0
EOF
  unset KEY
  chmod 600 demetra.env
  echo "demetra.env écrit (clé secrète générée, non affichée)"
fi

mkdir -p data backup
if [ "$(id -u)" -eq 0 ]; then
  chown 1000:1000 data backup
  echo "data/ et backup/ prêts (UID 1000)"
else
  echo "Attention : lancez en root (sudo) pour donner data/ et backup/ à l'UID 1000, sinon le conteneur ne peut" >&2
  echo "pas écrire sa base. Ou bien : sudo chown 1000:1000 data backup" >&2
fi
