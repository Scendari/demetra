# Brancher une IA en sécurité

Version {{version}}.

Ce chapitre s'adresse à la fois à la personne qui branche son IA (Copilot dans VS Code, Claude Code, Codex,
Cursor…) et à l'IA elle-même. Ces règles valent avant toute autre lecture.

## Obtenir un accès : le lien d'autorisation

La personne n'a ni jeton à copier ni commande à taper. Si `DEMETRA_TOKEN` est vide, c'est **vous, l'IA**, qui
faites la démarche :

1. **Demandez un lien** (sans authentification) :

   ```bash
   curl -sS -X POST -H "Content-Type: application/json" -d '{"client_name": "Copilot VS Code"}' {{origin}}/api/v1/connect
   ```

   Mettez dans `client_name` le nom de votre outil : la personne le verra. La réponse contient `verification_url`,
   `user_code` et `device_code`. Le lien et le code expirent au bout de 10 minutes.

2. **Donnez à la personne le lien `verification_url` et le code `user_code`**, et rien d'autre. Elle ouvre le lien,
   se connecte si besoin, vérifie le code, choisit les permissions et clique « Autoriser ». Le `device_code` est
   secret : ne le montrez pas.

3. **Quand elle vous dit que c'est autorisé, récupérez le jeton et rangez-le sans l'afficher**, en une seule
   commande.

   macOS / Linux : prenez comme profil `~/.zshrc` (macOS) ou `~/.bashrc` (Linux), et remplacez `DEVICE_CODE` :

   ```bash
   PROFILE=~/.zshrc; TOKEN=$(curl -sSf -X POST -H "Accept: text/plain" -H "Content-Type: application/json" \
     -d '{"device_code": "DEVICE_CODE"}' {{origin}}/api/v1/connect/token) && [ -n "$TOKEN" ] \
     && { grep -v '^export DEMETRA_TOKEN=' "$PROFILE" 2>/dev/null; echo "export DEMETRA_TOKEN=\"$TOKEN\""; } > "$PROFILE.demetra" \
     && cat "$PROFILE.demetra" > "$PROFILE" && rm "$PROFILE.demetra" && export DEMETRA_TOKEN="$TOKEN" && unset TOKEN \
     && echo "Jeton rangé dans DEMETRA_TOKEN" || echo "Pas encore autorisé, refusé ou expiré"
   ```

   Windows PowerShell :

   ```powershell
   $r = Invoke-RestMethod -Method Post -Uri {{origin}}/api/v1/connect/token -ContentType 'application/json' -Body '{"device_code": "DEVICE_CODE"}'
   if ($r.token) { [Environment]::SetEnvironmentVariable('DEMETRA_TOKEN', $r.token, 'User'); $env:DEMETRA_TOKEN = $r.token; Remove-Variable r; 'Jeton rangé dans DEMETRA_TOKEN' } else { $r.status }
   ```

   Avec `Accept: text/plain`, la réponse ne contient que le jeton ; sinon c'est un JSON avec `token`.

   - **202** `pending` : la personne n'a pas encore cliqué. Attendez qu'elle le dise, puis relancez la commande.
     Laissez au moins 3 secondes entre deux appels.
   - **403** : elle a refusé. **410** : le lien a expiré ou le jeton a déjà été remis ; recommencez à l'étape 1.

4. **Vérifiez** avec `GET /api/v1/me` (voir « Premier appel »). Si une nouvelle commande ne voit pas la variable,
   relisez le profil (`source ~/.zshrc`) ou demandez de relancer l'éditeur.

## Règles pour l'IA

1. **Le jeton est un mot de passe.** Il vit dans la variable d'environnement `DEMETRA_TOKEN`. Ne le demandez
   jamais dans la conversation : obtenez-le par le lien d'autorisation. Ne l'affichez pas : pas de
   `echo $DEMETRA_TOKEN`, pas de `env` ni de `printenv`, pas de `set -x`. Ne l'écrivez dans aucun fichier de
   projet, script ou commit (seul le profil du shell le contient). Ne le mettez **jamais** dans une URL.

2. **Écrivez toujours `$DEMETRA_TOKEN` dans vos commandes, jamais sa valeur.** Une commande qui contient la
   valeur la laisse dans l'historique de la conversation et du terminal.

3. **Appelez l'API depuis un terminal (curl) ou un client HTTP qui envoie des en-têtes.** Les outils de lecture
   de page web (« fetch », « browse », « ouvrir l'URL ») peuvent lire ce mode d'emploi, qui est public. Ils ne
   peuvent pas s'authentifier, car ils n'envoient pas l'en-tête `Authorization` : l'API répond alors **401**.

4. **Si l'API répond 401 avec un jeton** (révoqué ou expiré), recommencez le lien d'autorisation. Ne demandez
   pas le jeton à la personne.

5. **Si un jeton apparaît en clair** (dans la conversation, une capture, un fichier), dites-le et conseillez de
   le révoquer dans *Compte › Jetons d'accès*. La révocation est immédiate.

6. Un jeton ne permet jamais de rendre un avis ni de partager sans confirmation humaine : ces gestes restent
   réservés aux humains, dans l'interface.

## Premier appel

macOS, Linux, Git Bash, WSL :

```bash
curl -sS -H "Authorization: Bearer $DEMETRA_TOKEN" {{origin}}/api/v1/me
```

Windows PowerShell (écrire `curl.exe`, car `curl` seul y désigne une autre commande) :

```powershell
curl.exe -sS -H "Authorization: Bearer $env:DEMETRA_TOKEN" {{origin}}/api/v1/me
# ou
Invoke-RestMethod {{origin}}/api/v1/me -Headers @{ Authorization = "Bearer $env:DEMETRA_TOKEN" }
```

`/api/v1/me` rend le compte, les portées du jeton, sa date d'expiration et les études auxquelles il est limité.
Lisez ensuite `{{origin}}/api/v1/guide?format=md`.

Pour envoyer un document JSON, mettez-le dans un fichier plutôt que dans la ligne de commande :

```bash
curl -sS -X POST -H "Authorization: Bearer $DEMETRA_TOKEN" -H "Content-Type: application/json" \
     --data @cas.json {{origin}}/api/v1/studies/<id>/cases
```

## Pour la personne

Dites simplement à votre IA : « Connecte-toi à mes études Demetra en suivant {{origin}}/llms.txt ». Elle vous
donne un lien. Ouvrez-le, vérifiez que le code est celui qu'elle affiche, choisissez les permissions, puis
cliquez « Autoriser » et dites-lui que c'est fait. Vous n'avez rien à copier.

Choisissez le moins de droits possible : une durée courte, les seules études concernées, et pas
`share:request` si elle n'en a pas besoin. Chaque accès apparaît dans *Compte › Jetons d'accès*, où vous pouvez
le révoquer.

N'autorisez un lien que si vous venez de le demander à votre IA. Demetra ne vous enverra jamais ce lien par
e-mail ou par message.

## Selon l'outil

- **GitHub Copilot (VS Code)** : utilisez le mode **Agent**, qui peut lancer des commandes dans le terminal, et
  acceptez les commandes proposées (`curl`, ou `Invoke-RestMethod` sous Windows). L'outil de lecture de page de Copilot peut lire ce mode d'emploi,
  pas appeler l'API.
- **Claude Code, Codex, Cursor (agent)** : ils lancent des commandes dans le terminal ; la variable est lue
  depuis la session qui a démarré l'outil.
- **Assistant sans terminal** (chat web seul) : il ne peut pas utiliser l'API. Passez par un outil qui en a un.

## Instructions permanentes pour l'IA

Pour ne pas répéter ces consignes à chaque conversation, copiez ce bloc dans le fichier d'instructions de votre
projet : `.github/copilot-instructions.md` pour Copilot, `AGENTS.md` pour Codex et Copilot, `CLAUDE.md` pour
Claude Code. Il ne contient aucun secret. Les dernières lignes, s'il y en a après « Commencer par… », sont les
consignes propres à votre organisation, écrites par l'administrateur de ce site.

```markdown
## Demetra
- Site : {{origin}} — mode d'emploi : {{origin}}/llms.txt (lire « Brancher une IA en sécurité » en premier).
- Jeton : variable d'environnement DEMETRA_TOKEN. Ne jamais le demander, l'afficher, l'écrire dans un fichier
  ni le mettre dans une URL ; toujours écrire $DEMETRA_TOKEN dans les commandes.
- Appels : depuis le terminal avec curl -H "Authorization: Bearer $DEMETRA_TOKEN" (PowerShell : curl.exe et
  $env:DEMETRA_TOKEN). L'outil de lecture web ne peut pas s'authentifier.
- Variable vide ou 401 : obtenir un accès par le lien d'autorisation (POST {{origin}}/api/v1/connect, voir
  « Brancher une IA en sécurité »), jamais en demandant le jeton.
- Commencer par GET {{origin}}/api/v1/me, puis GET {{origin}}/api/v1/guide?format=md.
```
