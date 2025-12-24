#!/usr/bin/env python3
"""
DeepSeek Chat Export Tool
Konvertiert DeepSeek conversations.json in einzelne Markdown-Dateien
Verwendung: python deepseek_export.py [datei.json]
"""

import json
import os
import sys
from datetime import datetime
import re
from pathlib import Path

def sanitize_filename(filename, replace_spaces=True):
    """
    Macht Dateinamen sicher für das Dateisystem
    """
    if replace_spaces:
        filename = filename.replace(' ', '_')
    
    # Entferne oder ersetze ungültige Zeichen
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)
    filename = filename.strip('._ ')
    
    # Reduziere mehrere Unterstriche auf einen
    filename = re.sub(r'_+', '_', filename)
    
    # Maximallänge begrenzen
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        name = name[:200 - len(ext)]
        filename = name + ext
    
    # Wenn Dateiname leer ist
    if not filename or filename == '_':
        filename = 'unnamed_thread'
    
    return filename

def create_thread_folder(base_folder="deepseek_chats"):
    """Erstellt einen Ordner für die Threads mit Datumsstempel"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"{base_folder}_{timestamp}"
    
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
    
    return folder_name

def find_json_file(input_arg=None):
    """
    Sucht nach JSON-Dateien in dieser Reihenfolge:
    1. Kommandozeilenargument
    2. conversations.json
    3. chat.json
    4. Alle .json Dateien im aktuellen Ordner
    """
    # 1. Kommandozeilenargument
    if input_arg and os.path.exists(input_arg):
        return input_arg
    
    # 2. Standardnamen
    default_files = ['conversations.json', 'chat.json', 'export.json']
    for filename in default_files:
        if os.path.exists(filename):
            return filename
    
    # 3. Alle .json Dateien im aktuellen Ordner
    json_files = [f for f in os.listdir('.') if f.lower().endswith('.json')]
    
    if len(json_files) == 1:
        return json_files[0]
    elif len(json_files) > 1:
        print("\nMehrere JSON-Dateien gefunden:")
        for i, f in enumerate(json_files, 1):
            size = os.path.getsize(f) / (1024*1024)
            print(f"  {i}. {f} ({size:.1f} MB)")
        
        try:
            choice = int(input(f"\nWählen Sie eine Datei (1-{len(json_files)}): "))
            if 1 <= choice <= len(json_files):
                return json_files[choice-1]
        except:
            pass
    
    return None

def export_threads(input_file, max_threads=None, max_messages_per_file=None):
    """
    Exportiert jeden Thread als separate Markdown-Datei
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Fehler beim Lesen der JSON-Datei: {e}")
        return None
    except UnicodeDecodeError:
        # Versuche mit anderer Kodierung
        try:
            with open(input_file, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
        except Exception as e:
            print(f"❌ Fehler beim Lesen der Datei: {e}")
            return None
    
    print(f"✓ Datei geladen: {len(data) if isinstance(data, list) else '1'} Thread(s)")
    
    # Ordner erstellen
    input_name = Path(input_file).stem
    folder = create_thread_folder(f"deepseek_{input_name}")
    print(f"📁 Export-Ordner: {folder}\n")
    
    total_threads = 0
    total_messages = 0
    stats = []
    
    # Index-Datei
    index_file = os.path.join(folder, "00_INDEX.md")
    
    with open(index_file, 'w', encoding='utf-8') as index:
        index.write(f"# DeepSeek Chat Export\n\n")
        index.write(f"**Quelldatei:** `{input_file}`\n")
        index.write(f"**Export-Datum:** {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n")
        index.write(f"**Anzahl Threads:** {len(data) if isinstance(data, list) else 1}\n\n")
        index.write("## Thread-Übersicht\n\n")
        index.write("| Nr. | Datei | Titel | Nachrichten | Größe |\n")
        index.write("|-----|-------|-------|-------------|-------|\n")
    
    # Prüfe Datenformat
    if not isinstance(data, list):
        data = [data]
    
    # Threads verarbeiten
    for thread_idx, thread in enumerate(data, 1):
        if max_threads and thread_idx > max_threads:
            break
            
        if not isinstance(thread, dict):
            print(f"  Thread {thread_idx}: Ungültiges Format - übersprungen")
            continue
        
        # Thread-Informationen
        thread_id = thread.get('id', '')
        title = thread.get('title', f'Thread_{thread_idx}')
        inserted_at = thread.get('inserted_at', '')
        
        # Dateinamen erstellen (OHNE Leerzeichen)
        safe_title = sanitize_filename(title, replace_spaces=True)
        
        # Dateiname mit führender Nummer
        filename = f"{thread_idx:03d}_{safe_title}.md"
        filepath = os.path.join(folder, filename)
        
        print(f"Thread {thread_idx}: {title}")
        
        # Thread-Datei erstellen
        with open(filepath, 'w', encoding='utf-8') as out:
            out.write(f"# {title}\n\n")
            
            # Metadaten
            out.write("**Metadaten:**\n")
            out.write(f"- Thread-ID: `{thread_id}`\n")
            if inserted_at:
                try:
                    dt = datetime.fromisoformat(inserted_at.replace('Z', '+00:00'))
                    formatted_date = dt.strftime('%d.%m.%Y %H:%M:%S')
                    out.write(f"- Erstellt: {formatted_date}\n")
                except:
                    out.write(f"- Erstellt: {inserted_at}\n")
            
            out.write(f"- Datei: `{filename}`\n")
            out.write("\n---\n\n")
            
            # Nachrichten extrahieren
            mapping = thread.get('mapping', {})
            thread_messages = 0
            all_messages = []
            
            for msg_id, msg_data in mapping.items():
                if not isinstance(msg_data, dict) or msg_id == "root":
                    continue
                
                message = msg_data.get('message')
                if not message or not isinstance(message, dict):
                    continue
                
                fragments = message.get('fragments', [])
                for fragment in fragments:
                    if isinstance(fragment, dict):
                        msg_type = fragment.get('type', '')
                        content = fragment.get('content', '')
                        
                        if content and content.strip():
                            all_messages.append({
                                'id': msg_id,
                                'type': msg_type,
                                'content': content
                            })
            
            # Nachrichten sortieren
            try:
                def extract_numeric_id(msg_id):
                    numbers = re.findall(r'\d+', msg_id)
                    return int(numbers[0]) if numbers else float('inf')
                
                all_messages.sort(key=lambda x: extract_numeric_id(x['id']))
            except:
                pass
            
            # Nachrichten ausgeben
            out.write("## Chat-Verlauf\n\n")
            
            for i, msg in enumerate(all_messages):
                if max_messages_per_file and i >= max_messages_per_file:
                    remaining = len(all_messages) - max_messages_per_file
                    out.write(f"\n> *Hinweis: {remaining} weitere Nachrichten gekürzt.*\n")
                    break
                
                if msg['type'] == 'REQUEST':
                    out.write("### 👤 Sie\n\n")
                elif msg['type'] == 'RESPONSE':
                    out.write("### 🤖 DeepSeek\n\n")
                else:
                    out.write(f"### {msg['type']}\n\n")
                
                out.write(f"{msg['content']}\n\n")
                thread_messages += 1
                total_messages += 1
            
            # Zusammenfassung
            out.write("---\n\n")
            out.write(f"**Statistik:** {thread_messages} Nachrichten\n")
        
        # Dateigröße
        file_size_kb = os.path.getsize(filepath) / 1024
        
        # Statistik
        stats.append({
            'idx': thread_idx,
            'filename': filename,
            'title': title,
            'messages': thread_messages,
            'size_kb': file_size_kb
        })
        
        print(f"  → {thread_messages} Nachrichten in '{filename}' ({file_size_kb:.1f} KB)")
        total_threads += 1
        
        # Index aktualisieren
        with open(index_file, 'a', encoding='utf-8') as index:
            index.write(f"| {thread_idx} | [{filename}](./{filename}) | {title} | {thread_messages} | {file_size_kb:.1f} KB |\n")
    
    # Index-Datei vervollständigen
    with open(index_file, 'a', encoding='utf-8') as index:
        index.write(f"\n## Gesamtstatistik\n")
        index.write(f"- **Exportierte Threads:** {total_threads}\n")
        index.write(f"- **Gesamtnachrichten:** {total_messages}\n")
        
        if total_threads > 0:
            avg_messages = total_messages / total_threads
            index.write(f"- **Durchschnitt pro Thread:** {avg_messages:.1f} Nachrichten\n")
        
        total_size_mb = sum(stat['size_kb'] for stat in stats) / 1024
        index.write(f"- **Gesamtgröße:** {total_size_mb:.2f} MB\n")
        
        if stats:
            largest = max(stats, key=lambda x: x['size_kb'])
            smallest = min(stats, key=lambda x: x['size_kb'])
            index.write(f"- **Größte Datei:** {largest['filename']} ({largest['size_kb']:.1f} KB)\n")
            index.write(f"- **Kleinste Datei:** {smallest['filename']} ({smallest['size_kb']:.1f} KB)\n")
        
        index.write(f"\n**Ordner:** `{folder}`\n")
        index.write(f"**Index:** [00_INDEX.md](./00_INDEX.md)\n")
    
    # Zusammenfassung anzeigen
    print(f"\n{'='*60}")
    print("EXPORT ZUSAMMENFASSUNG")
    print(f"{'='*60}")
    print(f"✓ Threads exportiert: {total_threads}")
    print(f"✓ Gesamtnachrichten: {total_messages}")
    
    if total_threads > 0:
        avg_messages = total_messages / total_threads
        print(f"✓ Durchschnitt pro Thread: {avg_messages:.1f} Nachrichten")
    
    total_size_mb = sum(stat['size_kb'] for stat in stats) / 1024
    print(f"✓ Gesamtgröße: {total_size_mb:.2f} MB")
    
    if stats:
        print(f"\nTop 5 größte Dateien:")
        for stat in sorted(stats, key=lambda x: x['size_kb'], reverse=True)[:5]:
            print(f"  {stat['filename']}: {stat['messages']} Nachrichten ({stat['size_kb']:.1f} KB)")
    
    print(f"\n✅ Export abgeschlossen!")
    print(f"   📁 Ordner: {folder}/")
    print(f"   📄 Index: {folder}/00_INDEX.md")
    
    return folder

def main():
    print(f"{'='*60}")
    print("DEEPSEEK CHAT EXPORT TOOL")
    print(f"{'='*60}")
    
    # Datei suchen
    input_arg = sys.argv[1] if len(sys.argv) > 1 else None
    input_file = find_json_file(input_arg)
    
    if not input_file:
        print("❌ Keine JSON-Datei gefunden!")
        print("\nBitte eine der folgenden Optionen:")
        print("1. conversations.json im gleichen Ordner ablegen")
        print("2. Andere JSON-Datei als Argument angeben:")
        print(f"   python {sys.argv[0]} meine_datei.json")
        input("\nDrücke Enter zum Beenden...")
        return
    
    file_size = os.path.getsize(input_file) / (1024*1024)
    print(f"📄 Eingabedatei: {input_file} ({file_size:.1f} MB)")
    
    print(f"\n{'='*60}")
    print("EXPORT OPTIONEN:")
    print(f"{'='*60}")
    print("1. Standard: Alle Threads als einzelne Dateien")
    print("2. Testlauf: Nur erste 5 Threads")
    print("3. Mit Begrenzung: Max. 100 Nachrichten pro Datei")
    
    try:
        choice = input("\nIhre Wahl (1-3): ").strip()
        
        if choice == "1":
            print("\n🚀 Starte Standard-Export...")
            export_threads(input_file)
        
        elif choice == "2":
            print("\n🧪 Starte Testlauf (erste 5 Threads)...")
            folder = export_threads(input_file, max_threads=5)
            if folder:
                print(f"\n✅ Testlauf abgeschlossen.")
                print(f"   Bitte prüfen Sie: {folder}")
        
        elif choice == "3":
            print("\n📊 Starte Export mit Begrenzung...")
            export_threads(input_file, max_messages_per_file=100)
        
        else:
            print("\nℹ️ Ungültige Auswahl. Verwende Option 1 (Standard).")
            export_threads(input_file)
    
    except KeyboardInterrupt:
        print("\n\n⏹️ Export abgebrochen.")
    except Exception as e:
        print(f"\n❌ Unerwarteter Fehler: {e}")
    
    input("\nDrücke Enter zum Beenden...")

# Batch-Skript Vorlage für Windows
BATCH_TEMPLATE = """@echo off
echo DeepSeek Chat Export Tool
echo.
echo Bitte conversations.json in diesen Ordner legen
echo oder per Drag&Drop auf diese Datei ziehen.
echo.
if "%~1"=="" (
    echo Keine Datei angegeben, suche Standarddateien...
    python "%~dp0deepseek_export.py"
) else (
    echo Verarbeite: %~1
    python "%~dp0deepseek_export.py" "%~1"
)
pause
"""

# Shell-Skript Vorlage für Linux/macOS
SHELL_TEMPLATE = """#!/bin/bash
echo "DeepSeek Chat Export Tool"
echo ""
echo "Usage: $0 [conversations.json]"
echo ""

if [ $# -eq 0 ]; then
    echo "No file specified, looking for default files..."
    python3 "$(dirname "$0")/deepseek_export.py"
else
    echo "Processing: $1"
    python3 "$(dirname "$0")/deepseek_export.py" "$1"
fi

read -p "Press Enter to continue..."
"""

if __name__ == "__main__":
    # Prüfe ob Hilfeflag gesetzt ist
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', '/?']:
        print(f"\nVerwendung: {sys.argv[0]} [datei.json]")
        print("\nOptionen:")
        print("  datei.json    - Zu konvertierende JSON-Datei")
        print("  (keine)       - Sucht automatisch nach conversations.json")
        print("  -h, --help    - Diese Hilfe anzeigen")
        print("\nBeispiele:")
        print(f"  {sys.argv[0]} conversations.json")
        print(f"  {sys.argv[0]} chat_export.json")
        print(f"  {sys.argv[0]}              (sucht automatisch)")
        
        # Frage ob Batch-Skripte erstellt werden sollen
        create = input("\nBatch-Skripte erstellen? (j/n): ").lower()
        if create == 'j':
            with open('deepseek_export.bat', 'w', encoding='utf-8') as f:
                f.write(BATCH_TEMPLATE)
            with open('deepseek_export.sh', 'w', encoding='utf-8') as f:
                f.write(SHELL_TEMPLATE)
            os.chmod('deepseek_export.sh', 0o755)
            print("✓ Batch-Skripte erstellt: deepseek_export.bat und deepseek_export.sh")
        
        sys.exit(0)
    
    # Normale Ausführung
    main()

