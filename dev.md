# Notes de développement

Procédure complète (environnement, tests, ajout de commandes, publication) : voir [CONTRIBUTING.md](CONTRIBUTING.md).

Nouvelle version, en bref :

1. modifier `version` dans `custom_components/philips_dline_sicp/manifest.json`
2. compléter `CHANGELOG.md`
3. commiter, tagger et pousser :

```bash
git add .
git commit -m "chore: version 1.2.3"
git tag v1.2.3
git push origin main v1.2.3
```
