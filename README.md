# Gold Trading Agent — Système d'aide à la décision sur l'or (XAU/USD)

Système multi-agents qui analyse l'or toutes les heures (technique, macro via le dollar,
sentiment des news) et envoie une décision expliquée par Telegram. **Ce n'est pas un bot
d'exécution automatique** : c'est toi qui décides et qui passes l'ordre sur XTB.

⚠️ **Avertissement** : cet outil ne constitue pas un conseil financier. Le trading sur
marge/CFD comporte un risque réel de perte en capital. Les décisions générées sont basées
sur des règles simples et peuvent se tromper.

## 1. Obtenir les clés API (gratuit)

### Twelve Data (données de prix)
1. Va sur https://twelvedata.com et crée un compte gratuit
2. Récupère ta clé API dans le dashboard

### NewsAPI (actualités)
1. Va sur https://newsapi.org et crée un compte gratuit
2. Récupère ta clé API

### Bot Telegram
1. Ouvre Telegram, cherche `@BotFather`
2. Tape `/newbot`, choisis un nom et un username pour ton bot
3. Il te donne un **token** — garde-le
4. Envoie n'importe quel message à ton nouveau bot (pour l'initialiser)
5. Va sur `https://api.telegram.org/bot<TON_TOKEN>/getUpdates` dans ton navigateur
6. Cherche `"chat":{"id":...}` dans la réponse — c'est ton **chat_id**

## 2. Configuration locale

```bash
cp .env.example .env
# Édite .env et colle tes 4 clés/tokens dedans
pip install -r requirements.txt
```

## 3. Tester en local

```bash
python main.py
```

Tu devrais recevoir une première notification Telegram dans la minute, puis une toutes
les heures. Arrête avec `Ctrl+C`.

## 4. Déployer 24/7 gratuitement (pour que ça tourne sans ton ordi allumé)

### Option recommandée : Railway ou Render

1. Crée un compte sur https://render.com (ou railway.app)
2. Crée un nouveau "Background Worker" (pas un "Web Service")
3. Connecte ton repo GitHub (il faut d'abord pousser ce dossier sur GitHub — dis-moi si
   tu as besoin d'aide pour ça)
4. Commande de démarrage : `python main.py`
5. Ajoute tes 4 variables d'environnement (les mêmes que dans `.env`) dans les
   "Environment Variables" du service
6. Déploie — le service tourne en continu et t'envoie les notifs Telegram

## 5. Structure du projet

```
gold-trading-agent/
├── config.py                  # Paramètres et clés (lues depuis .env)
├── main.py                    # Orchestrateur, boucle toutes les heures
├── telegram_bot.py            # Formatage + envoi des notifications
├── agents/
│   ├── data_agent.py          # Récupère les prix (or + dollar)
│   ├── technical_agent.py     # Indicateurs techniques (SMA, RSI, ATR)
│   ├── macro_agent.py         # Proxy macro via le dollar (DXY)
│   ├── sentiment_agent.py     # Analyse des titres d'actualité
│   └── decision_agent.py      # Agrège tout, sort LONG/SHORT/NEUTRE
├── requirements.txt
└── .env.example
```

## Version 2 : ce qui a été renforcé

- **Calendrier économique réel** : le système lit maintenant le flux gratuit
  ForexFactory (Fed, CPI, NFP, PCE...) et **bascule automatiquement en NEUTRE**
  si un événement majeur est imminent (< 2h) — la volatilité pré-annonce rend
  toute prédiction peu fiable, mieux vaut s'abstenir
- **Sentiment renforcé** : recherche sur 3 axes (or, Fed/taux, dollar/inflation),
  dédoublonnage des titres, et score pondéré par la densité de signal détecté
  (un ratio extrême sur 2 titres ne pèse plus autant qu'un vrai consensus sur 15)

## Limites connues restantes (v2)

- Le calendrier signale la présence d'un événement mais n'essaie pas encore de
  comparer l'actual vs le forecast une fois publié (amélioration possible v3)
- Le sentiment reste une analyse lexicale (mots-clés), pas un vrai modèle NLP
- **Pas de backtesting** : le système n'a pas encore été testé sur données
  historiques pour valider sa fiabilité avant la semaine de démo

## Prochaines étapes suggérées

1. Faire tourner le système une semaine en observant sans forcément suivre chaque signal
2. Logger chaque décision + résultat réel pour calculer un vrai taux de réussite
3. Ajuster les poids dans `config.py` (`WEIGHTS`) selon ce qui marche le mieux
4. Éventuellement ajouter un vrai calendrier économique (v2)
