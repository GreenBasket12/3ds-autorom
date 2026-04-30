import os
import subprocess
import platform
import zipfile
import shutil
import psutil
import httpx
import readchar
import rarfile
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import (
    Progress, DownloadColumn, TransferSpeedColumn,
    TimeRemainingColumn, BarColumn, TextColumn
)
from rich.prompt import Prompt, IntPrompt

console = Console()

ARCHIVE_IDENTIFIER = '3dscia_202310'
DESTINATION_PATH = Path.cwd() / 'output'
EXCLUDE_FILES = {
    '3dscia_202310_archive.torrent',
    '3dscia_202310_files.xml',
    '3dscia_202310_meta.sqlite',
    '3dscia_202310_meta.xml',
}


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def extract_archive(file_path: Path, destination: Path) -> None:
    ensure_dir(destination)
    suffix = file_path.suffix.lower()
    if suffix == '.rar':
        with rarfile.RarFile(file_path, 'r') as rar:
            rar.extractall(destination)
    elif suffix == '.zip':
        with zipfile.ZipFile(file_path, 'r') as zf:
            zf.extractall(destination)


def download_file(item_id: str, file_name: str, destination: Path) -> Optional[Path]:
    url = f'https://archive.org/download/{item_id}/{file_name}'
    ensure_dir(destination)
    output_path = destination / file_name

    with Progress(
        TextColumn("[bold blue]{task.fields[filename]}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Downloading", filename=file_name, total=None)
        try:
            with httpx.stream('GET', url, follow_redirects=True, verify=False, timeout=30) as response:
                response.raise_for_status()
                total = int(response.headers.get('content-length', 0)) or None
                progress.update(task, total=total)
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_bytes(chunk_size=65536):
                        f.write(chunk)
                        progress.advance(task, len(chunk))
        except httpx.HTTPError as e:
            console.print(f"[red]Download failed: {e}[/red]")
            return None

    console.print(f"[green]✓ Download complete:[/green] {file_name}")

    extracted_path = destination / output_path.stem
    console.print(f"Extracting [cyan]{file_name}[/cyan]...")
    try:
        extract_archive(output_path, extracted_path)
    except Exception as e:
        console.print(f"[red]Extraction failed: {e}[/red]")
        return None

    console.print(f"[green]✓ Extraction complete[/green]")
    return extracted_path


def get_file_list() -> list[str]:
    url = f'https://archive.org/download/{ARCHIVE_IDENTIFIER}/{ARCHIVE_IDENTIFIER}_files.xml'
    try:
        with httpx.Client(verify=False, timeout=15) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as e:
        console.print(f"[red]Failed to fetch file list: {e}[/red]")
        return []

    root = ET.fromstring(response.content)
    files = []
    for f in root.findall('.//file'):
        name = f.get('name')
        if name and name.endswith(('.rar', '.zip')) and name not in EXCLUDE_FILES:
            files.append(name)
    return files


def list_usb_devices() -> list[str]:
    system = platform.system()
    if system == 'Windows':
        return [p.device for p in psutil.disk_partitions() if 'removable' in p.opts]
    elif system == 'Linux':
        result = subprocess.run(['lsblk', '-o', 'NAME,MOUNTPOINT'], capture_output=True, text=True)
        devices = []
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and '/media' in parts[1]:
                devices.append(parts[1])
        return devices
    return []


def move_to_usb(source: Path, usb_device: str) -> None:
    usb_path = Path(usb_device)
    moved = 0
    for file in source.rglob('*'):
        if not file.is_file():
            continue
        suffix = file.suffix.lower()
        if suffix == '.cia':
            target_dir = usb_path / 'cia'
        elif suffix == '.nds':
            target_dir = usb_path / 'nds'
        else:
            continue
        ensure_dir(target_dir)
        shutil.move(str(file), target_dir / file.name)
        console.print(f"  Moved [cyan]{file.name}[/cyan] → [green]{target_dir}[/green]")
        moved += 1
    if moved == 0:
        console.print("[yellow]No .cia or .nds files found to move.[/yellow]")


def clear_screen() -> None:
    os.system('cls' if platform.system() == 'Windows' else 'clear')


def render_menu(file_list: list[str], current_index: int, visible_range: tuple[int, int]) -> None:
    clear_screen()

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(justify="left", no_wrap=True)

    for i, name in enumerate(file_list[visible_range[0]:visible_range[1]]):
        idx = i + visible_range[0]
        if idx == current_index:
            table.add_row(f"[bold cyan]▶  {name}[/bold cyan]")
        else:
            table.add_row(f"   {name}")

    total = len(file_list)
    start, end = visible_range
    subtitle = (
        f"[dim]{current_index + 1}/{total}  "
        f"showing {start + 1}–{min(end, total)}  │  "
        f"↑↓/jk navigate  Enter select  q quit[/dim]"
    )
    console.print(Panel(table, title="[bold]3DS Archive Downloader[/bold]", subtitle=subtitle))


def handle_download(file_list: list[str], current_index: int) -> None:
    file_name = file_list[current_index]
    clear_screen()
    console.rule(f"[bold cyan]{file_name}[/bold cyan]")

    extracted_path = download_file(ARCHIVE_IDENTIFIER, file_name, DESTINATION_PATH)
    if not extracted_path:
        Prompt.ask("\n[red]Download failed.[/red] Press Enter to go back")
        return

    original_file = DESTINATION_PATH / file_name
    if original_file.exists():
        original_file.unlink()

    usb_devices = list_usb_devices()
    if usb_devices:
        console.print("\n[bold]Connected USB devices:[/bold]")
        for i, device in enumerate(usb_devices, 1):
            console.print(f"  {i}. {device}")
        choice = IntPrompt.ask("Select a device (number)", default=1)
        if 1 <= choice <= len(usb_devices):
            move_to_usb(extracted_path, usb_devices[choice - 1])
        else:
            console.print("[yellow]Invalid choice. Files remain in output/[/yellow]")
    else:
        console.print(f"[yellow]No USB devices found. Files saved to:[/yellow] {extracted_path}")

    Prompt.ask("\nPress Enter to continue")


def main() -> None:
    console.print("[bold]Fetching file list from archive.org…[/bold]")
    file_list = get_file_list()

    if not file_list:
        console.print("[red]No .rar or .zip files found.[/red]")
        return

    PAGE_SIZE = 10
    current_index = 0
    visible_range = (0, min(len(file_list), PAGE_SIZE))

    while True:
        render_menu(file_list, current_index, visible_range)
        key = readchar.readkey()

        if key == 'q':
            clear_screen()
            console.print("[dim]Goodbye![/dim]")
            break

        elif key in (readchar.key.ENTER, '\r', '\n'):
            handle_download(file_list, current_index)

        elif key in (readchar.key.UP, 'k'):
            current_index = (current_index - 1) % len(file_list)
            if current_index < visible_range[0]:
                start = current_index
                visible_range = (start, min(len(file_list), start + PAGE_SIZE))

        elif key in (readchar.key.DOWN, 'j'):
            current_index = (current_index + 1) % len(file_list)
            if current_index >= visible_range[1]:
                end = min(len(file_list), current_index + 1)
                visible_range = (end - PAGE_SIZE, end)

        elif key == readchar.key.PAGE_UP:
            current_index = max(0, current_index - PAGE_SIZE)
            start = max(0, current_index - PAGE_SIZE + 1)
            visible_range = (start, start + PAGE_SIZE)

        elif key == readchar.key.PAGE_DOWN:
            current_index = min(len(file_list) - 1, current_index + PAGE_SIZE)
            end = min(len(file_list), current_index + PAGE_SIZE)
            visible_range = (end - PAGE_SIZE, end)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
