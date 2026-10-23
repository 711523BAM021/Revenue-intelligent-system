# Supplied deliveries (private assessment data)

Place the two assessment delivery files here, unchanged, before importing:

```
01_initial.json    # delivery revision 1
02_update.json     # delivery revision 2 (contains the late M07 transcript)
```

They are loaded only by the import service (`backend/app/ingest.py`). The application never
serves a static `/data` route, and the files are excluded from version control and from the
export archive. Do not publish them.

Expected envelope shape (see `DATA_CONTRACT.md`):

```json
{
  "batch_id": "...",
  "revision": 1,
  "exported_at": "...",
  "records": [
    {
      "record_ref": "M07",
      "source_type": "meeting",
      "source_id": "...",
      "payload": { "...": "source metadata" },
      "transcript_payload": { "meeting_id": "...", "turns": [], "unavailable_reason": "..." }
    }
  ]
}
```

If either file is missing, the Import lab says so and refuses to import rather than guessing.
Import History → **Load post-update demo state** imports revision 1 then revision 2.
