<h1 align="center">
  🏠 kovnet
</h1>

<p align="center">
  <em>A CLI and Python SDK for KovNet, the Dutch childcare (kinderopvang) platform.</em><br>
  Contracten bekijken, facturen downloaden en kinderinfo ophalen — zonder de app te openen.
</p>

<p align="center">
  <a href="https://github.com/anneschuth/kovnet-cli/actions"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/anneschuth/kovnet-cli/ci.yml?branch=main&label=CI"></a>
  <a href="https://pypi.org/project/kovnet/"><img alt="PyPI" src="https://img.shields.io/pypi/v/kovnet"></a>
  <a href="https://pypi.org/project/kovnet/"><img alt="Python" src="https://img.shields.io/pypi/pyversions/kovnet"></a>
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/github/license/anneschuth/kovnet-cli"></a>
</p>

---

## Wat doet het?

`kovnet` geeft je toegang tot het [KovNet](https://kovnet.nl) kinderopvangplatform vanuit de terminal:

- **Kinderen** bekijken met geboortedatums
- **Contracten** tonen met start/einddatums
- **Facturen** bekijken en PDF's downloaden
- **Vakanties** tonen
- **Explore** modus om nieuwe endpoints te ontdekken
- **JSON output** voor scripting en automatisering

Authenticatie gaat via session cookies — geen browser nodig.

## Installatie

```bash
# CLI (met pip)
pip install kovnet[cli]

# CLI (met uv, aanbevolen)
uv tool install kovnet[cli]

# CLI (met Homebrew)
brew install anneschuth/tap/kovnet

# Alleen SDK (geen rich/click)
pip install kovnet

# Vanuit source
git clone https://github.com/anneschuth/kovnet-cli.git
cd kovnet-cli
uv tool install .[cli]
```

## Snel aan de slag

```bash
# Inloggen
kovnet login

# Kinderen bekijken
kovnet children

# Contracten
kovnet contracts

# Facturen
kovnet invoices

# Factuur PDF openen (nummer uit de output)
kovnet open 1

# Endpoint verkennen
kovnet explore /parents/contracts/123/invoices
```

## Alle commando's

| Commando | Wat het doet |
|---|---|
| `kovnet login` | Inloggen bij KovNet |
| `kovnet logout` | Sessie verwijderen |
| `kovnet children` | Kinderen tonen |
| `kovnet contracts` | Contracten tonen |
| `kovnet invoices` | Facturen tonen (`--contract ID`) |
| `kovnet holidays` | Vakanties tonen (`--contract ID`) |
| `kovnet open <ref>` | Factuur PDF openen op nummer |
| `kovnet explore <url>` | URL verkennen met sessie cookies |
| `kovnet completion <shell>` | Shell completion script genereren |

### JSON output

Elke data-commando ondersteunt `--json` voor machine-leesbare output:

```bash
kovnet --json contracts
kovnet --json invoices | jq '.[0].bedrag'
```

## Configuratie

### Credentials

Drie manieren om in te loggen:

```bash
# 1. Interactief (prompts)
kovnet login

# 2. Command-line opties
kovnet login -u je@email.nl -p geheim

# 3. Environment variabelen of .env bestand
export KOVNET_USERNAME=je@email.nl
export KOVNET_PASSWORD=geheim
kovnet login
```

Voor `.env` bestanden: plaats ze in `~/.config/kovnet/.env` of in je huidige directory.

### Sessie

Na het inloggen worden session cookies opgeslagen in `~/.config/kovnet/session.json` (mode `0600`). De CLI probeert automatisch opnieuw in te loggen als de sessie verlopen is (met opgeslagen .env credentials).

## Shell completion

```bash
# bash — toevoegen aan ~/.bashrc
eval "$(kovnet completion bash)"

# zsh — toevoegen aan ~/.zshrc
eval "$(kovnet completion zsh)"

# fish
kovnet completion fish > ~/.config/fish/completions/kovnet.fish
```

## SDK gebruik

Het `kovnet` package kan ook als Python SDK gebruikt worden, zonder CLI-afhankelijkheden:

```python
from kovnet import KovNetClient, KovNetAuth

# Inloggen (eenmalig)
session = KovNetAuth.login("je@email.nl", "geheim")

# API gebruiken
with KovNetClient(session) as client:
    for child in client.get_children():
        print(child.get("nickname", child.get("name", "")))

    for contract in client.get_contracts():
        print(contract["start_date"], contract["end_date"])
```

## Development

```bash
git clone https://github.com/anneschuth/kovnet-cli.git
cd kovnet-cli
uv sync --extra dev
uv run pre-commit install
uv run pytest
uv run kovnet --help
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for more details.

## Licentie

MIT — see [LICENSE](LICENSE).
