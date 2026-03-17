"""KovNet CLI - command-line interface for the KovNet childcare platform.

Usage:
    kovnet login                         # Authenticate
    kovnet logout                        # Remove session
    kovnet children                      # List children
    kovnet contracts                     # List contracts
    kovnet invoices [--contract ID]      # List invoices
    kovnet holidays [--contract ID]      # List holidays
    kovnet open REF                      # Open invoice PDF by number
    kovnet explore URL                   # Fetch URL with session cookies
    kovnet completion SHELL              # Output shell completion script
"""

from __future__ import annotations

__version__ = "1.1.0"

import json
import sys
from typing import Any

import click
import httpx
from rich.console import Console
from rich.table import Table

from .client import KovNetAuth, KovNetClient

console = Console()

_last_invoice_refs: list[dict[str, str]] = []


class AliasedGroup(click.Group):
    """Click group that handles errors gracefully."""

    pass


@click.group(cls=AliasedGroup)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output als JSON")
@click.version_option(version=__version__, prog_name="kovnet")
@click.pass_context
def cli(ctx: click.Context, as_json: bool) -> None:
    """KovNet CLI - toegang tot het KovNet kinderopvangplatform vanuit de terminal."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = as_json


@cli.command()
@click.option("-u", "--username", default=None, help="Email (of KOVNET_USERNAME env)")
@click.option("-p", "--password", default=None, help="Wachtwoord (of KOVNET_PASSWORD env)")
@click.option(
    "--store", is_flag=True, default=False, help="Credentials opslaan in ~/.config/kovnet/.env"
)
@click.option("--location", default=None, help="Locatie ID (bij meerdere locaties)")
@click.option("--code", default=None, help="2FA code (indien vereist)")
def login(
    username: str | None,
    password: str | None,
    store: bool,
    location: str | None,
    code: str | None,
) -> None:
    """Inloggen bij KovNet."""
    import os

    from dotenv import load_dotenv

    from .client import SESSION_PATH

    # Load .env files: ~/.config/kovnet/.env first, then local .env
    env_path = SESSION_PATH.parent / ".env"
    load_dotenv(env_path)
    load_dotenv()  # local .env

    username = username or os.environ.get("KOVNET_USERNAME", "")
    password = password or os.environ.get("KOVNET_PASSWORD", "")

    try:
        session = KovNetAuth.login(
            username=username or None,
            password=password or None,
            location_id=location,
            twofa_code=code,
        )
        console.print("[green]Login geslaagd![/]")
        if session.get("location_id"):
            console.print(f"  Locatie ID: {session['location_id']}")
        console.print(f"  Gebruiker: {session.get('username', '')}")

        if store and username and password:
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.write_text(f"KOVNET_USERNAME={username}\nKOVNET_PASSWORD={password}\n")
            env_path.chmod(0o600)
            console.print(f"  [dim]Credentials opgeslagen in {env_path}[/]")
    except Exception as e:
        console.print(f"[red]Login mislukt: {e}[/]")
        sys.exit(1)


@cli.command()
def logout() -> None:
    """Uitloggen (sessie verwijderen)."""
    from .client import SESSION_PATH

    if SESSION_PATH.exists():
        SESSION_PATH.unlink()
        console.print("[green]Uitgelogd.[/]")
    else:
        console.print("[dim]Je was al uitgelogd.[/]")


@cli.command()
@click.option("--location", default=None, help="Locatie ID")
@click.pass_context
def children(ctx: click.Context, location: str | None) -> None:
    """Kinderen tonen."""
    as_json = ctx.obj["json"]
    with KovNetClient() as client:
        items = client.get_children(location_id=location)

        if as_json:
            print(json.dumps(items, indent=2, default=str))
            return

        if not items:
            console.print("[dim]Geen kinderen gevonden[/]")
            return

        for child in items:
            name = child.get("nickname") or child.get("name", "")
            bsnr = child.get("bsnr", "")
            dob = child.get("date_of_birth", "")
            parts = [f"[bold]{name}[/]" if name else ""]
            if dob:
                parts.append(f"geb. {dob}")
            if bsnr:
                parts.append(f"BSN: {bsnr}")
            console.print("  " + " | ".join(p for p in parts if p))


@cli.command()
@click.option("--location", default=None, help="Locatie ID")
@click.pass_context
def contracts(ctx: click.Context, location: str | None) -> None:
    """Contracten tonen."""
    as_json = ctx.obj["json"]
    with KovNetClient() as client:
        items = client.get_contracts(location_id=location)

        if as_json:
            print(json.dumps(items, indent=2, default=str))
            return

        if not items:
            console.print("[dim]Geen contracten gevonden[/]")
            return

        table = Table(title="Contracten")
        table.add_column("ID", style="dim")
        table.add_column("Start", style="green")
        table.add_column("Eind", style="red")
        table.add_column("Berekendatum", style="cyan")

        for c in items:
            cid = str(c.get("id", ""))
            start = c.get("start_date", "")
            end = c.get("end_date", "")
            calc = c.get("calculation_date", "")
            table.add_row(cid, start, end, calc)

        console.print(table)


@cli.command()
@click.option("--contract", default=None, help="Contract ID (toont alle contracten als leeg)")
@click.option("--location", default=None, help="Locatie ID")
@click.pass_context
def invoices(ctx: click.Context, contract: str | None, location: str | None) -> None:
    """Facturen tonen."""
    as_json = ctx.obj["json"]
    with KovNetClient() as client:
        if contract:
            contract_ids = [contract]
        else:
            # Get all contracts and show invoices for each
            contracts_list = client.get_contracts(location_id=location)
            contract_ids = [str(c.get("id", "")) for c in contracts_list if c.get("id")]

        all_invoices: list[dict[str, str]] = []
        for cid in contract_ids:
            inv = client.get_invoices(cid)
            for i in inv:
                i["contract_id"] = cid
            all_invoices.extend(inv)

        if as_json:
            print(json.dumps(all_invoices, indent=2, default=str))
            return

        if not all_invoices:
            console.print("[dim]Geen facturen gevonden[/]")
            return

        _last_invoice_refs.clear()

        table = Table(title="Facturen")
        table.add_column("#", style="dim")
        table.add_column("Nr", style="bold")
        table.add_column("Datum", style="cyan")
        table.add_column("Maand", style="cyan")
        table.add_column("Jaar", style="cyan")
        table.add_column("Bedrag", style="green")
        table.add_column("Contract", style="dim")

        for idx, inv in enumerate(all_invoices, 1):
            _last_invoice_refs.append(inv)
            table.add_row(
                str(idx),
                inv.get("nr", ""),
                inv.get("datum", ""),
                inv.get("maand", ""),
                inv.get("jaar", ""),
                inv.get("bedrag", ""),
                inv.get("contract_id", ""),
            )

        console.print(table)


@cli.command()
@click.option("--contract", default=None, help="Contract ID")
@click.option("--location", default=None, help="Locatie ID")
@click.pass_context
def holidays(ctx: click.Context, contract: str | None, location: str | None) -> None:
    """Vakanties tonen."""
    as_json = ctx.obj["json"]
    with KovNetClient() as client:
        if contract:
            contract_ids = [contract]
        else:
            contracts_list = client.get_contracts(location_id=location)
            contract_ids = [str(c.get("id", "")) for c in contracts_list if c.get("id")]

        all_holidays: list[dict[str, Any]] = []
        for cid in contract_ids:
            hols = client.get_holidays(cid, location_id=location)
            for h in hols:
                h["contract_id"] = cid
            all_holidays.extend(hols)

        if as_json:
            print(json.dumps(all_holidays, indent=2, default=str))
            return

        if not all_holidays:
            console.print("[dim]Geen vakanties gevonden[/]")
            return

        for h in all_holidays:
            console.print(f"  {h}")


@cli.command()
@click.pass_context
def chats(ctx: click.Context) -> None:
    """Chatrooms tonen."""
    as_json = ctx.obj["json"]
    with KovNetClient() as client:
        items = client.get_chats()

        if as_json:
            print(json.dumps(items, indent=2, default=str))
            return

        if not items:
            console.print("[dim]Geen chats gevonden[/]")
            return

        table = Table(title="Chats")
        table.add_column("Key", style="dim")
        table.add_column("Groep", style="bold")
        table.add_column("Kind", style="cyan")
        table.add_column("Locatie", style="dim")
        table.add_column("Ongelezen", style="red")
        table.add_column("Vandaag", style="green")

        for chat in items:
            table.add_row(
                chat.get("chat_key", ""),
                chat.get("group", ""),
                chat.get("child", ""),
                chat.get("location", ""),
                chat.get("unread", "0"),
                "●" if chat.get("today") == "true" else "",
            )

        console.print(table)


@cli.command()
@click.argument("chat_key", type=str)
@click.pass_context
def messages(ctx: click.Context, chat_key: str) -> None:
    """Berichten in een chat tonen.

    CHAT_KEY is het chat ID (bijv. 19868_425817, uit `kovnet chats`).
    """
    as_json = ctx.obj["json"]
    with KovNetClient() as client:
        items = client.get_chat_messages(chat_key)

        if as_json:
            print(json.dumps(items, indent=2, default=str))
            return

        if not items:
            console.print("[dim]Geen berichten gevonden[/]")
            return

        for msg in items:
            dt = msg.get("datetime", "")
            sender = msg.get("sender", "")
            text = msg.get("text", "")
            is_parent = msg.get("is_parent") == "true"

            style = "bold" if is_parent else "bold cyan"
            console.print(f"  [dim]{dt}[/] [{style}]{sender}:[/] {text}")


@click.command("open")
@click.argument("ref", type=str)
def open_invoice(ref: str) -> None:
    """Open een factuur PDF in de standaard app.

    REF is een nummer (uit invoices output) of een URL-pad.
    """
    import subprocess
    import tempfile
    from pathlib import Path

    if ref.isdigit():
        idx = int(ref)
        if not _last_invoice_refs:
            console.print("[red]Geen facturen gevonden. Run eerst `kovnet invoices`.[/]")
            sys.exit(1)
        if idx < 1 or idx > len(_last_invoice_refs):
            console.print(
                f"[red]Nummer {idx} bestaat niet. Beschikbaar: 1-{len(_last_invoice_refs)}[/]"
            )
            sys.exit(1)
        inv = _last_invoice_refs[idx - 1]
        contract_id = inv.get("contract_id", "")
        pdf_url = inv.get("pdf_url", "")
        if not pdf_url or not contract_id:
            console.print("[red]Geen PDF URL gevonden voor deze factuur.[/]")
            sys.exit(1)

        # Extract invoice ID from pdf_url
        invoice_id = pdf_url.rstrip("/").split("/")[-1].replace(".pdf", "")

        with KovNetClient() as client:
            console.print(f"  Downloaden factuur {inv.get('nr', ref)}...", end="")
            pdf_bytes = client.get_invoice_pdf(contract_id, invoice_id)

        filename = f"kovnet-factuur-{inv.get('nr', ref)}.pdf"
        tmp = Path(tempfile.gettempdir()) / filename
        tmp.write_bytes(pdf_bytes)
        console.print(f" [green]ok[/green] ({len(pdf_bytes) // 1024}KB)")
        subprocess.run(["open", str(tmp)])
    else:
        # Treat as a URL path to fetch
        with KovNetClient() as client:
            console.print(f"  Downloaden {ref}...", end="")
            data = client._get_bytes(ref)

        filename = ref.rstrip("/").split("/")[-1]
        tmp = Path(tempfile.gettempdir()) / f"kovnet-{filename}"
        tmp.write_bytes(data)
        console.print(f" [green]ok[/green] ({len(data) // 1024}KB)")
        subprocess.run(["open", str(tmp)])


cli.add_command(open_invoice)


@cli.command()
@click.argument("url", type=str)
@click.pass_context
def explore(ctx: click.Context, url: str) -> None:
    """Verken een URL met sessie cookies.

    Handig om nieuwe endpoints te ontdekken.
    Geef een pad op (bijv. /parents/contracts/123/invoices).
    """
    as_json = ctx.obj["json"]
    with KovNetClient() as client:
        resp = client.explore(url)
        content_type = resp.headers.get("content-type", "")

        if as_json or "json" in content_type:
            try:
                data = resp.json()
                print(json.dumps(data, indent=2, default=str))
            except Exception:
                print(resp.text)
        else:
            print(resp.text)


@cli.command()
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def completion(shell: str) -> None:
    """Output shell completion script.

    Add to your shell config to enable tab completion:

    \b
      # bash (~/.bashrc)
      eval "$(kovnet completion bash)"

    \b
      # zsh (~/.zshrc)
      eval "$(kovnet completion zsh)"

    \b
      # fish (~/.config/fish/completions/kovnet.fish)
      kovnet completion fish > ~/.config/fish/completions/kovnet.fish
    """
    import os

    os.environ["_KOVNET_COMPLETE"] = f"{shell}_source"
    try:
        cli.main(standalone_mode=False)
    except SystemExit:
        pass
    finally:
        del os.environ["_KOVNET_COMPLETE"]


def main() -> None:
    try:
        cli(standalone_mode=True)
    except RuntimeError as e:
        console.print(f"[red]{e}[/]")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            console.print("[red]Sessie verlopen. Run `kovnet login` opnieuw.[/]")
        else:
            console.print(f"[red]API fout: {e.response.status_code}[/]")
        sys.exit(1)


if __name__ == "__main__":
    main()
