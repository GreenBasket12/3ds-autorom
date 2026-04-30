# 3DS Archive Downloader

A terminal UI for browsing, downloading, and installing 3DS CIA/NDS ROMs from the [3dscia_202310](https://archive.org/details/3dscia_202310) archive. Files are automatically extracted and optionally moved to a connected USB/SD card.

## Features

- Browse the full archive with an interactive terminal UI
- Live download progress — speed, ETA, and transfer size
- Auto-extracts `.rar` and `.zip` archives
- Moves `.cia` and `.nds` files to the correct folders on a connected USB device
- Works on **Windows and Linux**

## Requirements

- Python 3.10+

## Setup

```bash
git clone https://github.com/Green-Basket12/3ds-autorom
cd 3ds-autorom
pip install -r requirements.txt
```

## Usage

```bash
python archive.py
```

| Key | Action |
|-----|--------|
| `↑` / `k` | Move up |
| `↓` / `j` | Move down |
| `Page Up/Down` | Scroll a page |
| `Enter` | Download selected file |
| `q` | Quit |

After a download completes, you'll be prompted to select a connected USB/SD device. `.cia` files go to `cia/` and `.nds` files go to `nds/` on the device. If no device is found, files are saved to `output/`.

## Authors

- [Green_Basket12](https://github.com/Green-Basket12)
