"""Apply editorial workbook content without replacing results or participation data."""
INSTANCE_COLUMNS = {
    'strategy_notes': "TEXT NOT NULL DEFAULT ''",
    'image_url': "TEXT NOT NULL DEFAULT ''",
    'video_url': "TEXT NOT NULL DEFAULT ''",
    'guest_appearances': "TEXT NOT NULL DEFAULT ''",
    'workbook_family': "TEXT NOT NULL DEFAULT ''",
    'workbook_sheet': "TEXT NOT NULL DEFAULT ''",
    'workbook_row': 'INTEGER',
}


def migrate_workbook_columns(db):
    columns = {r['name'] for r in db.execute('PRAGMA table_info(competition_instances)')}
    for name, definition in INSTANCE_COLUMNS.items():
        if name not in columns:
            db.execute(f'ALTER TABLE competition_instances ADD COLUMN {name} {definition}')
    db.execute('CREATE INDEX IF NOT EXISTS idx_instances_event_key ON competition_instances(source_event_key)')


def apply_workbook_content(db, content):
    redirects = {}
    if not content:
        return redirects
    if content.get('version') != 1:
        raise ValueError('Unsupported workbook content version')

    def ensure_family(name):
        existing = db.execute('SELECT id FROM competitions WHERE name = ? COLLATE NOCASE', (name,)).fetchone()
        if existing:
            return existing['id']
        return db.execute('''
            INSERT INTO competitions (name, category, description, verification_status)
            VALUES (?, 'Competition format', ?, 'workbook notes')
        ''', (name, "See the season appearances for this format's rules.")).lastrowid

    for name, family in content['families'].items():
        family_id = ensure_family(name)
        for column in ('description', 'strategy'):
            if family.get(column):
                db.execute(f'UPDATE competitions SET {column} = ? WHERE id = ?', (family[column], family_id))
        alias = family.get('workbook_name')
        if alias and alias.casefold() != name.casefold():
            current = db.execute('SELECT aliases FROM competitions WHERE id = ?', (family_id,)).fetchone()[0]
            if alias not in current.split(', '):
                db.execute('UPDATE competitions SET aliases = ? WHERE id = ?', (', '.join(filter(None, [current, alias])), family_id))

    # Name/week/type are matching keys, not replacements for the result catalog.
    # A shared event can have a secondary association with a more specific type
    # (for example HOH / Entry); changing it would alter the win-rate breakdown.
    fields = {'description': 'rules_notes', 'strategy': 'strategy_notes', 'image_url': 'image_url',
              'video_url': 'video_url', 'guest_appearances': 'guest_appearances', 'family': 'workbook_family',
              'sheet': 'workbook_sheet', 'row': 'workbook_row'}
    for event_key, entry in content['events'].items():
        rows = db.execute('''
            SELECT ci.id, ci.competition_id, c.name, s.season_number
            FROM competition_instances ci JOIN competitions c ON c.id = ci.competition_id
            JOIN seasons s ON s.id = ci.season_id
            WHERE ci.source_event_key = ? ORDER BY ci.id
        ''', (event_key,)).fetchall()
        if not rows or any(r['season_number'] != entry['season'] for r in rows):
            raise ValueError(f'Workbook event no longer matches catalog: {event_key}')
        family = entry.get('family')
        if family and family.casefold() not in ('none', 'n/a'):
            family_ids = [ensure_family(name) for name in entry.get('families', [family])]
            available = [r for r in rows if r['competition_id'] not in family_ids]
            for family_id in family_ids:
                if family_id in [r['competition_id'] for r in rows]:
                    continue
                # Reassign the primary appearance, retaining its ID and every participant.
                # Existing secondary format associations are not deleted.
                if not available:
                    raise ValueError(f'{event_key}: additional family association requires review')
                primary = available.pop(0)
                db.execute('UPDATE competition_instances SET competition_id = ? WHERE id = ?', (family_id, primary['id']))
                if not db.execute('SELECT 1 FROM competition_instances WHERE competition_id = ?', (primary['competition_id'],)).fetchone():
                    db.execute("UPDATE competitions SET category = 'Season-specific name' WHERE id = ?", (primary['competition_id'],))
                    redirects[primary['competition_id']] = family_id
        updates = {column: entry[key] for key, column in fields.items() if entry.get(key) not in ('', None)}
        if updates:
            db.execute('UPDATE competition_instances SET ' + ', '.join(f'{k} = ?' for k in updates) + ' WHERE source_event_key = ?',
                       [*updates.values(), event_key])
        for row in rows:
            for field, urls in entry.get('sources', {}).items():
                for url in urls:
                    title = f'Workbook {field.replace("_", " ")} source'
                    if not db.execute('SELECT 1 FROM sources WHERE instance_id = ? AND url = ? AND title = ?', (row['id'], url, title)).fetchone():
                        db.execute('''INSERT INTO sources (instance_id, title, url, source_type, notes)
                                      VALUES (?, ?, ?, 'workbook reference', 'Imported from a source note in the research workbook.')''',
                                   (row['id'], title, url))
    return redirects
